from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

log = logging.getLogger("ventude.audit")


class Level(StrEnum):
    AUTO = "auto"
    CONFIRM = "confirm"
    DENY = "deny"


Approver = Callable[[str, dict[str, Any], str], Awaitable[bool]]


class PermissionManager:
    """Decide se uma ferramenta pode rodar e registra cada passo (auditoria)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        approver: Approver | None = None,
        overrides: dict[str, Level] | None = None,
    ) -> None:
        self.conn = conn
        self.approver = approver
        self.overrides = dict(overrides or {})
        conn.execute(
            "CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " ts REAL, tool TEXT, stage TEXT, detail TEXT)"
        )
        conn.commit()

    def level_for(self, tool: str, default: Level, destructive: bool) -> Level:
        level = self.overrides.get(tool, default)
        if destructive and level == Level.AUTO:
            level = Level.CONFIRM  # destrutivo nunca roda sem aprovação
        return level

    def record(self, tool: str, stage: str, detail: Any = "") -> None:
        if tool == "remember_user_preference":
            # The audit records the decision; the editable profile owns the actual fact.
            detail = ""
        text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
        text = text[:2000]
        with self.conn:
            self.conn.execute(
                "INSERT INTO audit_log(ts, tool, stage, detail) VALUES(?,?,?,?)",
                (time.time(), tool, stage, text),
            )
        log.info("tool=%s stage=%s", tool, stage)

    async def authorize(
        self, tool: str, args: dict[str, Any], default: Level, destructive: bool, summary: str
    ) -> bool:
        self.record(tool, "requested", args)
        level = self.level_for(tool, default, destructive)
        if level == Level.DENY:
            self.record(tool, "denied", "política")
            return False
        if level == Level.CONFIRM:
            ok = bool(self.approver and await self.approver(tool, args, summary))
            self.record(tool, "approved" if ok else "denied", "usuário")
            return ok
        self.record(tool, "approved", "auto")
        return True

    def history(self, limit: int = 50) -> list[tuple[str, str, str]]:
        return self.conn.execute(
            "SELECT tool, stage, detail FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
