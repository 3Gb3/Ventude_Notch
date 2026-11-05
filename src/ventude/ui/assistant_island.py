from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QRect, QTimer
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ventude.core.config import Settings
from ventude.core.events import EventBus
from ventude.storage.database import Database
from ventude.ui.island_base import FloatingIsland


class AssistantIsland(FloatingIsland):
    def __init__(
        self, settings: Settings, db: Database, bus: EventBus, page_factory: Callable[[], QWidget]
    ) -> None:
        super().__init__(
            settings,
            db,
            bus,
            position_key="assistant_position_json",
            title="Ventude · IA",
            symbol="sparkles",
        )
        self.page = page_factory()
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.page)
        layout.addWidget(scroll)
        self.status_timer = QTimer(self, interval=600, timeout=self._update_status)
        self.status_timer.start()
        self._update_status()
        self.reposition()
        if not settings.assistant_position_json:
            self.save_position()
        # Companion island is opt-in; hover expand only applies while visible.
        self.hover_timer.setInterval(100)

    def _default_anchor(self, area: QRect) -> QPoint:
        # The companion sits to the side so the main dashboard can open independently.
        return QPoint(area.right() - 106, area.top() + self.settings.top_margin)

    def _sizes(self, expanded: bool) -> tuple[int, int]:
        return (680, 560) if expanded else (172, 46)

    def _update_status(self) -> None:
        self.clock.setText("Pensando…" if getattr(self.page, "busy", False) else "Ventude IA")

    def _keep_open(self) -> bool:
        return bool(getattr(self.page, "busy", False))

    def sync_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.reposition()
