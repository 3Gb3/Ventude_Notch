"""Listas personalizadas (tarefas/itens) em SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ListItem:
    id: int
    list_id: int
    text: str
    done: bool
    position: int


@dataclass(frozen=True)
class TodoList:
    id: int
    name: str


class ListsStore:
    def __init__(self, path: Path) -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(list_id) REFERENCES lists(id) ON DELETE CASCADE);
            """
        )
        self.conn.commit()
        if not self.lists():
            self.add_list("Geral")

    def lists(self) -> list[TodoList]:
        return [
            TodoList(r[0], r[1])
            for r in self.conn.execute("SELECT id, name FROM lists ORDER BY id").fetchall()
        ]

    def add_list(self, name: str) -> TodoList:
        with self.conn:
            cur = self.conn.execute("INSERT INTO lists(name) VALUES(?)", (name.strip(),))
        return TodoList(int(cur.lastrowid or 0), name.strip())

    def remove_list(self, list_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM list_items WHERE list_id=?", (list_id,))
            self.conn.execute("DELETE FROM lists WHERE id=?", (list_id,))
        if not self.lists():
            self.add_list("Geral")

    def items(self, list_id: int) -> list[ListItem]:
        rows = self.conn.execute(
            "SELECT id, list_id, text, done, position FROM list_items "
            "WHERE list_id=? ORDER BY done, position, id",
            (list_id,),
        ).fetchall()
        return [ListItem(r[0], r[1], r[2], bool(r[3]), r[4]) for r in rows]

    def add_item(self, list_id: int, text: str) -> ListItem:
        pos = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1)+1 FROM list_items WHERE list_id=?",
            (list_id,),
        ).fetchone()[0]
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO list_items(list_id, text, position) VALUES(?,?,?)",
                (list_id, text.strip(), pos),
            )
        return ListItem(int(cur.lastrowid or 0), list_id, text.strip(), False, pos)

    def toggle(self, item_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE list_items SET done = CASE done WHEN 0 THEN 1 ELSE 0 END WHERE id=?",
                (item_id,),
            )

    def remove_item(self, item_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM list_items WHERE id=?", (item_id,))

    def close(self) -> None:
        self.conn.close()
