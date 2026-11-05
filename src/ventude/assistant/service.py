"""Monta o agente com provedores e ferramentas (sem UI)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from ventude.assistant.agent import Agent
from ventude.assistant.auth import ChatGPTAuth
from ventude.assistant.history import ChatHistory
from ventude.assistant.memory import PersonalMemory, memory_tools
from ventude.assistant.permissions import Approver, PermissionManager
from ventude.assistant.providers.base import Provider
from ventude.assistant.providers.codex import CodexAppServerProvider
from ventude.assistant.providers.responses import ApiKeyProvider, ChatGPTPlanProvider
from ventude.assistant.token_store import TokenStore
from ventude.assistant.tools.base import ToolRegistry
from ventude.assistant.tools.file_tools import PathGuard, default_roots, file_tools
from ventude.assistant.tools.system_tools import system_tools
from ventude.assistant.tools.ventude_tools import ventude_tools
from ventude.core.config import Settings
from ventude.storage.database import Database


class AssistantService:
    def __init__(
        self,
        data_dir: Path,
        db: Database,
        get_settings: Callable[[], Settings],
        apply_settings: Callable[[Settings], None],
        on_pinned_changed: Callable[[], None],
        approver: Approver,
        store: TokenStore | None = None,
    ) -> None:
        self.store = store or TokenStore(data_dir / "credentials.bin")
        self.auth = ChatGPTAuth(self.store)
        self.conn = sqlite3.connect(data_dir / "assistant.db", check_same_thread=False)
        self.memory = PersonalMemory(data_dir / "personal_memory.db")
        registry = ToolRegistry()
        registry.register(
            *ventude_tools(db, get_settings, apply_settings, on_pinned_changed),
            *system_tools(),
            *file_tools(PathGuard(default_roots())),
            *memory_tools(self.memory),
        )
        self.permissions = PermissionManager(self.conn, approver)
        self.agent = Agent(ChatHistory(self.conn), registry, self.permissions, self.memory)
        self.providers: dict[str, Provider] = {
            p.id: p
            for p in (
                ChatGPTPlanProvider(self.auth),
                CodexAppServerProvider(self.auth),
                ApiKeyProvider(self.store),
            )
        }

    def set_api_key(self, key: str) -> None:
        if key.strip():
            self.store.set("openai_api_key", key.strip())
        else:
            self.store.delete("openai_api_key")

    async def close(self) -> None:
        for p in self.providers.values():
            await p.close()
        await self.auth.http.aclose()
        self.memory.close()
        self.conn.close()
