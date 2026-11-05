from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QDateTime, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ventude.core.config import Settings
from ventude.core.events import EventBus
from ventude.services.media import MediaService, MediaState
from ventude.storage.database import Database
from ventude.ui import themes
from ventude.ui.icons import icon, icon_button
from ventude.ui.island_base import FloatingIsland
from ventude.ui.pages.home import HomePage
from ventude.ui.pages.pinned import PinnedPage
from ventude.ui.pages.placeholder import PlaceholderPage
from ventude.ui.pages.settings_page import SettingsPage
from ventude.ui.tools_bar import ToolsBar, ToolsController

TABS = [
    ("Início", "home"),
    ("Aplicativos", "apps"),
    ("Pastas", "folder"),
    ("Clima", "sun"),
    ("Calendário", "calendar"),
    ("Notícias", "news"),
    ("Mercado", "chart"),
    ("Listas", "check"),
    ("Configurações", "settings"),
]


class IslandWindow(FloatingIsland):
    assistant_toggled = Signal()
    settings_updated = Signal(object)
    quit_requested = Signal()
    reset_positions_requested = Signal()

    def __init__(
        self,
        settings: Settings,
        db: Database,
        bus: EventBus,
        media: MediaService,
        *,
        widgets: dict[str, Callable[[], QWidget]] | None = None,
        home_factory: Callable[[], HomePage] | None = None,
    ) -> None:
        super().__init__(
            settings, db, bus, position_key="island_position_json", title="Ventude", symbol="apps"
        )
        self.media, self.media_state = media, None
        self._widgets = widgets or {}
        self.pinned_pages: list[PinnedPage] = []
        self.tools = ToolsController(self)
        self.tools.assistant_toggle.connect(self.assistant_toggled)
        self.tools_bar = ToolsBar(self.tools, self)
        self.tools_layout.addWidget(self.tools_bar)
        self._build(home_factory)
        media.state_changed.connect(self._on_media)
        bus.pinned_changed.connect(lambda: [p.reload() for p in self.pinned_pages])
        bus.apply_settings_requested.connect(self._settings_changed)
        bus.monitor_changed.connect(self.settings_page.set_monitor)
        self.clock_timer = QTimer(self, interval=1000, timeout=self._update_clock)
        self.clock_timer.start()
        self._update_clock()
        self.reposition()

    def _build(self, home_factory: Callable[[], HomePage] | None) -> None:
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        tabs = QHBoxLayout()
        tabs.setSpacing(4)
        tabs.addStretch()
        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.settings_page = SettingsPage(self.settings, self._settings_changed)
        self.settings_page.quit_requested.connect(self.quit_requested)
        self.settings_page.reset_positions_requested.connect(self.reset_positions_requested)
        for index, (name, symbol) in enumerate(TABS):
            button = icon_button(symbol, name, 36)
            button.setObjectName("Tab")
            button.setCheckable(True)
            self.group.addButton(button, index)
            tabs.addWidget(button)
            if name == "Início":
                page = (
                    home_factory()
                    if home_factory
                    else HomePage(self.media, self.settings.clock_24h)
                )
                self.home = page
                page.navigate_requested.connect(self.navigate)
            elif name in ("Aplicativos", "Pastas"):
                page = PinnedPage("app" if name == "Aplicativos" else "folder", self.db, self.bus)
                self.pinned_pages.append(page)
            elif name == "Configurações":
                page = self.settings_page
            elif name in self._widgets:
                try:
                    page = self._widgets[name]()
                except Exception:
                    logging.getLogger(__name__).exception("Widget %s falhou", name)
                    page = PlaceholderPage(name, "erro ao iniciar; veja o log")
            else:
                page = PlaceholderPage(name, "")
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        tabs.addStretch()
        self.group.idClicked.connect(self._select_page)
        self._select_page(0)
        layout.addLayout(tabs)
        layout.addWidget(self.stack, 1)

    def set_assistant_visible(self, visible: bool) -> None:
        self.tools_bar.set_ai_checked(visible)

    def _select_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, (_, symbol) in enumerate(TABS):
            btn = self.group.button(i)
            btn.setChecked(i == index)
            btn.setIcon(icon(symbol, themes.GREEN if i == index else themes.TEXT_MUTED))
        if index == 0:
            self.home.refresh()

    def navigate(self, name: str) -> None:
        for index, (label, _) in enumerate(TABS):
            if label == name:
                self.animate_to(True)
                self._select_page(index)
                return

    def animate_to(self, expanded: bool) -> None:
        if expanded and not self.expanded and not self._dragging:
            self._select_page(0)
        super().animate_to(expanded)
        self._update_clock()

    def _sizes(self, expanded: bool) -> tuple[int, int]:
        s = self.settings
        if expanded:
            return max(700, s.expanded_width), max(440, s.expanded_height)
        # Compact bar needs room for utility icons + clock/media.
        base = s.compact_media_width if self._showing_track() else max(280, s.compact_width)
        return base, max(44, s.compact_height)

    def _showing_track(self) -> bool:
        return self.media_state is not None and self.media_state.is_playing

    def compact_text(self) -> str:
        fmt = "HH:mm" if self.settings.clock_24h else "h:mm AP"
        time = QDateTime.currentDateTime().toString(fmt)
        if self._showing_track() and self.media_state and not self.expanded:
            title = self.clock.fontMetrics().elidedText(
                self.media_state.title,
                Qt.TextElideMode.ElideRight,
                max(72, self.settings.compact_media_width - 200),
            )
            return f"{title}   ·   {time}"
        return time

    def _update_clock(self) -> None:
        self.clock.setText("Ventude" if self.expanded else self.compact_text())
        self.mark.setPixmap(
            icon("music" if self._showing_track() else "apps", themes.GREEN, 18).pixmap(18, 18)
        )

    def _on_media(self, state: MediaState | None) -> None:
        was = self._showing_track()
        self.media_state = state
        self._update_clock()
        if was != self._showing_track() and not self.expanded:
            self.animate_to(False)

    def _settings_changed(self, settings: Settings) -> None:
        changed_monitor = settings.monitor_index != self.settings.monitor_index
        if changed_monitor:
            settings.island_position_json = ""
        self.settings = settings
        self.db.save_settings(settings)
        self.settings_page.sync(settings)
        self.home.clock_24h = settings.clock_24h
        self.home.refresh()
        self._update_clock()
        self.settings_updated.emit(settings)
        if changed_monitor:
            self.bus.monitor_changed.emit(settings.monitor_index)
        self.reposition()

    def set_monitor(self, index: int) -> None:
        settings = Settings.from_dict(self.settings.to_dict())
        settings.monitor_index = index
        settings.island_position_json = ""
        self._settings_changed(settings)

    def _keep_open(self) -> bool:
        return self.tools._overlay is not None

    def toggle_visible(self) -> None:
        self.setVisible(not self.isVisible())
