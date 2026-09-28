"""immobiliare.it - Next.js site, listings are embedded as JSON in __NEXT_DATA__."""
from __future__ import annotations

import logging
from typing import List

from ..models import Listing
from ..parsing import parse_published
from .base import Fetcher, finalize, generic_cards, next_data, num, walk

log = logging.getLogger(__name__)
SOURCE = "immobiliare"
BASE = "https://www.immobiliare.it"


def _from_json(data: dict) -> List[Listing]:
    out = []
    for node in walk(data, lambda d: "realEstate" in d and isinstance(d["realEstate"], dict)):
        re_ = node["realEstate"]
        props = re_.get("properties") or [{}]
        p = props[0] if props else {}
        loc = p.get("location") or {}
        url = (node.get("seo") or {}).get("url") or f"{BASE}/annunci/{re_.get('id')}/"
        price = re_.get("price") or {}
        l = Listing(
            source=SOURCE, url=url,
            title=re_.get("title") or p.get("caption") or "",
            description=p.get("description") or "",
            price=num(price.get("value") if isinstance(price, dict) else price),
            surface_m2=num(p.get("surface") or p.get("surfaceValue")),
            address=", ".join(x for x in (loc.get("address"), loc.get("microzone") or loc.get("macrozone")) if x),
            lat=loc.get("latitude"), lon=loc.get("longitude"),
            agency=((re_.get("advertiser") or {}).get("agency") or {}).get("displayName", ""),
            contact_phone=", ".join(((re_.get("advertiser") or {}).get("agency") or {}).get("phones", []) or []) if isinstance(((re_.get("advertiser") or {}).get("agency") or {}).get("phones"), list) else "",
            raw={"id": re_.get("id")},
        )
        for f in p.get("features") or []:
            if isinstance(f, str) and "box" in f.lower():
                l.kind = "box"
        creation = re_.get("creationDate") or p.get("creationDate") or ""
        if creation:
            l.published = parse_published(str(creation))
        if isinstance(re_.get("visits"), (int, float)):
            l.views = int(re_["visits"])
        out.append(l)
    return out


def search(cfg: dict, fetcher: Fetcher | None = None) -> List[Listing]:
    fetcher = fetcher or Fetcher()
    urls = cfg["sources"]["immobiliare"]["urls"]
    out: List[Listing] = []
    for u in urls:
        soup = fetcher.soup(u)
        if soup is None:
            continue
        data = next_data(soup)
        found = _from_json(data) if data else []
        if not found:
            found = generic_cards(soup, BASE, r"/annunci/\d+")
        # follow the detail page for the ones we keep to get the full text (dimensions are only there)
        if cfg["sources"]["immobiliare"].get("fetch_details", True):
            for l in found[: cfg.get("max_details_per_source", 40)]:
                _detail(l, fetcher)
        out.extend(found)
    return finalize(out, SOURCE)


def _detail(l: Listing, fetcher: Fetcher) -> None:
    soup = fetcher.soup(l.url)
    if soup is None:
        return
    data = next_data(soup)
    if data:
        for node in walk(data, lambda d: "description" in d and isinstance(d.get("description"), str) and len(d["description"]) > 40):
            l.description = node["description"]
            break
        for node in walk(data, lambda d: "phones" in d and isinstance(d["phones"], list)):
            ph = [x.get("num") if isinstance(x, dict) else str(x) for x in node["phones"]]
            l.contact_phone = ", ".join(p for p in ph if p)
            break
        for node in walk(data, lambda d: "expenses" in d or "condominiumExpenses" in d):
            l.annual_expenses = num(node.get("expenses") or node.get("condominiumExpenses"))
            if l.annual_expenses and l.annual_expenses < 100:   # site shows monthly values
                l.annual_expenses *= 12
            break
    if not l.description:
        d = soup.select_one("[data-tracking-key='description'], .in-readAll, .im-description__text")
        if d:
            l.description = d.get_text(" ", strip=True)
