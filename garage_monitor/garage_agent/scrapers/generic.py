"""Generic adapter for bulletin-board style sites (secondamanoitalia.it, bakeca.it,
clickannunci, agency websites...). Configured entirely from config.yaml:

    secondamano:
      adapter: generic
      base: https://www.secondamanoitalia.it
      urls: [ "https://www.secondamanoitalia.it/annunci/...?q=box+auto+milano" ]
      card: "article, .annuncio, .listing"      # optional CSS selector for a card
      link: "a[href*='/annuncio']"               # CSS selector of the ad link inside a card
      href_pattern: "/annunci?o/"                # regex fallback if selectors fail
      fetch_details: true
      detail_description: ".descrizione, #description"
"""
from __future__ import annotations

import logging
import re
from typing import List

from ..models import Listing
from ..parsing import parse_published
from .base import Fetcher, finalize, generic_cards, text

log = logging.getLogger(__name__)


def _cards(soup, sc: dict) -> List[Listing]:
    out = []
    base = sc["base"].rstrip("/")
    for card in soup.select(sc.get("card", "article")):
        a = card.select_one(sc.get("link", "a[href]"))
        if not a or not a.get("href"):
            continue
        href = a["href"]
        url = href if href.startswith("http") else base + "/" + href.lstrip("/")
        t = text(card)
        if len(t) < 15:
            continue
        out.append(Listing(source=sc["name"], url=url, title=text(a)[:150] or t[:80], description=t))
    return out


def _detail(l: Listing, fetcher: Fetcher, sc: dict) -> None:
    soup = fetcher.soup(l.url)
    if soup is None:
        return
    d = soup.select_one(sc.get("detail_description", "[class*=descri], #description, .description, .body"))
    if d:
        l.description = text(d)
    else:
        main = soup.select_one("main, article, #content") or soup.body
        l.description = text(main)[:4000] if main else l.description
    addr = soup.select_one(sc.get("detail_address", "[class*=indirizzo], [class*=address], [class*=location], [class*=zona]"))
    if addr:
        l.address = text(addr)
    ph = soup.select_one("a[href^='tel:']")
    if ph:
        l.contact_phone = ph["href"].replace("tel:", "").strip()
    mail = soup.select_one("a[href^='mailto:']")
    if mail:
        l.contact_email = mail["href"].replace("mailto:", "").strip()
    dt = soup.select_one(sc.get("detail_date", "time, [class*=data], [class*=date], [class*=pubblic]"))
    if dt:
        l.published = parse_published(dt.get("datetime") or text(dt))
    if not l.published:
        m = re.search(r"pubblicat[oa]\s+(?:il\s+)?([^.<\n]{4,30})", soup.get_text(" ", strip=True), re.I)
        if m:
            l.published = parse_published(m.group(1))


def search(cfg: dict, name: str, fetcher: Fetcher | None = None) -> List[Listing]:
    sc = {"name": name, **cfg["sources"][name]}
    fetcher = fetcher or Fetcher()
    out: List[Listing] = []
    for u in sc["urls"]:
        soup = fetcher.soup(u)
        if soup is None:
            continue
        found = _cards(soup, sc)
        if not found and sc.get("href_pattern"):
            found = generic_cards(soup, sc["base"], sc["href_pattern"])
        # keep only ads that look like garages / car spots for sale
        found = [l for l in found if re.search(r"box|garage|posto auto|posti auto|autorimessa", (l.title + l.description).lower())]
        if sc.get("fetch_details", True):
            for l in found[: cfg.get("max_details_per_source", 40)]:
                _detail(l, fetcher, sc)
        out.extend(found)
    return finalize(out, name)
