from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ventude.core.async_worker import AsyncWorker
from ventude.services.weather import Place, WeatherNow, WeatherService
from ventude.ui import themes
from ventude.ui.icons import icon, icon_button, weather_icon


class _Bridge(QObject):
    places = Signal(list)
    weather = Signal(object)
    error = Signal(str)


class WeatherPage(QWidget):
    def __init__(
        self,
        service: WeatherService,
        worker: AsyncWorker,
        get_city: Any,
        set_city: Any,
    ) -> None:
        super().__init__()
        self.service, self.worker = service, worker
        self.get_city, self.set_city = get_city, set_city
        self.bridge = _Bridge()
        self.bridge.places.connect(self._show_places)
        self.bridge.weather.connect(self._show_weather)
        self.bridge.error.connect(lambda m: self.status.setText(m))

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Cidade (ex.: Cachoeirinha)")
        self.query.returnPressed.connect(self._search)
        search = icon_button("search", "Buscar cidade")
        search.clicked.connect(self._search)
        refresh = icon_button("refresh", "Atualizar previsão")
        refresh.clicked.connect(self._refresh_saved)
        row.addWidget(self.query, 1)
        row.addWidget(search)
        row.addWidget(refresh)
        lay.addLayout(row)
        self.places = QListWidget()
        self.places.setMaximumHeight(90)
        self.places.itemActivated.connect(self._pick)
        self.places.hide()
        lay.addWidget(self.places)
        self.title = QLabel("Clima")
        self.title.setObjectName("Title")
        self.temp = QLabel("—")
        self.temp.setObjectName("Big")
        self.symbol = QLabel()
        self.symbol.setFixedSize(48, 48)
        self.symbol.setPixmap(icon("cloud-sun", "#E9C987", 44).pixmap(44, 44))
        self.detail = QLabel()
        self.detail.setObjectName("Muted")
        self.detail.setWordWrap(True)
        self.forecast = QLabel()
        self.forecast.setObjectName("Muted")
        self.forecast.setWordWrap(True)
        self.status = QLabel("Dados: Open-Meteo (sem chave).")
        self.status.setObjectName("Muted")
        lay.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        current = QHBoxLayout()
        current.addStretch()
        current.addWidget(self.symbol)
        current.addWidget(self.temp)
        current.addStretch()
        lay.addLayout(current)
        for w in (self.detail, self.forecast, self.status):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(w)
        lay.addStretch()
        self._refresh_saved()

    def _search(self) -> None:
        q = self.query.text().strip()
        if len(q) < 2:
            return
        self.status.setText("Buscando…")

        async def run() -> None:
            try:
                places = await self.service.search_places(q)
                self.bridge.places.emit(places)
            except Exception as exc:  # noqa: BLE001
                self.bridge.error.emit(f"Falha na busca: {exc.__class__.__name__}")

        self.worker.submit(run())

    def _show_places(self, places: list) -> None:
        self.places.clear()
        if not places:
            self.places.hide()
            self.status.setText("Nenhum lugar encontrado.")
            return
        for p in places:
            item = QListWidgetItem(p.label)
            item.setData(256, p)
            self.places.addItem(item)
        self.places.show()
        self.status.setText(f"{len(places)} resultados. Clique duas vezes para escolher.")

    def _pick(self, item: QListWidgetItem) -> None:
        place: Place = item.data(256)
        self.set_city(
            {
                "name": place.name,
                "country": place.country,
                "lat": place.lat,
                "lon": place.lon,
                "admin1": place.admin1,
            }
        )
        self.places.hide()
        self._load(place)

    def _refresh_saved(self) -> None:
        data = self.get_city()
        if not data:
            self.status.setText("Busque uma cidade para começar. Fonte: Open-Meteo.")
            return
        self._load(Place(**data))

    def _load(self, place: Place) -> None:
        self.status.setText("Atualizando clima…")
        self.title.setText(place.label)

        async def run() -> None:
            try:
                wx = await self.service.forecast(place)
                self.bridge.weather.emit(wx)
            except Exception as exc:  # noqa: BLE001
                self.bridge.error.emit(f"Falha no clima: {exc.__class__.__name__}")

        self.worker.submit(run())

    def _show_weather(self, wx: WeatherNow) -> None:
        self.title.setText(wx.place)
        self.temp.setText(f"{wx.temp_c:.0f}°")
        symbol = weather_icon(wx.code)
        color = "#E9C987" if symbol in ("sun", "cloud-sun") else "#AFCBE9"
        self.symbol.setPixmap(icon(symbol, color, 44).pixmap(44, 44))
        self.symbol.setToolTip(wx.description)
        self.detail.setText(
            f"{wx.description} · sensação {wx.feels_c:.0f}° · "
            f"umidade {wx.humidity}% · vento {wx.wind_kmh:.0f} km/h"
        )
        lines = []
        for d in wx.daily[:5]:
            lines.append(
                f"{d['date'][5:]}  {d['min_c']:.0f}°/{d['max_c']:.0f}°  {d['description']}"
            )
        self.forecast.setText("\n".join(lines))
        self.status.setText("Atualizado (cache até 30 min). Open-Meteo.")
        self.temp.setStyleSheet(f"color:{themes.GREEN};")
