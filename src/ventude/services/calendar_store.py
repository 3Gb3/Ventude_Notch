"""Calendário local (SQLite). Sem integração externa obrigatória."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path


@dataclass(frozen=True)
class CalendarEvent:
    id: int
    title: str
    day: date
    start: time | None
    end: time | None
    notes: str = ""

    @property
    def when(self) -> str:
        if self.start and self.end:
            return f"{self.start.strftime('%H:%M')}–{self.end.strftime('%H:%M')}"
        if self.start:
            return self.start.strftime("%H:%M")
        return "Dia inteiro"


class CalendarStore:
    def __init__(self, path: Path) -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "title TEXT NOT NULL, day TEXT NOT NULL,"
            "start TEXT, end TEXT, notes TEXT DEFAULT '')"
        )
        self.conn.commit()

    def add(
        self,
        title: str,
        day: date,
        start: time | None = None,
        end: time | None = None,
        notes: str = "",
    ) -> CalendarEvent:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO events(title, day, start, end, notes) VALUES(?,?,?,?,?)",
                (
                    title.strip(),
                    day.isoformat(),
                    start.isoformat(timespec="minutes") if start else None,
                    end.isoformat(timespec="minutes") if end else None,
                    notes,
                ),
            )
        return CalendarEvent(int(cur.lastrowid or 0), title.strip(), day, start, end, notes)

    def remove(self, event_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM events WHERE id=?", (event_id,))

    def for_day(self, day: date) -> list[CalendarEvent]:
        rows = self.conn.execute(
            "SELECT id, title, day, start, end, notes FROM events WHERE day=? "
            "ORDER BY start IS NOT NULL, start",
            (day.isoformat(),),
        ).fetchall()
        return [self._row(r) for r in rows]

    def upcoming(self, from_day: date | None = None, days: int = 14) -> list[CalendarEvent]:
        start = from_day or date.today()
        end = start + timedelta(days=days)
        rows = self.conn.execute(
            "SELECT id, title, day, start, end, notes FROM events "
            "WHERE day>=? AND day<? ORDER BY day, start IS NOT NULL, start",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row(r) for r in rows]

    def month_days_with_events(self, year: int, month: int) -> set[int]:
        prefix = f"{year:04d}-{month:02d}-"
        rows = self.conn.execute(
            "SELECT DISTINCT day FROM events WHERE day LIKE ?", (prefix + "%",)
        ).fetchall()
        return {int(d[0][8:10]) for d in rows}

    @staticmethod
    def _row(r: tuple) -> CalendarEvent:
        start = time.fromisoformat(r[3]) if r[3] else None
        end = time.fromisoformat(r[4]) if r[4] else None
        return CalendarEvent(r[0], r[1], date.fromisoformat(r[2]), start, end, r[5] or "")

    def close(self) -> None:
        self.conn.close()


def parse_time(text: str) -> time | None:
    text = text.strip()
    if not text:
        return None
    return datetime.strptime(text, "%H:%M").time()
