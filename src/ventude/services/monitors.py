from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QScreen


def screens() -> list[QScreen]:
    return list(QGuiApplication.screens())


def screen_for(index: int) -> QScreen:
    all_s = screens()
    if 0 <= index < len(all_s):
        return all_s[index]
    return QGuiApplication.primaryScreen()


def top_center_rect(area: QRect, width: int, height: int, margin: int) -> QRect:
    x = area.x() + (area.width() - width) // 2
    return QRect(x, area.y() + margin, width, height)
