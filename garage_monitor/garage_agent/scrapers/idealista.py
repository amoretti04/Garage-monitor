"""idealista.it - server-rendered HTML (article.item cards).

NOTE: idealista uses aggressive bot protection (DataDome). Requests may return
403; when that happens the run keeps going with the other portals and logs it.
A residential proxy or a headless browser (see README, `use_playwright`) helps."""
from __future__ import annotations

import logging
from typing import List

from ..models import Listing
from ..parsing import parse_published
from .base import Fetcher, finalize, generic_cards, num, text

log = logging.getLogger(__name__)
SOURCE = "idealista"
BASE = "https://www.idealista.it"


def _cards(soup) -> List[Listing]:
    out = []
    for art in soup.select("article.item, article[data-element-id]"):
        a = art.select_one("a.item-link")
        if not a:
            continue
        url = a["href"] if a["href"].startswith("http") else BASE + a["href"]
        l = Listing(source=SOURCE, url=url, title=text(a), description=text(art.select_one(".item-description")) or text(art))
        l.price = num(text(art.select_one(".item-price")))
        details = [text(d) for d in art.select(".item-detail")]
        for d in details:
            if "m²" in d or "mq" in d:
                l.surface_m2 = num(d)
        l.agency = text(art.select_one(".logo-branding img[alt]") and art.select_one(".logo-branding img")["alt"]) if art.select_one(".logo-branding img") else ""
        l.contact_phone = text(art.select_one(".icon-phone, .item-phone"))
        out.append(l)
    return out


def _detail(l: Listing, fetcher: Fetcher) -> None:
    soup = fetcher.soup(l.url)
    if soup is None:
        return
    d = soup.select_one(".comment, .adCommentsLanguage, #description")
    if d:
        l.description = text(d)
    addr = soup.select_one("#headerMap li, .main-info__title-minor, #mapWrapper .info-address")
    if addr:
        l.address = text(addr)
    date_el = soup.select_one(".date-update-text, p.stats-text, .ide-box-detail-stats")
    if date_el:
        l.published = parse_published(text(date_el)) or l.published
    for li in soup.select(".details-property li, .info-features span"):
        t = text(li).lower()
        if "spese" in t or "condominio" in t:
            v = num(t)
            if v:
                l.annual_expenses = v * 12 if "mese" in t else v
    ph = soup.select_one("[data-phone], .hidden-contact-phones_formatted-phone, ._phone")
    if ph:
        l.contact_phone = ph.get("data-phone") or text(ph)
    ag = soup.select_one(".professional-name, .advertiser-name, .about-advertiser-name")
    if ag:
        l.agency = text(ag)


def search(cfg: dict, fetcher: Fetcher | None = None) -> List[Listing]:
    fetcher = fetcher or Fetcher(delay=3)
    out: List[Listing] = []
    for u in cfg["sources"]["idealista"]["urls"]:
        soup = fetcher.soup(u)
        if soup is None:
            continue
        found = _cards(soup) or generic_cards(soup, BASE, r"/immobile/\d+")
        if cfg["sources"]["idealista"].get("fetch_details", True):
            for l in found[: cfg.get("max_details_per_source", 40)]:
                _detail(l, fetcher)
        out.extend(found)
    return finalize(out, SOURCE)
