"""Resolve approximate user location for weather without typing a city."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

import httpx

from ventude.services.weather import Place

log = logging.getLogger(__name__)

# Lightweight IP lookup (no key). Fields kept minimal.
IP_ENDPOINTS = (
    "http://ip-api.com/json/?fields=status,message,city,regionName,country,lat,lon",
    "https://ipapi.co/json/",
)


async def detect_place(http: httpx.AsyncClient | None = None) -> Place | None:
    """Prefer OS geolocation on Windows; fall back to IP geolocation."""
    owns = http is None
    client = http or httpx.AsyncClient(timeout=12)
    try:
        if sys.platform == "win32":
            place = await _windows_geolocate(client)
            if place is not None:
                return place
        return await _ip_geolocate(client)
    finally:
        if owns:
            await client.aclose()


async def _windows_geolocate(http: httpx.AsyncClient) -> Place | None:
    try:
        from winrt.windows.devices.geolocation import Geolocator, PositionAccuracy
    except Exception:  # noqa: BLE001
        return None

    def read() -> tuple[float, float] | None:
        try:
            locator = Geolocator()
            locator.desired_accuracy = PositionAccuracy.DEFAULT
            # WinRT async bridged via .get() on IAsyncOperation in some builds;
            # fall through on any failure.
            op = locator.get_geoposition_async()
            pos = op.get() if hasattr(op, "get") else None
            if pos is None:
                return None
            coord = pos.coordinate.point.position
            return float(coord.latitude), float(coord.longitude)
        except Exception:  # noqa: BLE001
            log.debug("Windows Geolocator indisponível", exc_info=True)
            return None

    coords = await asyncio.to_thread(read)
    if coords is None:
        return None
    lat, lon = coords
    return await _reverse_name(http, lat, lon)


async def _ip_geolocate(http: httpx.AsyncClient) -> Place | None:
    for url in IP_ENDPOINTS:
        try:
            response = await http.get(url)
            response.raise_for_status()
            data = response.json()
            place = _place_from_ip_payload(data)
            if place is not None:
                return place
        except Exception:  # noqa: BLE001
            log.debug("IP geo falhou (%s)", url, exc_info=True)
    return None


def _place_from_ip_payload(data: dict[str, Any]) -> Place | None:
    if data.get("status") == "fail":
        return None
    try:
        lat = float(data.get("lat") if "lat" in data else data["latitude"])
        lon = float(data.get("lon") if "lon" in data else data["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    name = str(data.get("city") or data.get("regionName") or "Local atual").strip()
    country = str(data.get("country") or data.get("country_name") or "").strip()
    admin1 = str(data.get("regionName") or data.get("region") or "").strip()
    if admin1 == name:
        admin1 = ""
    return Place(name=name, country=country, lat=lat, lon=lon, admin1=admin1)


async def _reverse_name(http: httpx.AsyncClient, lat: float, lon: float) -> Place:
    """Best-effort label via Open-Meteo reverse (search by nearby name)."""
    try:
        # Open-Meteo has no official reverse endpoint; use bigdatacloud free reverse.
        response = await http.get(
            "https://api.bigdatacloud.net/data/reverse-geocode-client",
            params={"latitude": lat, "longitude": lon, "localityLanguage": "pt"},
        )
        response.raise_for_status()
        data = response.json()
        name = (
            data.get("city")
            or data.get("locality")
            or data.get("principalSubdivision")
            or "Local atual"
        )
        return Place(
            name=str(name),
            country=str(data.get("countryName") or ""),
            lat=lat,
            lon=lon,
            admin1=str(data.get("principalSubdivision") or ""),
        )
    except Exception:  # noqa: BLE001
        log.debug("Reverse geocode falhou", exc_info=True)
        return Place(name="Local atual", country="", lat=lat, lon=lon)
