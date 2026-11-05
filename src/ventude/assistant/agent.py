"""Agente: orquestra provedor, ferramentas, permissões e histórico. Não depende da UI."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from ventude.assistant.history import ChatHistory
from ventude.assistant.memory import PersonalMemory
from ventude.assistant.permissions import PermissionManager
from ventude.assistant.providers.base import Provider
from ventude.assistant.tools.base import ToolError, ToolRegistry
from ventude.assistant.types import (
    ChatMessage,
    Completed,
    Failed,
    TextDelta,
    ToolCallsRequested,
    ToolUsed,
)

INSTRUCTIONS = (
    "Você é o assistente do Ventude, um app de Windows. Responda em português, de forma "
    "direta. Use as ferramentas disponíveis só quando forem necessárias e nunca invente "
    "resultados de ferramentas."
)
MAX_TOOL_ROUNDS = 6


class Agent:
    def __init__(
        self,
        history: ChatHistory,
        tools: ToolRegistry,
        permissions: PermissionManager,
        memory: PersonalMemory | None = None,
    ) -> None:
        self.history = history
        self.tools = tools
        self.permissions = permissions
        self.memory = memory
        self.conversation_id = history.latest_conversation() or history.new_conversation()

    def new_conversation(self) -> None:
        self.conversation_id = self.history.new_conversation()

    def messages(self) -> list[ChatMessage]:
        return self.history.messages(self.conversation_id)

    def select_conversation(self, conversation_id: int) -> None:
        if not self.history.exists(conversation_id):
            raise ValueError("Conversa não encontrada.")
        self.conversation_id = conversation_id

    async def run_tool(self, name: str, args: dict[str, Any]) -> tuple[str, str]:
        """Retorna (status, saída em texto)."""
        try:
            tool = self.tools.get(name)
            tool.validate(args)
        except ToolError as exc:
            self.permissions.record(name, "error", str(exc))
            return "error", str(exc)
        summary = f"{name}({json.dumps(args, ensure_ascii=False)})"
        if name == "remember_user_preference":
            summary = f'guardar no seu perfil “{args["fact"]}”'
        if not await self.permissions.authorize(name, args, tool.level, tool.destructive, summary):
            return "denied", "Ação negada pelo usuário ou pela política."
        try:
            result = tool.handler(args)
            if asyncio.iscoroutine(result):
                result = await result
        except ToolError as exc:
            self.permissions.record(name, "error", str(exc))
            return "error", str(exc)
        except Exception as exc:  # noqa: BLE001
            self.permissions.record(name, "error", repr(exc))
            return "error", f"Falha inesperada: {exc.__class__.__name__}"
        out = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        self.permissions.record(name, "executed", out[:500])
        return "executed", out

    async def send(
        self, provider: Provider, model: str, text: str, images: list[str] | None = None
    ) -> AsyncIterator[Any]:
        user = ChatMessage("user", text, list(images or []))
        history = self.messages() + [user]
        self.history.add(self.conversation_id, user)
        specs = self.tools.specs() if provider.supports_tools else []
        if self.memory is not None and not self.memory.enabled:
            specs = [s for s in specs if s["name"] != "remember_user_preference"]
        extra: list[dict[str, Any]] = []
        full: list[str] = []
        instructions = INSTRUCTIONS + (self.memory.context() if self.memory else "")
        if not provider.supports_tools:
            instructions += (
                " Neste provedor não há ferramenta para salvar memórias. "
                "Oriente o usuário a editar Sobre você; nunca afirme que salvou algo."
            )
        await provider.select_context(self.conversation_id, instructions)
        for _ in range(MAX_TOOL_ROUNDS):
            requested = None
            async for ev in provider.stream(model, instructions, history, specs, extra):
                if isinstance(ev, TextDelta):
                    full.append(ev.text)
                    yield ev
                elif isinstance(ev, ToolCallsRequested):
                    requested = ev
                elif isinstance(ev, Failed):
                    if full:
                        self.history.add(
                            self.conversation_id, ChatMessage("assistant", "".join(full))
                        )
                    yield ev
                    return
                elif isinstance(ev, Completed):
                    reply = "".join(full) or ev.text
                    self.history.add(self.conversation_id, ChatMessage("assistant", reply))
                    yield Completed(reply)
                    return
            if requested is None:
                yield Failed("O provedor encerrou sem resposta.")
                return
            for call in requested.calls:
                status, out = await self.run_tool(call.name, call.arguments)
                yield ToolUsed(call.name, status, out[:200])
                extra.append(
                    {
                        "type": "function_call",
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    }
                )
                extra.append(
                    {"type": "function_call_output", "call_id": call.call_id, "output": out}
                )
        yield Failed("Limite de chamadas de ferramenta atingido.")
