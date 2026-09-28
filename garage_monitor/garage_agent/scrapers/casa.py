"""casa.it - Next.js site; listings in __NEXT_DATA__ or JSON-LD, HTML cards as fallback."""
from __future__ import annotations

import logging
from typing import List

from ..models import Listing
from ..parsing import parse_published
from .base import Fetcher, finalize, generic_cards, json_ld, next_data, num, text, walk

log = logging.getLogger(__name__)
SOURCE = "casa"
BASE = "https://www.casa.it"


def _from_json(data) -> List[Listing]:
    out = []
    for node in walk(data, lambda d: ("uri" in d or "url" in d) and "price" in d and ("title" in d or "description" in d)):
        url = node.get("uri") or node.get("url")
        if not url or "casa.it" not in url and not url.startswith("/"):
            continue
        url = url if url.startswith("http") else BASE + url
        price = node.get("price")
        if isinstance(price, dict):
            price = price.get("value") or price.get("amount") or price.get("formatted")
        geo = node.get("geo") or node.get("location") or node.get("coordinates") or {}
        l = Listing(
            source=SOURCE, url=url, title=node.get("title") or "", description=node.get("description") or "",
            price=num(price), surface_m2=num(node.get("surface") or node.get("mq")),
            address=str(node.get("address") or (node.get("location") or {}).get("address", "") if isinstance(node.get("location"), dict) else node.get("address", "") or ""),
            lat=geo.get("lat") or geo.get("latitude"), lon=geo.get("lng") or geo.get("lon") or geo.get("longitude"),
            agency=str((node.get("agency") or {}).get("name", "") if isinstance(node.get("agency"), dict) else node.get("agency") or ""),
        )
        d = node.get("publishedAt") or node.get("date") or node.get("createdAt")
        if d:
            l.published = parse_published(str(d))
        out.append(l)
    return out


def _detail(l: Listing, fetcher: Fetcher) -> None:
    soup = fetcher.soup(l.url)
    if soup is None:
        return
    d = soup.select_one("[class*=description], #description, .description")
    if d:
        l.description = text(d)
    for row in soup.select("li, dl, tr, [class*=feature]"):
        t = text(row).lower()
        if len(t) > 120:
            continue
        if "spese" in t and num(t):
            v = num(t)
            l.annual_expenses = v * 12 if "mese" in t else v
        if t.startswith("indirizzo") or "via " in t[:20] or "viale " in t[:20] or "piazza" in t[:20]:
            l.address = l.address or text(row)
    ph = soup.select_one("a[href^='tel:']")
    if ph:
        l.contact_phone = ph["href"].replace("tel:", "")


def search(cfg: dict, fetcher: Fetcher | None = None) -> List[Listing]:
    fetcher = fetcher or Fetcher()
    out: List[Listing] = []
    for u in cfg["sources"]["casa"]["urls"]:
        soup = fetcher.soup(u)
        if soup is None:
            continue
        found: List[Listing] = []
        data = next_data(soup)
        if data:
            found = _from_json(data)
        if not found:
            found = _from_json(json_ld(soup))
        if not found:
            found = generic_cards(soup, BASE, r"/immobili/\d+|/vendita/[a-z-]+/[^\"']+/\d+")
        if cfg["sources"]["casa"].get("fetch_details", True):
            for l in found[: cfg.get("max_details_per_source", 40)]:
                _detail(l, fetcher)
        out.extend(found)
    return finalize(out, SOURCE)
