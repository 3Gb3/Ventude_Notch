"""Provedores pela Responses API pública (POST https://api.openai.com/v1/responses).

- ChatGPTPlanProvider: token OAuth do Sign in with ChatGPT. Segue as limitações do
  preview: store=false, stream=true, histórico enviado em `input`, sem temperature etc.
  Ferramentas de função exigem namespaces nesse modo; como o formato não está detalhado
  na documentação, as ferramentas do Ventude ficam desativadas nesse provedor.
- ApiKeyProvider: chave de API da OpenAI configurada explicitamente pelo usuário.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx

from ventude.assistant.providers.base import Provider
from ventude.assistant.types import (
    ChatMessage,
    Completed,
    Failed,
    ProviderUnavailable,
    TextDelta,
    ToolCall,
    ToolCallsRequested,
)

BASE = "https://api.openai.com/v1"


def to_input(history: list[ChatMessage]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for m in history:
        if m.role == "user":
            content: list[dict[str, Any]] = [{"type": "input_text", "text": m.text}]
            content += [{"type": "input_image", "image_url": url} for url in m.images]
            items.append({"role": "user", "content": content})
        else:
            items.append({"role": "assistant", "content": m.text})
    return items


async def parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[dict[str, Any]]:
    data: list[str] = []
    async for line in lines:
        if line.startswith("data:"):
            data.append(line[5:].strip())
        elif not line.strip() and data:
            raw = "\n".join(data)
            data = []
            if raw and raw != "[DONE]":
                yield json.loads(raw)
    if data and data[0] != "[DONE]":
        yield json.loads("\n".join(data))


class ResponsesProvider(Provider):
    supports_images = True

    def __init__(
        self,
        token_getter: Callable[[], Awaitable[str | None]],
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = token_getter
        self.http = http or httpx.AsyncClient(timeout=httpx.Timeout(30, read=300))

    async def _bearer(self) -> str:
        tok = await self._token()
        if not tok:
            raise ProviderUnavailable(self.availability()[1])
        return tok

    async def stream(
        self,
        model: str,
        instructions: str,
        history: list[ChatMessage],
        tools: list[dict[str, Any]],
        extra_input: list[dict[str, Any]],
    ) -> AsyncIterator[Any]:
        try:
            tok = await self._bearer()
        except ProviderUnavailable as exc:
            yield Failed(str(exc))
            return
        body: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": to_input(history) + extra_input,
            "store": False,
            "stream": True,
        }
        if tools and self.supports_tools:
            body["tools"] = tools
        calls: list[ToolCall] = []
        text: list[str] = []
        try:
            async with self.http.stream(
                "POST",
                f"{BASE}/responses",
                json=body,
                headers={"Authorization": f"Bearer {tok}"},
            ) as r:
                if r.status_code != 200:
                    detail = (await r.aread()).decode(errors="replace")[:300]
                    yield Failed(f"Erro {r.status_code} da API: {detail}")
                    return
                async for ev in parse_sse(r.aiter_lines()):
                    t = ev.get("type")
                    if t == "response.output_text.delta":
                        text.append(ev.get("delta", ""))
                        yield TextDelta(ev.get("delta", ""))
                    elif t == "response.output_item.done":
                        item = ev.get("item", {})
                        if item.get("type") == "function_call":
                            try:
                                args = json.loads(item.get("arguments") or "{}")
                            except ValueError:
                                args = {}
                            calls.append(ToolCall(item.get("call_id", ""), item["name"], args))
                    elif t in ("response.failed", "error"):
                        err = (ev.get("response") or {}).get("error") or ev.get("error") or {}
                        yield Failed(f"Falha: {err.get('code') or err.get('message') or t}")
                        return
                    elif t == "response.incomplete":
                        yield Failed("Resposta incompleta.")
                        return
                    elif t == "response.completed":
                        if calls:
                            yield ToolCallsRequested(calls)
                        else:
                            yield Completed("".join(text))
                        return
        except httpx.HTTPError as exc:
            yield Failed(f"Erro de rede: {exc.__class__.__name__}")
            return
        yield Failed("O stream terminou sem response.completed.")

    async def list_models(self) -> list[tuple[str, str]]:
        tok = await self._bearer()
        r = await self.http.get(f"{BASE}/models", headers={"Authorization": f"Bearer {tok}"})
        r.raise_for_status()
        data = r.json()
        if "models" in data:  # catálogo do plano ChatGPT
            return [
                (m["slug"], m.get("display_name") or m["slug"])
                for m in data["models"]
                if m.get("visibility") == "list"
            ]
        return sorted((m["id"], m["id"]) for m in data.get("data", []))

    async def close(self) -> None:
        await self.http.aclose()


class ChatGPTPlanProvider(ResponsesProvider):
    id = "chatgpt"
    label = "ChatGPT (seu plano)"
    supports_tools = False

    def __init__(self, auth: Any, http: httpx.AsyncClient | None = None) -> None:
        async def token() -> str | None:
            if not auth.credentials():
                return None
            return await auth.access_token()

        super().__init__(token, http)
        self.auth = auth

    def availability(self) -> tuple[bool, str]:
        if self.auth.credentials():
            return True, f"Conectado: {self.auth.account_label()}"
        return False, "Clique em Conectar para entrar com sua conta do ChatGPT."


class ApiKeyProvider(ResponsesProvider):
    id = "openai_api"
    label = "OpenAI API (chave)"
    supports_tools = True

    def __init__(self, store: Any, http: httpx.AsyncClient | None = None) -> None:
        async def token() -> str | None:
            return store.get("openai_api_key")

        super().__init__(token, http)
        self.store = store

    def availability(self) -> tuple[bool, str]:
        if self.store.get("openai_api_key"):
            return True, "Chave de API configurada."
        return False, "Opcional: configure uma chave de API da OpenAI para usar este provedor."
