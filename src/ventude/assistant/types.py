from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    text: str
    images: list[str] = field(default_factory=list)  # data URLs


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


# ----- eventos emitidos por provedores/agente -----
@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCallsRequested:
    calls: list[ToolCall]


@dataclass
class ToolUsed:
    name: str
    status: str  # executed | denied | error
    summary: str = ""


@dataclass
class Completed:
    text: str = ""


@dataclass
class Failed:
    message: str


class ProviderUnavailable(RuntimeError):
    """Provedor não configurado/conectado; a mensagem explica o que fazer."""
