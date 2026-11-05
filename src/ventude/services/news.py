"""Notícias via feeds RSS públicos (sem chave)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from html import unescape

import httpx

from ventude.services.cache import Cache

FEEDS: dict[str, str] = {
    "G1": "https://g1.globo.com/rss/g1/",
    "BBC Brasil": "https://feeds.bbci.co.uk/portuguese/rss.xml",
    "Tecnoblog": "https://tecnoblog.net/feed/",
}
TTL = 15 * 60
NS = {"atom": "http://www.w3.org/2005/Atom", "content": "http://purl.org/rss/1.0/modules/content/"}


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    source: str
    published: str = ""
    summary: str = ""


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return unescape(" ".join(el.text.split()))


def _strip_html(raw: str) -> str:
    # Remoção leve de tags; suficiente para resumos de feed.
    out, in_tag = [], False
    for ch in raw:
        if ch == "<":
            in_tag = True
        elif ch == ">":
            in_tag = False
        elif not in_tag:
            out.append(ch)
    return unescape(" ".join("".join(out).split()))




def _find(el, *names):
    for name in names:
        found = el.find(name)
        if found is not None:
            return found
    return None


def parse_feed(xml_text: str, source: str, limit: int = 12) -> list[NewsItem]:
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []
    # RSS 2.0
    for item in root.findall("./channel/item"):
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        if not title or not link:
            continue
        pub = _text(item.find("pubDate"))
        try:
            pub = parsedate_to_datetime(pub).astimezone().strftime("%d/%m %H:%M") if pub else ""
        except (TypeError, ValueError, OverflowError):
            pass
        summary = _strip_html(_text(item.find("description")))[:220]
        items.append(NewsItem(title, link, source, pub, summary))
        if len(items) >= limit:
            return items
    # Atom
    entries = list(root.findall("atom:entry", NS))
    if not entries:
        entries = list(root.findall("{http://www.w3.org/2005/Atom}entry"))
    for entry in entries:
        title_el = entry.find("atom:title", NS)
        if title_el is None:
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
        title = _text(title_el)
        link_el = entry.find("atom:link[@rel='alternate']", NS)
        if link_el is None:
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        link = (link_el.get("href") if link_el is not None else "") or ""
        if not title or not link:
            continue
        updated_el = entry.find("atom:updated", NS)
        if updated_el is None:
            updated_el = entry.find("{http://www.w3.org/2005/Atom}updated")
        updated = _text(updated_el)
        summary_el = entry.find("atom:summary", NS)
        if summary_el is None:
            summary_el = entry.find("{http://www.w3.org/2005/Atom}summary")
        summary = _strip_html(_text(summary_el))[:220]
        items.append(NewsItem(title, link, source, updated[:16], summary))
        if len(items) >= limit:
            break
    return items


class NewsService:
    def __init__(self, cache: Cache, http: httpx.AsyncClient | None = None) -> None:
        self.cache = cache
        self.http = http or httpx.AsyncClient(
            timeout=20, follow_redirects=True, headers={"User-Agent": "Ventude/0.1"}
        )

    async def fetch(self, sources: list[str] | None = None, limit: int = 10) -> list[NewsItem]:
        names = sources or list(FEEDS)
        all_items: list[NewsItem] = []
        for name in names:
            url = FEEDS.get(name)
            if not url:
                continue
            key = f"news:{name}"
            cached = self.cache.get(key)
            if cached is not None:
                all_items.extend(NewsItem(**i) for i in cached)
                continue
            try:
                r = await self.http.get(url)
                r.raise_for_status()
                items = parse_feed(r.text, name, limit)
            except (httpx.HTTPError, ET.ParseError):
                items = []
            self.cache.set(key, [asdict(i) for i in items], TTL)
            all_items.extend(items)
        # Ordena por data quando possível; mantém a ordem do feed como fallback.
        return all_items[: limit * max(1, len(names))]

    async def close(self) -> None:
        await self.http.aclose()
