from __future__ import annotations

import json
import sqlite3
import time

from ventude.assistant.types import ChatMessage


class ChatHistory:
    """Histórico local do chat em SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL, title TEXT);
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER,
                ts REAL, role TEXT, text TEXT, images TEXT);
            """
        )
        conn.commit()

    def new_conversation(self, title: str = "") -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO conversations(created, title) VALUES(?,?)", (time.time(), title)
            )
        return int(cur.lastrowid or 0)

    def latest_conversation(self) -> int | None:
        row = self.conn.execute("SELECT MAX(id) FROM conversations").fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def conversations(self) -> list[tuple[int, str]]:
        return self.conn.execute(
            "SELECT id, COALESCE(NULLIF(title,''), 'Nova conversa') "
            "FROM conversations ORDER BY id DESC"
        ).fetchall()

    def exists(self, conversation_id: int) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM conversations WHERE id=?", (conversation_id,)
        ).fetchone() is not None

    def add(self, conversation_id: int, msg: ChatMessage) -> None:
        # Imagens não são persistidas (só a contagem), para não inchar o banco.
        with self.conn:
            if msg.role == "user" and msg.text.strip():
                title = " ".join(msg.text.split())[:60]
                self.conn.execute(
                    "UPDATE conversations SET title=? WHERE id=? AND (title='' OR title IS NULL)",
                    (title, conversation_id),
                )
            self.conn.execute(
                "INSERT INTO chat_messages(conversation_id, ts, role, text, images)"
                " VALUES(?,?,?,?,?)",
                (conversation_id, time.time(), msg.role, msg.text, json.dumps(len(msg.images))),
            )

    def messages(self, conversation_id: int) -> list[ChatMessage]:
        rows = self.conn.execute(
            "SELECT role, text FROM chat_messages WHERE conversation_id=? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [ChatMessage(r, t) for r, t in rows]

    def clear(self, conversation_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM chat_messages WHERE conversation_id=?", (conversation_id,)
            )
