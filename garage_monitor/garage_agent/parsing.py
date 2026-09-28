"""Regex-based extraction of dimensions, prices, expenses, dates and interest
from the free text of Italian real-estate adverts."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

_NUM = r"(\d{1,2}(?:[.,]\d{1,2})?)"
_SEP = r"\s*(?:x|×|\*|per)\s*"
_UNIT = r"\s*(?:m|mt|metri|mtl|ml)?\.?"


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def parse_dimensions(text: str) -> Tuple[Optional[float], Optional[float]]:
    """Return (length_m, width_m) - larger value is always the length.

    Handles: '5x2,5', '5,20 x 2,60 m', 'misure 5.00x2.50', 'lunghezza 5 m larghezza 2,5',
    'lungo 4,80 largo 2,30', 'mt 5 x 2,5', 'L 5 m - P 2,5 m'."""
    if not text:
        return None, None
    t = text.lower().replace("\xa0", " ")

    # 1) explicit "A x B" pair (values plausible for a car space)
    for m in re.finditer(_NUM + _UNIT + _SEP + _NUM + _UNIT, t):
        a, b = _f(m.group(1)), _f(m.group(2))
        if 1.5 <= a <= 12 and 1.5 <= b <= 12 and not (a > 8 and b > 8):
            # avoid matching e.g. '2 x 3 piani' - require both look like metres
            return max(a, b), min(a, b)

    # 2) labelled length / width
    length = width = None
    m = re.search(r"(?:lunghezz[ao]|lungo|profondit[àa]|profondo|lung\.?)\D{0,12}" + _NUM, t)
    if m:
        length = _f(m.group(1))
    m = re.search(r"(?:larghezz[ao]|largo|larg\.?|ampiezza)\D{0,12}" + _NUM, t)
    if m:
        width = _f(m.group(1))
    if length and width:
        return max(length, width), min(length, width)
    if length and 3 <= length <= 12:
        return length, None
    if width and 1.5 <= width <= 5:
        return None, width
    return None, None


def parse_surface(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.lower()
    m = re.search(r"(\d{1,3}(?:[.,]\d)?)\s*(?:mq|m²|m2|metri quadr)", t) or re.search(r"(?:mq|m²|m2)\s*(\d{1,3})", t)
    if m:
        v = _f(m.group(1))
        return v if 5 <= v <= 120 else None
    return None


def parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.replace("\xa0", " ")
    m = re.search(r"€\s*([\d.]{4,9})(?:,\d+)?", t) or re.search(r"([\d.]{4,9})(?:,\d+)?\s*(?:€|euro)", t, re.I)
    if m:
        v = float(m.group(1).replace(".", ""))
        return v if 1000 <= v <= 500_000 else None
    return None


def parse_annual_expenses(text: str) -> Optional[float]:
    """Condominium / running costs, normalised to EUR per year."""
    if not text:
        return None
    t = text.lower().replace("\xa0", " ")
    pats = [
        r"spese(?:\s+condominiali|\s+condominio|\s+di gestione)?\D{0,25}?€?\s*(\d{1,2}(?:\.\d{3})+|\d{1,5})(?:,\d+)?\s*(?:€|euro)?\s*(?:/|al|a|l'|ogni)?\s*(anno|annue|annuali|annuo|mese|mensili|mensile|mensilmente)?",
        r"€?\s*(\d{1,5})(?:,\d+)?\s*(?:€|euro)?\s*(?:/|al|a|l')\s*(anno|mese)\s+di spese",
    ]
    for p in pats:
        m = re.search(p, t)
        if m:
            v = float(m.group(1).replace(".", ""))
            period = (m.group(2) or "").strip()
            if period.startswith("mes"):
                v *= 12
            if 0 < v <= 10_000:
                return round(v, 2)
    return None


_MONTHS = {m: i for i, m in enumerate(
    ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
     "agosto", "settembre", "ottobre", "novembre", "dicembre"], 1)}


def parse_published(text: str, today: Optional[date] = None) -> Optional[date]:
    """Absolute ('12/09/2026', '12 settembre 2026', ISO) or relative ('3 giorni fa', 'ieri')."""
    if not text:
        return None
    today = today or date.today()
    t = text.lower()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        try:
            return date(y, mo, d)
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s*(\d{4})?", t)
    if m:
        y = int(m.group(3)) if m.group(3) else today.year
        try:
            d = date(y, _MONTHS[m.group(2)], int(m.group(1)))
            return d if d <= today else d.replace(year=y - 1)
        except ValueError:
            pass
    if "oggi" in t or "poche ore" in t or re.search(r"\d+\s*(?:ore|minuti)\s+fa", t):
        return today
    if "ieri" in t:
        return today - timedelta(days=1)
    m = re.search(r"(\d+)\s*(giorn|settiman|mes)\w*\s+fa", t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        days = n if unit.startswith("giorn") else n * 7 if unit.startswith("settiman") else n * 30
        return today - timedelta(days=days)
    return None


def parse_views(text: str) -> Optional[int]:
    if not text:
        return None
    t = text.lower()
    m = re.search(r"(\d[\d.]*)\s*(?:visualizzazioni|visite|views)", t) or \
        re.search(r"(?:visualizzazioni|visite|visto)\D{0,10}(\d[\d.]*)", t)
    if m:
        try:
            return int(m.group(1).replace(".", ""))
        except ValueError:
            return None
    return None


def parse_kind(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"\bbox\b|garage|autorimessa", t):
        return "box"
    if "posto auto" in t or "posti auto" in t or "parcheggio" in t:
        return "posto_auto"
    return "unknown"


def parse_phone(text: str) -> str:
    m = re.search(r"(?:\+39\s?)?(?:0\d{1,3}[\s.-]?\d{5,8}|3\d{2}[\s.-]?\d{6,7})", text or "")
    return m.group(0).strip() if m else ""


def enrich_from_text(listing) -> None:
    """Fill missing numeric fields of a Listing from its title + description."""
    blob = " ".join(x for x in (listing.title, listing.description) if x)
    if listing.length_m is None and listing.width_m is None:
        listing.length_m, listing.width_m = parse_dimensions(blob)
    if listing.surface_m2 is None:
        listing.surface_m2 = parse_surface(blob)
    if listing.price is None:
        listing.price = parse_price(blob)
    if listing.annual_expenses is None:
        listing.annual_expenses = parse_annual_expenses(blob)
    if listing.views is None:
        listing.views = parse_views(blob)
    if listing.published is None:
        m = re.search(r"(?:pubblicat[oa]|inserit[oa]|online)\s+(?:il\s+|da\s+)?([^.\n]{2,25})", blob, re.I)
        if m:
            listing.published = parse_published(m.group(1))
    if listing.kind == "unknown":
        listing.kind = parse_kind(blob)
    if not listing.contact_phone:
        listing.contact_phone = parse_phone(listing.description)
    # derive surface from dims / a rough dims guess from surface for scoring
    if listing.surface_m2 is None and listing.length_m and listing.width_m:
        listing.surface_m2 = round(listing.length_m * listing.width_m, 1)
