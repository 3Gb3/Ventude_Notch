from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ventude.core.config import Settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pinned_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('app', 'folder')),
    label TEXT NOT NULL,
    path TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    UNIQUE(kind, path)
);
"""


@dataclass
class PinnedItem:
    id: int
    kind: str
    label: str
    path: str
    position: int


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        # Usado também pela thread do assistente (operações curtas e sequenciais).
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # settings
    def load_settings(self) -> Settings:
        rows = self._conn.execute("SELECT key, value FROM settings").fetchall()
        data = {}
        for k, v in rows:
            try:
                data[k] = json.loads(v)
            except json.JSONDecodeError:
                continue
        return Settings.from_dict(data)

    def save_settings(self, settings: Settings) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                [(k, json.dumps(v)) for k, v in settings.to_dict().items()],
            )

    # pinned
    def list_pinned(self, kind: str) -> list[PinnedItem]:
        rows = self._conn.execute(
            "SELECT id, kind, label, path, position FROM pinned_items WHERE kind=? "
            "ORDER BY position, id",
            (kind,),
        ).fetchall()
        return [PinnedItem(*r) for r in rows]

    def add_pinned(self, kind: str, label: str, path: str) -> PinnedItem | None:
        pos = self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM pinned_items WHERE kind=?", (kind,)
        ).fetchone()[0]
        try:
            with self._conn:
                cur = self._conn.execute(
                    "INSERT INTO pinned_items(kind, label, path, position) VALUES(?,?,?,?)",
                    (kind, label, path, pos),
                )
        except sqlite3.IntegrityError:
            return None
        return PinnedItem(int(cur.lastrowid or 0), kind, label, path, pos)

    def remove_pinned(self, item_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM pinned_items WHERE id=?", (item_id,))

    def move_pinned(self, item_id: int, delta: int) -> None:
        row = self._conn.execute("SELECT kind FROM pinned_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return
        items = self.list_pinned(row[0])
        ids = [i.id for i in items]
        idx = ids.index(item_id)
        new = max(0, min(len(ids) - 1, idx + delta))
        ids.insert(new, ids.pop(idx))
        with self._conn:
            self._conn.executemany(
                "UPDATE pinned_items SET position=? WHERE id=?",
                [(p, i) for p, i in enumerate(ids)],
            )
