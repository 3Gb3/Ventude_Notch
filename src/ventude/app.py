from __future__ import annotations

import json
import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel

from ventude.core.async_worker import AsyncWorker
from ventude.core.config import Settings
from ventude.core.events import EventBus
from ventude.core.logging import setup_logging
from ventude.core.paths import app_data_dir
from ventude.services.cache import Cache
from ventude.services.calendar_store import CalendarStore
from ventude.services.lists_store import ListsStore
from ventude.services.market import MarketService
from ventude.services.media import MediaService
from ventude.services.news import NewsService
from ventude.services.weather import WeatherService
from ventude.storage.database import Database
from ventude.ui import themes
from ventude.ui.assistant_island import AssistantIsland
from ventude.ui.fonts import load_fonts
from ventude.ui.notch import IslandWindow
from ventude.ui.pages.home import HomePage
from ventude.ui.tray import Tray

log = logging.getLogger(__name__)


def run() -> int:
    setup_logging()
    # Qt 6 já é per-monitor DPI aware; mantém fatores fracionários sem arredondar.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Ventude")
    app.setOrganizationName("Ventude")
    app.setQuitOnLastWindowClosed(False)
    load_fonts()
    app.setStyleSheet(themes.STYLESHEET)

    data = app_data_dir()
    db = Database(data / "ventude.db")
    settings = db.load_settings()
    bus = EventBus()
    media = MediaService()
    worker = AsyncWorker()
    cache = Cache(data / "cache.db")
    weather = WeatherService(cache)
    news = NewsService(cache)
    market = MarketService(cache)
    calendar_store = CalendarStore(data / "calendar.db")
    lists_store = ListsStore(data / "lists.db")
    holder: dict[str, IslandWindow] = {}
    pages: list = []
    ai_wanted = False

    def assistant_page():  # criado dentro da ilha, na thread da UI
        from ventude.assistant.service import AssistantService
        from ventude.ui.pages.assistant_page import AssistantPage

        def factory(approver):
            return AssistantService(
                data,
                db,
                lambda: Settings.from_dict(holder["island"].settings.to_dict()),
                bus.apply_settings_requested.emit,
                bus.pinned_changed.emit,
                approver,
            )

        try:
            page = AssistantPage(factory, worker, bus)
        except Exception:
            log.exception("Falha ao iniciar o assistente")
            message = QLabel("Não foi possível abrir a IA. Consulte o log do Ventude.")
            message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return message
        pages.append(page)
        return page

    def weather_city_get():
        raw = (
            holder["island"].settings.weather_city_json
            if "island" in holder
            else settings.weather_city_json
        )
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def weather_city_set(payload: dict) -> None:
        isl = holder["island"]
        isl.settings.weather_city_json = json.dumps(payload, ensure_ascii=False)
        db.save_settings(isl.settings)
        isl.home.refresh_weather()

    def make_widgets():
        from ventude.ui.pages.calendar_page import CalendarPage
        from ventude.ui.pages.lists_page import ListsPage
        from ventude.ui.pages.market_page import MarketPage
        from ventude.ui.pages.news_page import NewsPage
        from ventude.ui.pages.weather_page import WeatherPage

        return {
            "Clima": lambda: WeatherPage(weather, worker, weather_city_get, weather_city_set),
            "Calendário": lambda: CalendarPage(calendar_store),
            "Notícias": lambda: NewsPage(news, worker),
            "Mercado": lambda: MarketPage(market, worker),
            "Listas": lambda: ListsPage(lists_store, bus),
        }

    island = IslandWindow(
        settings,
        db,
        bus,
        media,
        widgets=make_widgets(),
        home_factory=lambda: HomePage(
            media,
            settings.clock_24h,
            weather=weather,
            worker=worker,
            city_get=weather_city_get,
            city_set=weather_city_set,
            calendar_store=calendar_store,
            market=market,
            news=news,
            db=db,
        ),
    )
    holder["island"] = island
    assistant = AssistantIsland(settings, db, bus, assistant_page)
    # AI panel starts hidden — toggled from the main notch tools strip.
    assistant.hide()
    island.set_assistant_visible(False)
    media.start()

    def set_ai_visible(visible: bool) -> None:
        nonlocal ai_wanted
        ai_wanted = visible
        if visible:
            assistant.reveal()
        else:
            assistant.hide()
        island.set_assistant_visible(visible)

    def toggle_assistant() -> None:
        set_ai_visible(not assistant.isVisible())

    island.assistant_toggled.connect(toggle_assistant)
    island.settings_updated.connect(assistant.sync_settings)

    def quit_app() -> None:
        db.save_settings(island.settings)
        app.exit(0)

    def toggle_islands() -> None:
        visible = not island.isVisible()
        island.setVisible(visible)
        if visible and ai_wanted:
            assistant.show()
        else:
            assistant.hide()

    def reset_positions() -> None:
        island.settings.island_position_json = ""
        island.settings.assistant_position_json = ""
        db.save_settings(island.settings)
        island.settings_page.sync(island.settings)
        island.reposition()
        assistant.reposition()
        assistant.save_position()

    island.quit_requested.connect(quit_app)
    island.reset_positions_requested.connect(reset_positions)
    tray = Tray(
        settings.monitor_index, island.set_monitor, toggle_islands, quit_app, toggle_assistant
    )
    bus.monitor_changed.connect(tray.rebuild_monitors)

    def screens_changed(*_: object) -> None:
        tray.rebuild_monitors(island.settings.monitor_index)
        # Se o índice ficou inválido, volta ao monitor principal.
        from ventude.services.monitors import screens

        if island.settings.monitor_index >= len(screens()):
            island.set_monitor(0)
        else:
            island.reposition()
        assistant.reposition()
        island.settings_page.sync(island.settings)

    def screen_geometry_changed(*_: object) -> None:
        island.reposition()
        assistant.reposition()

    def connect_screen(screen) -> None:
        screen.geometryChanged.connect(screen_geometry_changed)
        screen.availableGeometryChanged.connect(screen_geometry_changed)

    app.screenAdded.connect(connect_screen)
    app.screenAdded.connect(screens_changed)
    app.screenRemoved.connect(screens_changed)
    for screen in app.screens():
        connect_screen(screen)
    tray.show()
    island.show()
    log.info("Ventude iniciado")
    code = app.exec()
    media.stop()
    for p in pages:
        p.shutdown()
    for svc in (weather, news, market):
        try:
            worker.submit(svc.close()).result(timeout=3)
        except Exception:  # noqa: BLE001
            log.debug("close de serviço falhou", exc_info=True)
    cache.close()
    calendar_store.close()
    lists_store.close()
    worker.stop()
    db.close()
    return code
