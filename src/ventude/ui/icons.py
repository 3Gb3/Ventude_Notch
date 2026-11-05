"""Small, consistent vector icons. No font glyphs or downloaded assets are required."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton

from ventude.ui import themes

_PATHS = {
    "home": '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
    "apps": '<rect x="3" y="3" width="7" height="7" rx="2"/>'
    '<rect x="14" y="3" width="7" height="7" rx="2"/>'
    '<rect x="3" y="14" width="7" height="7" rx="2"/>'
    '<rect x="14" y="14" width="7" height="7" rx="2"/>',
    "folder": '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5'
    'a2 2 0 0 1-2-2V7Z"/>',
    "sparkles": '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>'
    '<path d="M20 2v4m-2-2h4M4 18v4m-2-2h4"/>',
    "sun": '<circle cx="12" cy="12" r="4"/>'
    '<path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19'
    'M5 19l1.5-1.5m11-11L19 5"/>',
    "moon": '<path d="M20.8 13.5A9 9 0 0 1 10.5 3.2 9 9 0 1 0 20.8 13.5Z"/>',
    "cloud": '<path d="M6 18a4 4 0 1 1 .2-8A6 6 0 0 1 18 8a5 5 0 0 1 0 10Z"/>',
    "cloud-sun": '<path d="M12 7a4 4 0 1 0-6 4M8 1v2M1 8h2m-.5-5.5L4 4m9-1.5L11.5 4"/>'
    '<path d="M8 21a4 4 0 1 1 .2-8A5 5 0 0 1 18 12a4.5 4.5 0 0 1 0 9Z"/>',
    "cloud-rain": '<path d="M6 15a4 4 0 1 1 .2-8A6 6 0 0 1 18 5a5 5 0 0 1 0 10"/>'
    '<path d="m8 17-1 3m6-3-1 3m6-3-1 3"/>',
    "snow": '<path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M9 4l3 3 3-3'
    'M9 20l3-3 3 3M3 10l4-1-1-4m12 14-1-4 4-1M3 14l4 1-1 4m12-14-1 4 4 1"/>',
    "storm": '<path d="M6 15a4 4 0 1 1 .2-8A6 6 0 0 1 18 5a5 5 0 0 1 0 10"/>'
    '<path d="m13 12-4 6h5l-3 5"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="3"/>'
    '<path d="M7 3v4m10-4v4M3 11h18m-14 4h2m4 0h2m-8 3h2"/>',
    "news": '<rect x="3" y="3" width="18" height="18" rx="3"/>'
    '<path d="M7 7h10M7 11h4v6H7Zm8 0h2m-2 3h2m-2 3h2"/>',
    "chart": '<path d="M3 3v18h18M7 15l5-5 4 3 5-7m-5 0h5v5"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "settings": '<path d="m9 3-1 3-3 1-2 3 2 2-1 3 2 3 3-1 3 2 3-2 3 1 2-3-1-3 2-2-2-3-3-1-1-3Z"/>'
    '<circle cx="12" cy="11" r="3"/>',
    "grip": '<path d="M8 5h.01M16 5h.01M8 12h.01M16 12h.01M8 19h.01M16 19h.01" '
    'stroke-width="3.5"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "close": '<path d="m6 6 12 12M6 18 18 6"/>',
    "power": '<path d="M12 2v10m-6-7a9 9 0 1 0 12 0"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "arrow-left": '<path d="m12 5-7 7 7 7M5 12h15"/>',
    "arrow-right": '<path d="m12 5 7 7-7 7M19 12H4"/>',
    "play": '<path d="m8 4 12 8-12 8Z"/>',
    "pause": '<path d="M8 4v16M16 4v16" stroke-width="3.5"/>',
    "skip-back": '<path d="M5 5v14m14-14-11 7 11 7Z"/>',
    "skip-forward": '<path d="M19 5v14M5 5l11 7-11 7Z"/>',
    "music": '<path d="M9 18V5l11-2v13M9 8l11-2"/>'
    '<ellipse cx="6" cy="18" rx="3" ry="3"/><ellipse cx="17" cy="16" rx="3" ry="3"/>',
    "volume": '<path d="m11 4-6 5H2v6h3l6 5Zm4 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
    "search": '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
    "send": '<path d="m3 3 19 9-19 9 4-9Zm4 9h15"/>',
    "trash": '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    "refresh": '<path d="M20 7a9 9 0 0 0-15-2L2 8m0-6v6h6M4 17a9 9 0 0 0 15 2l3-3'
    'm0 6v-6h-6"/>',
    "pin": '<path d="m8 3 9 9m-6-6 4-4 7 7-4 4-1 6-6-6-6-1 6-6ZM9 15l-6 6"/>',
    "paperclip": '<path d="m8 12 8-8a4 4 0 0 1 6 6L11 21a6 6 0 0 1-8-8L14 2'
    'm-6 10 8-8a2 2 0 0 1 3 3L8 18a2 2 0 0 1-3-3l9-9"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="3"/>',
    "key": '<circle cx="8" cy="8" r="5"/><path d="m12 12 9 9m-5-5 3-3m-6 0 3-3"/>',
    "history": '<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v6l4 2"/>',
}


@lru_cache(maxsize=256)
def icon(name: str, color: str | None = None, size: int = 20) -> QIcon:
    """Render at double resolution so icons stay crisp on Windows display scaling."""
    color = color or themes.TEXT_MUTED
    path = _PATHS.get(name, _PATHS["sparkles"])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    )
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def icon_button(name: str, tooltip: str, size: int = 36) -> QPushButton:
    button = QPushButton()
    button.setObjectName("IconButton")
    button.setIcon(icon(name))
    button.setIconSize(QSize(20, 20))
    button.setFixedSize(size, size)
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def weather_icon(code: int) -> str:
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "cloud-sun"
    if code in (3, 45, 48):
        return "cloud"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloud-rain" if code in range(51, 83) else "cloud"
