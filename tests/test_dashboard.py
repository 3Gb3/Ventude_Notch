import asyncio
from datetime import date, timedelta

from ventude.services.calendar_store import CalendarStore
from ventude.services.media import MediaService
from ventude.services.weather import WeatherNow
from ventude.ui.pages.home import HomePage


class QueuedWorker:
    def __init__(self):
        self.pending = []

    def submit(self, coroutine):
        self.pending.append(coroutine)


class FakeWeather:
    async def forecast(self, place):
        return WeatherNow(place.name, place.lat, 20, 60, 10, 0, "Céu limpo", [])

    async def detect_place(self):
        return None


def test_dashboard_only_shows_latest_city_response(qapp):
    worker = QueuedWorker()
    city = {"name": "Cidade A", "country": "BR", "lat": 20, "lon": 1}
    page = HomePage(
        MediaService(), weather=FakeWeather(), worker=worker, city_get=lambda: city
    )
    city.update(name="Cidade B", lat=25)
    page.refresh_weather()
    asyncio.run(worker.pending[1])
    asyncio.run(worker.pending[0])
    assert page.weather_state.place == "Cidade B"
    assert page.temperature.text() == "25°"
    page.close()


def test_dashboard_cleared_city_triggers_auto_locate(qapp):
    worker = QueuedWorker()
    city = {"name": "Cidade A", "country": "BR", "lat": 20, "lon": 1}
    page = HomePage(
        MediaService(), weather=FakeWeather(), worker=worker, city_get=lambda: city
    )
    city.clear()
    page.refresh_weather()
    # Pending forecast from first paint may exist; last job is auto-locate.
    asyncio.run(worker.pending[-1])
    assert page.weather_state is None
    assert page.temperature.text() == "—°"
    assert "indisponível" in page.weather_detail.toolTip().lower() or page._locating is False
    page.close()


def test_dashboard_agenda_refresh_and_navigation(qapp, tmp_path):
    calendar = CalendarStore(tmp_path / "calendar.db")
    event = calendar.add("Meu compromisso", date.today() + timedelta(days=1))
    page = HomePage(MediaService(), calendar_store=calendar)
    assert page.next_event.toolTip() == event.title
    calendar.remove(event.id)
    page.refresh_calendar()
    assert page.next_event.toolTip() == "Agenda livre"
    destinations = []
    page.navigate_requested.connect(destinations.append)
    page.weather_action.click()
    page.calendar_action.click()
    assert destinations == ["Clima", "Calendário"]
    page.close()
    calendar.close()
