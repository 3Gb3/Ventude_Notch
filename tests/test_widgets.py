from datetime import date, time

import httpx
import pytest

from ventude.services.cache import Cache
from ventude.services.calendar_store import CalendarStore, parse_time
from ventude.services.lists_store import ListsStore
from ventude.services.market import MarketService
from ventude.services.news import NewsService, parse_feed
from ventude.services.weather import WeatherService


def test_cache_ttl_and_expiry(tmp_path, monkeypatch):
    c = Cache(tmp_path / "c.db")
    c.set("a", {"x": 1}, ttl_seconds=60)
    assert c.get("a") == {"x": 1}
    # Expira forçando o relógio
    import ventude.services.cache as mod

    real = mod.time.time
    monkeypatch.setattr(mod.time, "time", lambda: real() + 120)
    assert c.get("a") is None
    c.set("b", 2, 10)
    c.clear("b")
    assert c.get("b") is None
    c.close()


RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>T</title>
<item><title>Um</title><link>https://ex/1</link><pubDate>Wed, 04 Nov 2026 12:00:00 GMT</pubDate>
<description>&lt;b&gt;Resumo&lt;/b&gt; legal</description></item>
<item><title>Dois</title><link>https://ex/2</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom</title><link href="https://ex/a" rel="alternate"/>
<updated>2026-11-04T10:00:00Z</updated><summary>s</summary></entry>
</feed>"""


def test_parse_rss_and_atom():
    items = parse_feed(RSS, "G1", limit=10)
    assert items[0].title == "Um" and "Resumo" in items[0].summary
    assert items[0].link == "https://ex/1" and len(items) == 2
    atom = parse_feed(ATOM, "X")
    assert atom[0].title == "Atom" and atom[0].link == "https://ex/a"


def test_news_service_uses_cache(tmp_path):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(200, text=RSS)

    cache = Cache(tmp_path / "c.db")
    svc = NewsService(cache, httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def run():
        a = await svc.fetch(["G1"], limit=5)
        b = await svc.fetch(["G1"], limit=5)
        await svc.close()
        return a, b

    import asyncio

    a, b = asyncio.run(run())
    assert len(a) == 2 and a[0].title == b[0].title
    assert len(calls) == 1  # segunda chamada veio do cache


def test_weather_search_and_forecast(tmp_path):
    def handler(req: httpx.Request) -> httpx.Response:
        if "geocoding" in str(req.url):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "name": "Cachoeirinha",
                            "country": "Brasil",
                            "latitude": -29.95,
                            "longitude": -51.11,
                            "admin1": "RS",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "current": {
                    "temperature_2m": 22.4,
                    "apparent_temperature": 21.0,
                    "relative_humidity_2m": 70,
                    "weather_code": 2,
                    "wind_speed_10m": 12.0,
                },
                "daily": {
                    "time": ["2026-11-04"],
                    "weather_code": [2],
                    "temperature_2m_max": [25.0],
                    "temperature_2m_min": [15.0],
                },
            },
        )

    cache = Cache(tmp_path / "c.db")
    svc = WeatherService(cache, httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    import asyncio

    async def run():
        places = await svc.search_places("Cachoeirinha")
        wx = await svc.forecast(places[0])
        wx2 = await svc.forecast(places[0])
        await svc.close()
        return places, wx, wx2

    places, wx, wx2 = asyncio.run(run())
    assert places[0].name == "Cachoeirinha" and "Parcialmente" in wx.description
    assert wx.temp_c == 22.4 and wx2.place == wx.place


def test_market_yahoo_and_crypto(tmp_path):
    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "finance.yahoo.com" in url:
            return httpx.Response(
                200,
                json={
                    "chart": {
                        "result": [
                            {
                                "meta": {
                                    "regularMarketPrice": 105.0,
                                    "previousClose": 100.0,
                                    "currency": "USD",
                                }
                            }
                        ]
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "bitcoin": {
                    "usd": 100000.0,
                    "brl": 500000.0,
                    "usd_24h_change": 1.5,
                    "brl_24h_change": 1.2,
                },
                "ethereum": {"usd": 3000.0, "brl": 15000.0, "usd_24h_change": -0.5},
            },
        )

    cache = Cache(tmp_path / "c.db")
    svc = MarketService(cache, httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    import asyncio

    async def run():
        q = await svc.quotes([("AAPL", "AAPL")])
        c = await svc.crypto()
        await svc.close()
        return q, c

    q, c = asyncio.run(run())
    assert q[0].price == 105 and abs(q[0].change_pct - 5.0) < 0.01
    assert any(x.name == "BTC" for x in c)

def test_calendar_and_lists(tmp_path):
    cal = CalendarStore(tmp_path / "cal.db")
    day = date(2026, 11, 4)
    ev = cal.add("Reunião", day, time(9, 0), time(10, 0))
    assert cal.for_day(day)[0].title == "Reunião"
    assert 4 in cal.month_days_with_events(2026, 11)
    assert cal.upcoming(day, 1)[0].id == ev.id
    cal.remove(ev.id)
    assert cal.for_day(day) == []
    assert parse_time("09:30") == time(9, 30)
    with pytest.raises(ValueError):
        parse_time("9h")

    lists = ListsStore(tmp_path / "l.db")
    assert lists.lists()[0].name == "Geral"
    lid = lists.lists()[0].id
    item = lists.add_item(lid, "Comprar café")
    lists.toggle(item.id)
    assert lists.items(lid)[0].done
    lists.remove_item(item.id)
    lists.add_list("Mercado")
    lists.remove_list(lid)
    assert any(x.name == "Mercado" for x in lists.lists())


def test_island_has_widget_tabs(qapp, tmp_path, monkeypatch):
    from ventude.core.config import Settings
    from ventude.core.events import EventBus
    from ventude.services.media import MediaService
    from ventude.storage.database import Database
    from ventude.ui.notch import TABS, IslandWindow

    monkeypatch.setenv("VENTUDE_HOME", str(tmp_path))
    names = [n for n, _ in TABS]
    assert names == [
        "Início",
        "Aplicativos",
        "Pastas",
        "Clima",
        "Calendário",
        "Notícias",
        "Mercado",
        "Listas",
        "Configurações",
    ]
    island = IslandWindow(
        Settings(animation_ms=50),
        Database(tmp_path / "u.db"),
        EventBus(),
        MediaService(),
        widgets={
            "Clima": lambda: __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel("ok")
        },
    )
    assert island.stack.count() == len(TABS)
