"""subito.it - the largest Italian classifieds site; many private (no-agency) garage sales.
Listings are in __NEXT_DATA__ as `ads` items."""
from __future__ import annotations

import logging
from typing import List

from ..models import Listing
from ..parsing import parse_published
from .base import Fetcher, finalize, generic_cards, next_data, num, walk

log = logging.getLogger(__name__)
SOURCE = "subito"
BASE = "https://www.subito.it"


def _from_json(data) -> List[Listing]:
    out = []
    for ad in walk(data, lambda d: "urn" in d and "subject" in d and ("urls" in d or "url" in d)):
        urls = ad.get("urls") or {}
        url = urls.get("default") if isinstance(urls, dict) else ad.get("url")
        if not url:
            continue
        feats = {}
        for f in ad.get("features") or []:
            if isinstance(f, dict) and f.get("uri"):
                vals = f.get("values") or []
                feats[f["uri"]] = (vals[0].get("value") if vals and isinstance(vals[0], dict) else vals[0] if vals else None)
        geo = ad.get("geo") or {}
        adv = ad.get("advertiser") or {}
        l = Listing(
            source=SOURCE, url=url, title=ad.get("subject") or "", description=ad.get("body") or "",
            price=num(feats.get("/price")), surface_m2=num(feats.get("/size")),
            address=", ".join(x for x in ((geo.get("address") or {}).get("value") if isinstance(geo.get("address"), dict) else geo.get("address"),
                                          (geo.get("city") or {}).get("value") if isinstance(geo.get("city"), dict) else None) if x),
            lat=num((geo.get("map") or {}).get("latitude")) if isinstance(geo.get("map"), dict) else None,
            lon=num((geo.get("map") or {}).get("longitude")) if isinstance(geo.get("map"), dict) else None,
            contact_name=adv.get("name") or "", agency=adv.get("company_name") or "" if isinstance(adv, dict) else "",
            raw={"urn": ad.get("urn")},
        )
        if adv.get("type") == 1 or adv.get("company") is True:
            l.agency = l.agency or "agenzia"
        d = (ad.get("dates") or {}).get("display") or ad.get("date")
        if d:
            l.published = parse_published(str(d))
        out.append(l)
    return out


def search(cfg: dict, fetcher: Fetcher | None = None) -> List[Listing]:
    fetcher = fetcher or Fetcher()
    out: List[Listing] = []
    for u in cfg["sources"]["subito"]["urls"]:
        soup = fetcher.soup(u)
        if soup is None:
            continue
        data = next_data(soup)
        found = _from_json(data) if data else []
        if not found:
            found = generic_cards(soup, BASE, r"/annunci-lombardia/.*\.htm")
        out.extend(found)
    return finalize(out, SOURCE)
