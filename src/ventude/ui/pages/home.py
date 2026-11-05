from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from PySide6.QtCore import QDateTime, QLocale, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ventude.core.async_worker import AsyncWorker
from ventude.services.calendar_store import CalendarStore
from ventude.services.launcher import open_path, validate_path
from ventude.services.market import Quote
from ventude.services.media import MediaService
from ventude.services.news import NewsItem
from ventude.services.weather import Place, WeatherNow, WeatherService
from ventude.storage.database import Database
from ventude.ui import themes
from ventude.ui.fonts import display_font, ui_font
from ventude.ui.icons import icon, icon_button, weather_icon
from ventude.ui.media_card import MediaCard


class _Bridge(QObject):
    weather_loaded = Signal(int, object)
    weather_failed = Signal(int)
    located = Signal(object)
    quotes = Signal(list)
    news = Signal(list)


def _glass_card() -> tuple[QWidget, QVBoxLayout]:
    card = QWidget()
    card.setObjectName("Card")
    card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    return card, layout


def _pill() -> tuple[QWidget, QHBoxLayout]:
    pill = QWidget()
    pill.setObjectName("GlassPill")
    pill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    layout = QHBoxLayout(pill)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(8)
    return pill, layout


class HomePage(QWidget):
    """Glass Crystal dashboard: date, weather, media, finance, AI ask, news, docks."""

    navigate_requested = Signal(str)
    assistant_requested = Signal()

    def __init__(
        self,
        media: MediaService,
        clock_24h: bool = True,
        *,
        weather: WeatherService | None = None,
        worker: AsyncWorker | None = None,
        city_get: Callable[[], dict[str, Any] | None] | None = None,
        city_set: Callable[[dict[str, Any]], None] | None = None,
        calendar_store: CalendarStore | None = None,
        market: Any | None = None,
        news: Any | None = None,
        db: Database | None = None,
    ) -> None:
        super().__init__()
        self.clock_24h = clock_24h
        self.weather, self.worker = weather, worker
        self.city_get, self.city_set = city_get, city_set
        self.calendar_store = calendar_store
        self.market, self.news_service, self.db = market, news, db
        self.locale = QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
        self._calendar_date: date | None = None
        self._weather_generation = 0
        self._weather_key: tuple[float, float] | None = None
        self._weather_pending = False
        self._locating = False
        self._weather_name = "Local"
        self._weather_description = "Detectando localização…"
        self.weather_state: WeatherNow | None = None
        self.bridge = _Bridge(self)
        self.bridge.weather_loaded.connect(self._show_weather)
        self.bridge.weather_failed.connect(self._weather_error)
        self.bridge.located.connect(self._on_located)
        self.bridge.quotes.connect(self._show_quotes)
        self.bridge.news.connect(self._show_news)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # --- Hero: date + weather ---
        hero = QHBoxLayout()
        hero.setSpacing(10)
        date_card, date_lay = _glass_card()
        self.hero_date = QLabel()
        self.hero_date.setObjectName("HeroDate")
        self.hero_date.setFont(display_font(22, QFont.Weight.Bold))
        self.hero_clock = QLabel()
        self.hero_clock.setObjectName("Muted")
        self.hero_clock.setFont(ui_font(12))
        date_lay.addWidget(self.hero_date)
        date_lay.addWidget(self.hero_clock)
        hero.addWidget(date_card, 3)

        weather_card, weather_lay = _glass_card()
        weather_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        wrow = QHBoxLayout()
        wrow.setSpacing(8)
        self.weather_symbol = QLabel()
        self.weather_symbol.setFixedSize(28, 28)
        self.weather_symbol.setPixmap(icon("cloud-sun", themes.SIGNAL_WARM, 24).pixmap(24, 24))
        self.temperature = QLabel("—°")
        self.temperature.setFont(display_font(26, QFont.Weight.Bold))
        self.city = QLabel("Detectando…")
        self.city.setObjectName("Muted")
        self.city.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        wrow.addWidget(self.weather_symbol)
        wrow.addWidget(self.temperature)
        wcol = QVBoxLayout()
        wcol.setSpacing(0)
        self.weather_detail = QLabel("Localização automática")
        self.weather_detail.setObjectName("Faint")
        wcol.addWidget(self.city)
        wcol.addWidget(self.weather_detail)
        wrow.addLayout(wcol, 1)
        self.weather_action = icon_button("arrow-right", "Abrir clima", 28)
        self.weather_action.clicked.connect(lambda: self.navigate_requested.emit("Clima"))
        wrow.addWidget(self.weather_action)
        weather_lay.addLayout(wrow)
        hero.addWidget(weather_card, 2)
        root.addLayout(hero)

        # --- Calendar strip ---
        cal_card, cal_lay = _glass_card()
        cal_lay.setSpacing(6)
        chead = QHBoxLayout()
        self.calendar_month = QLabel()
        self.calendar_month.setObjectName("Section")
        chead.addWidget(self.calendar_month, 1)
        self.calendar_action = icon_button("arrow-right", "Abrir calendário", 26)
        self.calendar_action.clicked.connect(lambda: self.navigate_requested.emit("Calendário"))
        chead.addWidget(self.calendar_action)
        cal_lay.addLayout(chead)
        week = QHBoxLayout()
        week.setSpacing(4)
        self.week_labels: list[tuple[QLabel, QLabel]] = []
        for _ in range(7):
            day_pill = QWidget()
            day_pill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
            col = QVBoxLayout(day_pill)
            col.setContentsMargins(4, 6, 4, 6)
            col.setSpacing(2)
            day_name = QLabel()
            day_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            day_name.setObjectName("Faint")
            day_number = QLabel()
            day_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            day_number.setFont(display_font(13, QFont.Weight.DemiBold))
            col.addWidget(day_name)
            col.addWidget(day_number)
            week.addWidget(day_pill, 1)
            self.week_labels.append((day_name, day_number))
            day_name.setProperty("pill", day_pill)
            day_number.setProperty("pill", day_pill)
        cal_lay.addLayout(week)
        self.next_event = QLabel("Agenda livre")
        self.next_event.setFont(ui_font(12, QFont.Weight.DemiBold))
        self.event_time = QLabel()
        self.event_time.setObjectName("Muted")
        cal_lay.addWidget(self.next_event)
        cal_lay.addWidget(self.event_time)
        root.addWidget(cal_card)

        # --- Media + finance + appearance ---
        mid = QHBoxLayout()
        mid.setSpacing(10)
        self.media_card = MediaCard(media)
        mid.addWidget(self.media_card, 3)

        finance_card, finance_lay = _glass_card()
        fin_title = QLabel("Mercado")
        fin_title.setObjectName("Section")
        finance_lay.addWidget(fin_title)
        self.quote_rows: list[tuple[QLabel, QLabel, QLabel]] = []
        for _ in range(3):
            pill, prow = _pill()
            name = QLabel("—")
            name.setFont(ui_font(12, QFont.Weight.DemiBold))
            change = QLabel("")
            change.setObjectName("Muted")
            price = QLabel("")
            price.setAlignment(Qt.AlignmentFlag.AlignRight)
            prow.addWidget(name)
            prow.addWidget(change, 1)
            prow.addWidget(price)
            finance_lay.addWidget(pill)
            self.quote_rows.append((name, change, price))
        market_go = icon_button("arrow-right", "Abrir mercado", 26)
        market_go.clicked.connect(lambda: self.navigate_requested.emit("Mercado"))
        finance_lay.addWidget(market_go, 0, Qt.AlignmentFlag.AlignRight)
        mid.addWidget(finance_card, 2)

        appear_card, appear_lay = _glass_card()
        appear_title = QLabel("Aparência")
        appear_title.setObjectName("Section")
        appear_lay.addWidget(appear_title)
        swatches = QHBoxLayout()
        swatches.setSpacing(8)
        for color in ("#FFFFFF", "#D8F5E3", "#1DB954"):
            sw = QFrame()
            sw.setFixedSize(22, 22)
            sw.setStyleSheet(
                f"background:{color}; border:1px solid {themes.GLASS_EDGE}; border-radius:11px;"
            )
            swatches.addWidget(sw)
        swatches.addStretch()
        appear_lay.addLayout(swatches)
        theme_name = QLabel("Glass / Crystal")
        theme_name.setFont(display_font(14, QFont.Weight.DemiBold))
        theme_desc = QLabel("Translúcido, fosco e sofisticado")
        theme_desc.setObjectName("Muted")
        theme_desc.setWordWrap(True)
        active = QLabel()
        active.setPixmap(icon("check", themes.GREEN, 16).pixmap(16, 16))
        active_row = QHBoxLayout()
        active_row.addWidget(theme_name, 1)
        active_row.addWidget(active)
        appear_lay.addLayout(active_row)
        appear_lay.addWidget(theme_desc)
        appear_lay.addStretch(1)
        mid.addWidget(appear_card, 2)
        root.addLayout(mid)

        # --- Ask AI pill ---
        ask = QPushButton("Pergunte à IA")
        ask.setObjectName("AskAI")
        ask.setCursor(Qt.CursorShape.PointingHandCursor)
        ask.setIcon(icon("sparkles", themes.GREEN))
        ask.setMinimumHeight(44)
        ask.clicked.connect(self.assistant_requested.emit)
        ask_row = QHBoxLayout()
        ask_row.addWidget(ask, 1)
        mic = icon_button("mic", "Entrada por voz (em breve)", 40)
        mic.clicked.connect(self.assistant_requested.emit)
        ask_row.addWidget(mic)
        root.addLayout(ask_row)

        # --- News ---
        news_card, news_lay = _glass_card()
        nhead = QHBoxLayout()
        ntitle = QLabel("Notícias")
        ntitle.setObjectName("Section")
        nhead.addWidget(ntitle, 1)
        news_go = icon_button("arrow-right", "Abrir notícias", 26)
        news_go.clicked.connect(lambda: self.navigate_requested.emit("Notícias"))
        nhead.addWidget(news_go)
        news_lay.addLayout(nhead)
        self.news_labels: list[QLabel] = []
        for _ in range(3):
            item = QLabel("Carregando…")
            item.setObjectName("Muted")
            item.setWordWrap(True)
            item.setTextFormat(Qt.TextFormat.PlainText)
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            news_lay.addWidget(item)
            self.news_labels.append(item)
        root.addWidget(news_card)

        # --- Dock: apps + folders ---
        dock_card, dock_lay = _glass_card()
        dock_lay.setSpacing(8)
        apps_head = QHBoxLayout()
        apps_title = QLabel()
        apps_title.setPixmap(icon("pin", themes.TEXT_MUTED, 14).pixmap(14, 14))
        apps_label = QLabel("Apps fixos")
        apps_label.setObjectName("Section")
        apps_head.addWidget(apps_title)
        apps_head.addWidget(apps_label, 1)
        apps_go = icon_button("plus", "Gerenciar aplicativos", 26)
        apps_go.clicked.connect(lambda: self.navigate_requested.emit("Aplicativos"))
        apps_head.addWidget(apps_go)
        dock_lay.addLayout(apps_head)
        self.apps_row = QHBoxLayout()
        self.apps_row.setSpacing(6)
        dock_lay.addLayout(self.apps_row)
        folders_head = QHBoxLayout()
        folders_label = QLabel("Pastas")
        folders_label.setObjectName("Section")
        folders_head.addWidget(folders_label, 1)
        folders_go = icon_button("plus", "Gerenciar pastas", 26)
        folders_go.clicked.connect(lambda: self.navigate_requested.emit("Pastas"))
        folders_head.addWidget(folders_go)
        dock_lay.addLayout(folders_head)
        self.folders_row = QHBoxLayout()
        self.folders_row.setSpacing(6)
        dock_lay.addLayout(self.folders_row)
        root.addWidget(dock_card)

        self._timer = QTimer(self, interval=1000, timeout=self.refresh)
        self._timer.start()
        self._agenda_timer = QTimer(self, interval=30_000, timeout=self.refresh_calendar)
        self._agenda_timer.start()
        self._weather_timer = QTimer(self, interval=30 * 60_000)
        self._weather_timer.timeout.connect(lambda: self.refresh_weather(force=True))
        self._weather_timer.start()
        self._market_timer = QTimer(self, interval=10 * 60_000, timeout=self.refresh_market)
        self._market_timer.start()
        self._news_timer = QTimer(self, interval=15 * 60_000, timeout=self.refresh_news)
        self._news_timer.start()
        self.refresh()
        self.refresh_weather()
        self.refresh_market()
        self.refresh_news()
        self.reload_pins()

    def refresh(self) -> None:
        now = QDateTime.currentDateTime()
        self.hero_date.setText(self.locale.toString(now.date(), "dddd, d 'de' MMMM").capitalize())
        fmt = "HH:mm" if self.clock_24h else "h:mm AP"
        self.hero_clock.setText(now.toString(fmt))
        if self._calendar_date != date.today():
            self.refresh_calendar()

    def refresh_calendar(self) -> None:
        today = date.today()
        self._calendar_date = today
        monday = today - timedelta(days=today.weekday())
        self.calendar_month.setText(
            self.locale.toString(QDateTime.currentDateTime().date(), "MMMM yyyy").upper()
        )
        names = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")
        for index, (day_name, day_number) in enumerate(self.week_labels):
            day = monday + timedelta(days=index)
            pill: QWidget = day_name.property("pill")
            day_name.setText(names[index])
            day_number.setText(str(day.day))
            day_number.setToolTip(day.strftime("%d/%m/%Y"))
            if day == today:
                pill.setStyleSheet(
                    f"background:{themes.GREEN}; border-radius:14px;"
                )
                day_name.setStyleSheet("color:rgba(255,255,255,0.85); font-size:10px;")
                day_number.setStyleSheet("color:white; font-weight:700;")
            else:
                pill.setStyleSheet(
                    f"background:rgba(255,255,255,120); border:1px solid {themes.GLASS_EDGE_SOFT};"
                    " border-radius:14px;"
                )
                day_name.setStyleSheet("")
                day_number.setStyleSheet("")
        events = self.calendar_store.upcoming(today) if self.calendar_store else []
        now = datetime.now().time()
        events = [
            event
            for event in events
            if event.day != today
            or not (event.end or event.start)
            or (event.end or event.start) >= now
        ]
        if events:
            event = events[0]
            self.next_event.setText(event.title)
            self.next_event.setToolTip(event.title)
            day_text = "Hoje" if event.day == today else event.day.strftime("%d/%m")
            self.event_time.setText(f"{day_text} · {event.when}")
        else:
            self.next_event.setText("Agenda livre")
            self.next_event.setToolTip("Nenhum evento nos próximos 14 dias")
            self.event_time.setText("Sem eventos nos próximos 14 dias")

    def refresh_weather(self, force: bool = False) -> None:
        if not self.weather or not self.worker or not self.city_get:
            return
        data = self.city_get()
        if not data:
            self._ensure_auto_location()
            return
        try:
            place = Place(**data)
            key = (float(place.lat), float(place.lon))
        except (TypeError, ValueError):
            self._weather_error(self._weather_generation)
            return
        if self._weather_pending and key == self._weather_key:
            return
        if not force and key == self._weather_key:
            return
        self._weather_key = key
        self._weather_generation += 1
        generation = self._weather_generation
        self._weather_pending = True
        self._weather_name = place.name
        self.city.setText(place.name)
        self.weather_detail.setText("Atualizando…")

        async def load() -> None:
            try:
                result = await self.weather.forecast(place)
                self.bridge.weather_loaded.emit(generation, result)
            except Exception:  # noqa: BLE001
                self.bridge.weather_failed.emit(generation)

        self.worker.submit(load())

    def _ensure_auto_location(self) -> None:
        if self._locating or not self.weather or not self.worker:
            return
        self._locating = True
        self.city.setText("Detectando…")
        self.weather_detail.setText("Localização automática")

        async def locate() -> None:
            try:
                place = await self.weather.detect_place()
                self.bridge.located.emit(place)
            except Exception:  # noqa: BLE001
                self.bridge.located.emit(None)

        self.worker.submit(locate())

    def _on_located(self, place: Place | None) -> None:
        self._locating = False
        if place is None:
            self.city.setText("Local indisponível")
            self.weather_detail.setText("Busque uma cidade em Clima")
            return
        if self.city_set:
            self.city_set(
                {
                    "name": place.name,
                    "country": place.country,
                    "lat": place.lat,
                    "lon": place.lon,
                    "admin1": place.admin1,
                }
            )
        self.refresh_weather(force=True)

    def _show_weather(self, generation: int, weather: WeatherNow) -> None:
        if generation != self._weather_generation:
            return
        self._weather_pending = False
        self.weather_state = weather
        self.temperature.setText(f"{weather.temp_c:.0f}°")
        self.city.setText(weather.place.split(",")[0].strip() or self._weather_name)
        self.weather_detail.setText(weather.description)
        symbol = weather_icon(weather.code)
        color = themes.SIGNAL_WARM if symbol in ("sun", "cloud-sun") else "#5B8DEF"
        self.weather_symbol.setPixmap(icon(symbol, color, 24).pixmap(24, 24))

    def _weather_error(self, generation: int) -> None:
        if generation != self._weather_generation:
            return
        self._weather_pending = False
        self._weather_key = None
        self.weather_detail.setText("Clima indisponível")

    def refresh_market(self) -> None:
        if not self.market or not self.worker:
            return

        async def load() -> None:
            try:
                crypto = await self.market.crypto()
                stocks = await self.market.quotes(
                    [("PETR4.SA", "PETR4"), ("USDBRL=X", "USD")]
                )
                self.bridge.quotes.emit(list(crypto) + list(stocks))
            except Exception:  # noqa: BLE001
                self.bridge.quotes.emit([])

        self.worker.submit(load())

    def _show_quotes(self, quotes: list) -> None:
        chosen: list[Quote] = []
        by_name = {q.name: q for q in quotes}
        for key in ("BTC (BRL)", "BTC", "USD", "PETR4"):
            if key in by_name and by_name[key] not in chosen:
                chosen.append(by_name[key])
        # Prefer BRL bitcoin if present
        for q in quotes:
            if q.name.startswith("BTC") and q.currency == "BRL":
                chosen = [q] + [c for c in chosen if not c.name.startswith("BTC")]
                break
        # Keep USD and PETR4
        for q in quotes:
            if q.name == "USD" and q not in chosen:
                chosen.append(q)
            if q.name == "PETR4" and q not in chosen:
                chosen.append(q)
        chosen = chosen[:3]
        while len(chosen) < 3:
            chosen.append(Quote("—", "—", 0.0, None, "", ""))
        for (name, change, price), quote in zip(self.quote_rows, chosen, strict=True):
            label = "BTC" if quote.name.startswith("BTC") else quote.name
            name.setText(label)
            if quote.change_pct is None:
                change.setText("")
                change.setStyleSheet("")
            else:
                sign = "+" if quote.change_pct >= 0 else ""
                change.setText(f"{sign}{quote.change_pct:.2f}%".replace(".", ","))
                color = themes.GREEN if quote.change_pct >= 0 else themes.DANGER
                change.setStyleSheet(f"color:{color}; font-weight:600;")
            if quote.price:
                raw = f"{quote.price:,.2f}"
                brl = raw.replace(",", "X").replace(".", ",").replace("X", ".")
                if quote.currency == "BRL" or label == "PETR4":
                    price.setText(f"R$ {brl}")
                elif quote.currency == "USD":
                    price.setText(f"$ {raw}")
                else:
                    price.setText(raw)
            else:
                price.setText("")

    def refresh_news(self) -> None:
        if not self.news_service or not self.worker:
            return

        async def load() -> None:
            try:
                items = await self.news_service.fetch(limit=3)
                self.bridge.news.emit(items[:3])
            except Exception:  # noqa: BLE001
                self.bridge.news.emit([])

        self.worker.submit(load())

    def _show_news(self, items: list) -> None:
        self._news_items = list(items)
        for index, label in enumerate(self.news_labels):
            if index >= len(items):
                label.setText("—")
                label.setToolTip("")
                continue
            news: NewsItem = items[index]
            label.setText(f"{news.source} · {news.title}")
            label.setToolTip(news.link or news.title)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # Open news links when a news label is clicked.
        child = self.childAt(event.position().toPoint())
        if child in getattr(self, "news_labels", []):
            index = self.news_labels.index(child)
            items = getattr(self, "_news_items", [])
            if index < len(items) and items[index].link:
                QDesktopServices.openUrl(QUrl(items[index].link))
                event.accept()
                return
        super().mousePressEvent(event)

    def reload_pins(self) -> None:
        self._fill_dock(self.apps_row, "app")
        self._fill_dock(self.folders_row, "folder")

    def _fill_dock(self, row: QHBoxLayout, kind: str) -> None:
        while row.count():
            item = row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.db:
            empty = QLabel("Nada fixado ainda")
            empty.setObjectName("Muted")
            row.addWidget(empty)
            row.addStretch(1)
            return
        items = self.db.list_pinned(kind)[:8]
        if not items:
            empty = QLabel("Use + para fixar")
            empty.setObjectName("Muted")
            row.addWidget(empty)
        for pinned in items:
            ok, _ = validate_path(kind, pinned.path)
            btn = icon_button(
                "apps" if kind == "app" else "folder",
                pinned.label if ok else f"{pinned.label} (inválido)",
                36,
            )
            if ok:
                btn.clicked.connect(lambda _=False, path=pinned.path: open_path(path))
            else:
                btn.setEnabled(False)
            row.addWidget(btn)
        row.addStretch(1)

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self.refresh_calendar()
        self.refresh_weather()
        self.reload_pins()
