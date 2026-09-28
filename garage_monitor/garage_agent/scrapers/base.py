"""Common HTTP + HTML helpers for portal adapters.

Every adapter exposes `search(cfg) -> list[Listing]`. Adapters are deliberately
defensive: portals change their markup often, so each one tries (1) structured
JSON embedded in the page (__NEXT_DATA__, JSON-LD, dataLayer), then (2) CSS
selectors, then (3) a generic 'link + text' fallback. When an adapter returns
zero results the run logs a warning so the selectors can be refreshed.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup

from ..models import Listing
from ..parsing import enrich_from_text

log = logging.getLogger(__name__)

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]


class Fetcher:
    def __init__(self, delay: float = 2.0, timeout: int = 30, retries: int = 2, proxies: Optional[dict] = None):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": random.choice(UA_POOL),
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })
        if proxies:
            self.s.proxies.update(proxies)
        self.delay, self.timeout, self.retries = delay, timeout, retries

    def get(self, url: str, **kw) -> Optional[requests.Response]:
        for attempt in range(self.retries + 1):
            try:
                time.sleep(self.delay + random.random())
                r = self.s.get(url, timeout=self.timeout, **kw)
                if r.status_code in (403, 429, 503):
                    log.warning("%s -> HTTP %s (bot protection?) attempt %d", url, r.status_code, attempt + 1)
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                log.warning("GET %s failed: %s", url, e)
        return None

    def soup(self, url: str) -> Optional[BeautifulSoup]:
        r = self.get(url)
        return BeautifulSoup(r.text, "lxml") if r is not None else None


# ---------------------------------------------------------------------------
def next_data(soup: BeautifulSoup) -> Optional[dict]:
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            return None
    return None


def json_ld(soup: BeautifulSoup) -> List[dict]:
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            out.extend(data if isinstance(data, list) else [data])
        except (json.JSONDecodeError, TypeError):
            pass
    return out


def walk(obj, key_pred, max_depth=12):
    """Yield every dict inside `obj` (any depth) that satisfies key_pred(dict)."""
    stack = [(obj, 0)]
    while stack:
        cur, d = stack.pop()
        if d > max_depth:
            continue
        if isinstance(cur, dict):
            if key_pred(cur):
                yield cur
            stack.extend((v, d + 1) for v in cur.values())
        elif isinstance(cur, list):
            stack.extend((v, d + 1) for v in cur)


def text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def num(x) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r"[\d.]+(?:,\d+)?", str(x))
    if not m:
        return None
    s = m.group(0)
    s = s.replace(".", "").replace(",", ".") if "," in s or s.count(".") > 1 or len(s.split(".")[-1]) == 3 else s
    try:
        return float(s)
    except ValueError:
        return None


def finalize(listings: Iterable[Listing], source: str) -> List[Listing]:
    """Deduplicate by URL, enrich numeric fields from text, drop obviously irrelevant ads."""
    seen, out = set(), []
    for l in listings:
        if not l.url or l.url in seen:
            continue
        seen.add(l.url)
        l.source = source
        enrich_from_text(l)
        blob = (l.title + " " + l.description).lower()
        if any(bad in blob for bad in ("affitto", "affittasi", "in locazione", "moto ", "posto moto", "motorino")):
            # rentals and motorcycle spots are out of scope
            if "vendita" not in blob and "vendesi" not in blob:
                continue
        out.append(l)
    if not out:
        log.warning("[%s] no listings parsed - portal markup may have changed", source)
    return out


def generic_cards(soup: BeautifulSoup, base: str, href_pattern: str) -> List[Listing]:
    """Last-resort extraction: any anchor matching href_pattern, with the text of its card."""
    out = []
    for a in soup.find_all("a", href=re.compile(href_pattern)):
        href = a["href"]
        url = href if href.startswith("http") else base.rstrip("/") + "/" + href.lstrip("/")
        card = a
        for _ in range(4):           # climb to something card-sized
            if card.parent and len(text(card.parent)) < 1200:
                card = card.parent
            else:
                break
        t = text(card)
        if len(t) < 15:
            continue
        out.append(Listing(source="", url=url, title=text(a)[:150] or t[:80], description=t))
    return out
