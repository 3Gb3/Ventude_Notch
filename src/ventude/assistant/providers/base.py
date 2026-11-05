from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ventude.assistant.types import ChatMessage


class Provider(ABC):
    id: str = ""
    label: str = ""
    supports_tools: bool = False
    supports_images: bool = False

    @abstractmethod
    def availability(self) -> tuple[bool, str]:
        """(disponível, explicação para o usuário)."""

    @abstractmethod
    async def list_models(self) -> list[tuple[str, str]]:
        """[(slug, nome exibido)]."""

    @abstractmethod
    def stream(
        self,
        model: str,
        instructions: str,
        history: list[ChatMessage],
        tools: list[dict[str, Any]],
        extra_input: list[dict[str, Any]],
    ) -> AsyncIterator[Any]:
        """Emite TextDelta/ToolCallsRequested/Completed/Failed."""

    async def close(self) -> None:  # noqa: B027
        pass

    async def select_context(self, conversation_id: int, instructions: str) -> None:  # noqa: B027
        """Allows stateful providers to keep local sessions isolated."""
        pass
