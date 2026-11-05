from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ventude.services.monitors import screens
from ventude.ui import themes


def make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(themes.BLACK))
    p.setPen(QColor(themes.GREEN))
    p.drawRoundedRect(4, 18, 56, 28, 14, 14)
    p.setBrush(QColor(themes.GREEN))
    p.drawEllipse(40, 26, 12, 12)
    p.end()
    return QIcon(pm)


class Tray(QSystemTrayIcon):
    def __init__(
        self,
        current_monitor: int,
        on_monitor: Callable[[int], None],
        on_toggle: Callable[[], None],
        on_quit: Callable[[], None],
        on_assistant: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(make_icon())
        self.setToolTip("Ventude")
        self.on_monitor = on_monitor
        menu = QMenu()
        menu.addAction("Mostrar/ocultar ilhas", on_toggle)
        if on_assistant:
            menu.addAction("Abrir IA", on_assistant)
        self.monitor_menu = menu.addMenu("Monitor")
        self.group = QActionGroup(self.monitor_menu)
        self.group.setExclusive(True)
        self.rebuild_monitors(current_monitor)
        menu.addSeparator()
        menu.addAction("Sair", on_quit)
        self._menu = menu
        self.setContextMenu(menu)

    def rebuild_monitors(self, current: int) -> None:
        self.monitor_menu.clear()
        for a in self.group.actions():
            self.group.removeAction(a)
        for i, s in enumerate(screens()):
            act = QAction(f"{i + 1}: {s.name()}", self.monitor_menu, checkable=True)
            act.setChecked(i == current)
            act.triggered.connect(lambda _=False, idx=i: self.on_monitor(idx))
            self.group.addAction(act)
            self.monitor_menu.addAction(act)
