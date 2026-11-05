"""Codex app-server como subprocesso gerenciado (JSON-RPC por stdio).

Segue https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server:
ACCESS_TOKEN no ambiente do processo filho, provedor "openai_chatgpt_plan" via -c,
initialize -> initialized -> thread/start -> turn/start, item/agentMessage/delta e
turn/completed (só status "completed" é sucesso). Renovação: reinicia com novo token
e usa thread/resume.
O Codex não é instalado pelo Ventude; se não estiver no PATH, o provedor fica indisponível.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import os
import shutil
from collections.abc import AsyncIterator, Callable
from typing import Any

from ventude import __version__
from ventude.assistant.providers.base import Provider
from ventude.assistant.types import ChatMessage, Completed, Failed, TextDelta

PROVIDER_ARGS = [
    'model_provider="openai_chatgpt_plan"',
    'model_providers.openai_chatgpt_plan.name="ChatGPT plan"',
    'model_providers.openai_chatgpt_plan.base_url="https://api.openai.com/v1"',
    'model_providers.openai_chatgpt_plan.env_key="ACCESS_TOKEN"',
    'model_providers.openai_chatgpt_plan.wire_api="responses"',
    "model_providers.openai_chatgpt_plan.requires_openai_auth=false",
    "model_providers.openai_chatgpt_plan.supports_websockets=false",
]

INSTALL_HELP = (
    "Codex CLI não encontrado. Para usar este provedor, instale o Codex por conta própria "
    "(veja https://developers.openai.com/codex) e reinicie o Ventude. "
    "O Ventude não instala nada globalmente."
)


def build_command(codex: str) -> list[str]:
    cmd = [codex, "app-server", "--listen", "stdio://"]
    for a in PROVIDER_ARGS:
        cmd += ["-c", a]
    return cmd


class JsonRpcProcess:
    def __init__(self, proc: Any) -> None:
        self.proc = proc
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self.notifications: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._reader = asyncio.ensure_future(self._read())

    async def _read(self) -> None:
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "id" in msg and ("result" in msg or "error" in msg) and "method" not in msg:
                fut = self._pending.pop(msg["id"], None)
                if fut and not fut.done():
                    if "error" in msg:
                        fut.set_exception(RuntimeError(str(msg["error"].get("message", "erro"))))
                    else:
                        fut.set_result(msg["result"])
            else:
                await self.notifications.put(msg)
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(RuntimeError("app-server encerrou"))
        await self.notifications.put({"method": "__closed__"})

    async def _send(self, payload: dict[str, Any]) -> None:
        self.proc.stdin.write((json.dumps(payload) + "\n").encode())
        await self.proc.stdin.drain()

    async def request(self, method: str, params: dict[str, Any], timeout: float = 60) -> Any:
        rid = next(self._ids)
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        await self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return await asyncio.wait_for(fut, timeout)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        await self._send(msg)

    async def respond(self, rid: Any, result: dict[str, Any]) -> None:
        await self._send({"jsonrpc": "2.0", "id": rid, "result": result})

    async def close(self) -> None:
        self._reader.cancel()
        with contextlib.suppress(ProcessLookupError):
            self.proc.terminate()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.proc.wait(), 5)


class CodexAppServerProvider(Provider):
    id = "codex"
    label = "Codex app-server"
    supports_tools = False  # o Codex usa as próprias ferramentas locais

    def __init__(
        self,
        auth: Any,
        which: Callable[[str], str | None] = shutil.which,
        spawn: Callable[..., Any] | None = None,
    ) -> None:
        self.auth = auth
        self._which = which
        self._spawn = spawn or asyncio.create_subprocess_exec
        self._rpc: JsonRpcProcess | None = None
        self._token_in_use: str | None = None
        self.thread_id: str | None = None
        self._active_turn: str | None = None
        self._context: tuple[int, str] | None = None
        self._has_turn = False

    async def select_context(self, conversation_id: int, instructions: str) -> None:
        context = (conversation_id, instructions)
        if context != self._context:
            await self.close()
            self.thread_id = None
            self._has_turn = False
            self._context = context

    def availability(self) -> tuple[bool, str]:
        if not self._which("codex"):
            return False, INSTALL_HELP
        if not self.auth.credentials():
            return False, "Conecte sua conta do ChatGPT (botão Conectar) para usar o Codex."
        return True, "Codex encontrado e conta conectada."

    async def _ensure(self, model: str) -> JsonRpcProcess:
        token = await self.auth.access_token()
        if self._rpc and token == self._token_in_use and self._rpc.proc.returncode is None:
            return self._rpc
        if self._rpc:
            await self._rpc.close()
        codex = self._which("codex")
        if not codex:
            raise RuntimeError(INSTALL_HELP)
        env = dict(os.environ, ACCESS_TOKEN=token)
        proc = await self._spawn(
            *build_command(codex),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        rpc = JsonRpcProcess(proc)
        await rpc.request(
            "initialize",
            {"clientInfo": {"name": "ventude", "title": "Ventude", "version": __version__}},
        )
        await rpc.notify("initialized")
        if self.thread_id:
            await rpc.request("thread/resume", {"threadId": self.thread_id})
        else:
            res = await rpc.request("thread/start", {"model": model})
            self.thread_id = res["thread"]["id"]
        self._rpc, self._token_in_use = rpc, token
        return rpc

    async def list_models(self) -> list[tuple[str, str]]:
        ok, msg = self.availability()
        if not ok:
            raise RuntimeError(msg)
        rpc = await self._ensure("")
        res = await rpc.request("model/list", {})
        items = res.get("data") or res.get("models") or []
        out = []
        for m in items:
            slug = m.get("model") or m.get("id") or m.get("slug")
            if slug:
                out.append((slug, m.get("displayName") or m.get("display_name") or slug))
        return out

    async def stream(
        self,
        model: str,
        instructions: str,
        history: list[ChatMessage],
        tools: list[dict[str, Any]],
        extra_input: list[dict[str, Any]],
    ) -> AsyncIterator[Any]:
        ok, msg = self.availability()
        if not ok:
            yield Failed(msg)
            return
        try:
            rpc = await self._ensure(model)
            last = history[-1].text if history else ""
            if instructions:
                messages = history[-1:] if self._has_turn else history
                context = "\n\n".join(f"{m.role}: {m.text}" for m in messages)
                last = f"Orientações do Ventude:\n{instructions}\n\nConversa:\n{context}"
            res = await rpc.request(
                "turn/start",
                {"threadId": self.thread_id, "input": [{"type": "text", "text": last}]},
            )
            self._active_turn = (res.get("turn") or {}).get("id")
            self._has_turn = True
            text: list[str] = []
            while True:
                ev = await rpc.notifications.get()
                method = ev.get("method", "")
                params = ev.get("params") or {}
                if method == "item/agentMessage/delta":
                    delta = params.get("delta", "")
                    text.append(delta)
                    yield TextDelta(delta)
                elif method.endswith("requestApproval") and "id" in ev:
                    # O Ventude não aprova comandos/edições do Codex automaticamente.
                    await rpc.respond(ev["id"], {"decision": "decline"})
                elif method == "turn/completed":
                    status = (params.get("turn") or {}).get("status")
                    if status == "completed":
                        yield Completed("".join(text))
                    else:
                        yield Failed(f"Turno terminou com status: {status}")
                    return
                elif method == "__closed__":
                    yield Failed("O app-server encerrou.")
                    return
        except asyncio.CancelledError:
            await self.interrupt()
            raise
        except Exception as exc:  # noqa: BLE001
            yield Failed(f"Codex: {exc}")
        finally:
            self._active_turn = None

    async def interrupt(self) -> None:
        if self._rpc and self.thread_id and self._active_turn:
            with contextlib.suppress(Exception):
                await self._rpc.request(
                    "turn/interrupt",
                    {"threadId": self.thread_id, "turnId": self._active_turn},
                    timeout=5,
                )

    async def close(self) -> None:
        if self._rpc:
            await self._rpc.close()
            self._rpc = None
