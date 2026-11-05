"""Cache em SQLite com TTL. Usado pelos widgets da Fase 5."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, path: Path) -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL)"
        )
        self.conn.commit()

    def get(self, key: str) -> Any | None:
        row = self.conn.execute("SELECT value, expires FROM cache WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        value, expires = row
        if expires < time.time():
            with self.conn:
                self.conn.execute("DELETE FROM cache WHERE key=?", (key,))
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO cache(key, value, expires) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, expires=excluded.expires",
                (key, json.dumps(value, ensure_ascii=False), time.time() + ttl_seconds),
            )

    def clear(self, prefix: str = "") -> None:
        with self.conn:
            if prefix:
                self.conn.execute("DELETE FROM cache WHERE key LIKE ?", (prefix + "%",))
            else:
                self.conn.execute("DELETE FROM cache")

    def close(self) -> None:
        self.conn.close()
