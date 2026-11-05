from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from PySide6.QtCore import QDateTime, QLocale, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ventude.core.async_worker import AsyncWorker
from ventude.services.calendar_store import CalendarStore
from ventude.services.media import MediaService
from ventude.services.weather import Place, WeatherNow, WeatherService
from ventude.ui import themes
from ventude.ui.fonts import display_font, mono_font, ui_font
from ventude.ui.icons import icon, icon_button, weather_icon
from ventude.ui.media_card import MediaCard


class _WeatherBridge(QObject):
    loaded = Signal(int, object)
    failed = Signal(int)
    located = Signal(object)


class HomePage(QWidget):
    """Glanceable clock, auto-located weather, agenda and media."""

    navigate_requested = Signal(str)

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
    ) -> None:
        super().__init__()
        self.clock_24h = clock_24h
        self._clock_mode: bool | None = None
        self.weather, self.worker = weather, worker
        self.city_get = city_get
        self.city_set = city_set
        self.calendar_store = calendar_store
        self.locale = QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
        self._calendar_date: date | None = None
        self._weather_generation = 0
        self._weather_key: tuple[float, float] | None = None
        self._weather_pending = False
        self._locating = False
        self._weather_name = "Clima"
        self._weather_description = "Detectando localização…"
        self.weather_state: WeatherNow | None = None
        self.bridge = _WeatherBridge(self)
        self.bridge.loaded.connect(self._show_weather)
        self.bridge.failed.connect(self._weather_error)
        self.bridge.located.connect(self._on_located)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        overview = QHBoxLayout()
        overview.setSpacing(8)

        clock_card, clock_layout = self._card()
        clock_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time = QLabel()
        self.time.setObjectName("HeroTime")
        self.time.setFont(display_font(40, QFont.Weight.DemiBold))
        self.date = QLabel()
        self.date.setObjectName("Muted")
        self.date.setFont(ui_font(11))
        self.weekday = QLabel()
        self.weekday.setObjectName("Section")
        for label in (self.weekday, self.time, self.date):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            clock_layout.addWidget(label)
        overview.addWidget(clock_card, 3)

        weather_card, weather_layout = self._card()
        weather_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.city = QLabel("Clima")
        self.city.setObjectName("Section")
        self.city.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.city.setTextFormat(Qt.TextFormat.PlainText)
        self.city.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        weather_layout.addWidget(self.city)
        temperature_row = QHBoxLayout()
        temperature_row.setSpacing(6)
        temperature_row.addStretch()
        self.weather_symbol = QLabel()
        self.weather_symbol.setFixedSize(32, 32)
        self.weather_symbol.setPixmap(
            icon("cloud-sun", themes.SIGNAL_WARM, 28).pixmap(28, 28)
        )
        temperature_row.addWidget(self.weather_symbol)
        self.temperature = QLabel("—°")
        self.temperature.setFont(display_font(32, QFont.Weight.DemiBold))
        self.temperature.setStyleSheet(f"color:{themes.TEXT}; letter-spacing:-1px;")
        temperature_row.addWidget(self.temperature)
        temperature_row.addStretch()
        weather_layout.addLayout(temperature_row)
        self.weather_detail = QLabel("Detectando localização…")
        self.weather_detail.setObjectName("Muted")
        self.weather_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.weather_detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        weather_layout.addWidget(self.weather_detail)
        self.weather_action = icon_button("arrow-right", "Ver previsão", 24)
        self.weather_action.clicked.connect(lambda: self.navigate_requested.emit("Clima"))
        weather_layout.addWidget(self.weather_action, 0, Qt.AlignmentFlag.AlignHCenter)
        overview.addWidget(weather_card, 3)

        calendar_card, calendar_layout = self._card()
        calendar_layout.setSpacing(6)
        heading = QHBoxLayout()
        self.calendar_month = QLabel()
        self.calendar_month.setObjectName("Section")
        heading.addWidget(self.calendar_month, 1)
        self.calendar_action = icon_button("arrow-right", "Abrir calendário", 24)
        self.calendar_action.clicked.connect(lambda: self.navigate_requested.emit("Calendário"))
        heading.addWidget(self.calendar_action)
        calendar_layout.addLayout(heading)
        week = QHBoxLayout()
        week.setSpacing(2)
        self.week_labels: list[tuple[QLabel, QLabel]] = []
        for _ in range(7):
            column = QVBoxLayout()
            column.setSpacing(3)
            day_name = QLabel()
            day_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            day_name.setObjectName("Faint")
            day_name.setFont(mono_font(9))
            day_number = QLabel()
            day_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            day_number.setMinimumSize(22, 24)
            day_number.setFont(display_font(12, QFont.Weight.Medium))
            column.addWidget(day_name)
            column.addWidget(day_number)
            week.addLayout(column, 1)
            self.week_labels.append((day_name, day_number))
        calendar_layout.addLayout(week)
        calendar_layout.addStretch(1)
        self.next_event = QLabel()
        self.next_event.setTextFormat(Qt.TextFormat.PlainText)
        self.next_event.setFont(ui_font(12, QFont.Weight.DemiBold))
        self.next_event.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.event_time = QLabel()
        self.event_time.setObjectName("Muted")
        self.event_time.setFont(ui_font(11))
        calendar_layout.addWidget(self.next_event)
        calendar_layout.addWidget(self.event_time)
        overview.addWidget(calendar_card, 5)
        root.addLayout(overview, 1)
        self.media_card = MediaCard(media)
        root.addWidget(self.media_card)
        self._timer = QTimer(self, interval=1000, timeout=self.refresh)
        self._timer.start()
        self._agenda_timer = QTimer(self, interval=30_000, timeout=self.refresh_calendar)
        self._agenda_timer.start()
        self._weather_timer = QTimer(self, interval=30 * 60_000)
        self._weather_timer.timeout.connect(lambda: self.refresh_weather(force=True))
        self._weather_timer.start()
        self.refresh()
        self.refresh_weather()

    @staticmethod
    def _card() -> tuple[QWidget, QVBoxLayout]:
        card = QWidget()
        card.setObjectName("Card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        card.setMinimumHeight(128)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        return card, layout

    def refresh(self) -> None:
        now = QDateTime.currentDateTime()
        self.time.setText(now.toString("HH:mm" if self.clock_24h else "h:mm AP"))
        if self._clock_mode != self.clock_24h:
            self._clock_mode = self.clock_24h
            self.time.setFont(display_font(40 if self.clock_24h else 30, QFont.Weight.DemiBold))
        self.date.setText(self.locale.toString(now.date(), "d 'de' MMMM"))
        self.weekday.setText(self.locale.toString(now.date(), "dddd").upper())
        if self._calendar_date != date.today():
            self.refresh_calendar()

    def refresh_calendar(self) -> None:
        today = date.today()
        self._calendar_date = today
        monday = today - timedelta(days=today.weekday())
        self.calendar_month.setText(
            self.locale.toString(QDateTime.currentDateTime().date(), "MMMM yyyy").upper()
        )
        for index, (day_name, day_number) in enumerate(self.week_labels):
            day = monday + timedelta(days=index)
            day_name.setText(("S", "T", "Q", "Q", "S", "S", "D")[index])
            day_number.setText(str(day.day))
            day_number.setToolTip(day.strftime("%d/%m/%Y"))
            if day == today:
                day_number.setStyleSheet(
                    f"background:{themes.GREEN}; color:{themes.BLACK}; border-radius:6px;"
                    "font-weight:600;"
                )
            else:
                day_number.setStyleSheet("background:transparent;")
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
            self._event_title = event.title
            self.next_event.setToolTip(event.title)
            day_text = "Hoje" if event.day == today else event.day.strftime("%d/%m")
            self.event_time.setText(f"{day_text} · {event.when}")
        else:
            self._event_title = "Agenda livre"
            self.next_event.setToolTip("Nenhum evento nos próximos 14 dias")
            self.event_time.setText("Sem eventos nos próximos 14 dias")
        self._elide_labels()

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
        if key != self._weather_key:
            self.weather_state = None
            self.temperature.setText("—°")
        self._weather_key = key
        self._weather_generation += 1
        generation = self._weather_generation
        self._weather_pending = True
        self._weather_name = place.name
        self._weather_description = "Atualizando…"
        self._elide_labels()

        async def load() -> None:
            try:
                result = await self.weather.forecast(place)
                self.bridge.loaded.emit(generation, result)
            except Exception:  # noqa: BLE001
                self.bridge.failed.emit(generation)

        self.worker.submit(load())

    def _ensure_auto_location(self) -> None:
        if self._locating or not self.weather or not self.worker:
            return
        self._locating = True
        self._weather_name = "Clima"
        self._weather_description = "Detectando localização…"
        self._elide_labels()

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
            self._weather_description = "Localização indisponível"
            self._elide_labels()
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
        self._weather_description = weather.description
        symbol = weather_icon(weather.code)
        color = themes.SIGNAL_WARM if symbol in ("sun", "cloud-sun") else "#9BB7D4"
        self.weather_symbol.setPixmap(icon(symbol, color, 28).pixmap(28, 28))
        self.weather_symbol.setToolTip(weather.description)
        self.weather_action.setToolTip(
            f"Sensação {weather.feels_c:.0f}° · umidade {weather.humidity}% · ver previsão"
        )
        # Prefer city name from saved place label when available.
        if weather.place:
            self._weather_name = weather.place.split(",")[0].strip() or self._weather_name
        self._elide_labels()

    def _weather_error(self, generation: int) -> None:
        if generation != self._weather_generation:
            return
        self._weather_pending = False
        self._weather_key = None
        self._weather_description = "Clima indisponível"
        self._elide_labels()

    def _elide_labels(self) -> None:
        for label, value in (
            (self.city, self._weather_name),
            (self.weather_detail, self._weather_description),
            (self.next_event, getattr(self, "_event_title", "Agenda livre")),
        ):
            label.setText(
                label.fontMetrics().elidedText(
                    value, Qt.TextElideMode.ElideRight, max(40, label.width())
                )
            )
            label.setToolTip(value)

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self.refresh_calendar()
        self.refresh_weather()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._elide_labels()
