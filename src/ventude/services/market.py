"""Mercado via Yahoo Finance chart (sem chave) e CoinGecko (cripto, sem chave)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx

from ventude.services.cache import Cache

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
COINGECKO = "https://api.coingecko.com/api/v3/simple/price"
DEFAULT_SYMBOLS = [
    ("^BVSP", "Ibovespa"),
    ("PETR4.SA", "PETR4"),
    ("VALE3.SA", "VALE3"),
    ("ITUB4.SA", "ITUB4"),
    ("AAPL", "AAPL"),
    ("MSFT", "MSFT"),
]
CRYPTO = [("bitcoin", "BTC"), ("ethereum", "ETH")]
TTL = 10 * 60


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    price: float
    change_pct: float | None
    currency: str = ""
    source: str = ""


class MarketService:
    def __init__(self, cache: Cache, http: httpx.AsyncClient | None = None) -> None:
        self.cache = cache
        self.http = http or httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 Ventude/0.2"},
        )

    async def quotes(
        self, symbols: list[tuple[str, str]] | None = None
    ) -> list[Quote]:
        pairs = symbols or DEFAULT_SYMBOLS
        key = "mkt:yahoo:" + ",".join(s for s, _ in pairs)
        cached = self.cache.get(key)
        if cached is not None:
            return [Quote(**q) for q in cached]
        out: list[Quote] = []
        for symbol, name in pairs:
            try:
                r = await self.http.get(
                    YAHOO.format(symbol=symbol),
                    params={"interval": "1d", "range": "5d"},
                )
                r.raise_for_status()
                result = (r.json().get("chart") or {}).get("result") or []
                if not result:
                    continue
                meta = result[0].get("meta") or {}
                price = meta.get("regularMarketPrice")
                if price is None:
                    continue
                prev = meta.get("chartPreviousClose") or meta.get("previousClose")
                change = None
                if prev:
                    change = (float(price) - float(prev)) / float(prev) * 100
                out.append(
                    Quote(
                        symbol,
                        name,
                        float(price),
                        change,
                        meta.get("currency") or "",
                        "Yahoo Finance",
                    )
                )
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                continue
        self.cache.set(key, [asdict(q) for q in out], TTL)
        return out

    async def crypto(self) -> list[Quote]:
        key = "mkt:crypto"
        cached = self.cache.get(key)
        if cached is not None:
            return [Quote(**q) for q in cached]
        ids = ",".join(i for i, _ in CRYPTO)
        try:
            r = await self.http.get(
                COINGECKO,
                params={
                    "ids": ids,
                    "vs_currencies": "usd,brl",
                    "include_24hr_change": "true",
                },
            )
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return []
        out: list[Quote] = []
        for cid, name in CRYPTO:
            info = data.get(cid) or {}
            if "usd" not in info:
                continue
            out.append(
                Quote(
                    cid,
                    name,
                    float(info["usd"]),
                    float(info.get("usd_24h_change") or 0),
                    "USD",
                    "CoinGecko",
                )
            )
            if "brl" in info:
                out.append(
                    Quote(
                        cid + ".brl",
                        f"{name} (BRL)",
                        float(info["brl"]),
                        float(info.get("brl_24h_change") or info.get("usd_24h_change") or 0),
                        "BRL",
                        "CoinGecko",
                    )
                )
        self.cache.set(key, [asdict(q) for q in out], TTL)
        return out

    async def all(self) -> list[Quote]:
        return (await self.quotes()) + (await self.crypto())

    async def close(self) -> None:
        await self.http.aclose()
