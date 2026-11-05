"""Clima via Open-Meteo (gratuito, sem chave) + geocoding Open-Meteo."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import httpx

from ventude.services.cache import Cache

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
WMO = {
    0: "Céu limpo",
    1: "Principalmente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Neblina",
    48: "Neblina com geada",
    51: "Garoa fraca",
    53: "Garoa",
    55: "Garoa forte",
    61: "Chuva fraca",
    63: "Chuva",
    65: "Chuva forte",
    71: "Neve fraca",
    73: "Neve",
    75: "Neve forte",
    80: "Pancadas fracas",
    81: "Pancadas",
    82: "Pancadas fortes",
    95: "Tempestade",
    96: "Tempestade com granizo",
    99: "Tempestade forte com granizo",
}
TTL = 30 * 60  # 30 min


@dataclass(frozen=True)
class Place:
    name: str
    country: str
    lat: float
    lon: float
    admin1: str = ""

    @property
    def label(self) -> str:
        parts = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass(frozen=True)
class WeatherNow:
    place: str
    temp_c: float
    feels_c: float
    humidity: int
    wind_kmh: float
    code: int
    description: str
    daily: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WeatherNow:
        return cls(**d)


class WeatherService:
    def __init__(self, cache: Cache, http: httpx.AsyncClient | None = None) -> None:
        self.cache = cache
        self.http = http or httpx.AsyncClient(timeout=20)

    async def search_places(self, query: str, limit: int = 6) -> list[Place]:
        q = query.strip()
        if len(q) < 2:
            return []
        key = f"geo:{q.lower()}:{limit}"
        cached = self.cache.get(key)
        if cached is not None:
            return [Place(**p) for p in cached]
        r = await self.http.get(
            GEOCODE, params={"name": q, "count": limit, "language": "pt", "format": "json"}
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        places = [
            Place(
                name=i["name"],
                country=i.get("country", ""),
                lat=float(i["latitude"]),
                lon=float(i["longitude"]),
                admin1=i.get("admin1", "") or "",
            )
            for i in results
        ]
        self.cache.set(key, [asdict(p) for p in places], 24 * 3600)
        return places

    async def forecast(self, place: Place) -> WeatherNow:
        key = f"wx:{place.lat:.3f},{place.lon:.3f}"
        cached = self.cache.get(key)
        if cached is not None:
            return WeatherNow.from_dict(cached)
        r = await self.http.get(
            FORECAST,
            params={
                "latitude": place.lat,
                "longitude": place.lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
                "forecast_days": 5,
                "wind_speed_unit": "kmh",
            },
        )
        r.raise_for_status()
        data = r.json()
        cur = data["current"]
        daily = data["daily"]
        code = int(cur["weather_code"])
        days = [
            {
                "date": daily["time"][i],
                "code": int(daily["weather_code"][i]),
                "description": WMO.get(int(daily["weather_code"][i]), "—"),
                "max_c": daily["temperature_2m_max"][i],
                "min_c": daily["temperature_2m_min"][i],
            }
            for i in range(len(daily["time"]))
        ]
        now = WeatherNow(
            place=place.label,
            temp_c=float(cur["temperature_2m"]),
            feels_c=float(cur["apparent_temperature"]),
            humidity=int(cur["relative_humidity_2m"]),
            wind_kmh=float(cur["wind_speed_10m"]),
            code=code,
            description=WMO.get(code, "—"),
            daily=days,
        )
        self.cache.set(key, now.to_dict(), TTL)
        return now

    async def close(self) -> None:
        await self.http.aclose()
