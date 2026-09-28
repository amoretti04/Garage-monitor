"""Filtering and priority scoring.

Priority order requested by the client (most to least important):
  1. distance from home   2. size   3. price   4. days since publication   5. interest / views
Each criterion is normalised to 0..1 and combined with decreasing weights.
"""
from __future__ import annotations

import statistics
from typing import Dict, List, Optional, Tuple

from .models import Listing

DEFAULT_WEIGHTS = {"distance": 0.40, "size": 0.28, "price": 0.20, "freshness": 0.07, "interest": 0.05}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def passes_hard_filters(l: Listing, cfg: dict) -> Tuple[bool, str]:
    """Reject listings that certainly don't fit. Unknown values are kept (flagged for manual check)."""
    req = cfg["requirements"]
    max_walk = cfg["home"]["max_walk_minutes"]
    if l.walk_minutes is not None and l.walk_minutes > max_walk * cfg["home"].get("tolerance", 1.15):
        return False, f"troppo lontano ({l.walk_minutes:.0f} min)"
    if l.length_m is not None and l.length_m < req["min_length_m"]:
        return False, f"troppo corto ({l.length_m} m)"
    if l.width_m is not None and l.width_m < req["min_width_m"]:
        return False, f"troppo stretto ({l.width_m} m)"
    if l.surface_m2 is not None and l.surface_m2 < req.get("min_surface_m2", 10):
        return False, f"superficie insufficiente ({l.surface_m2} m²)"
    if l.price is not None and l.price > req.get("max_price", 1e9):
        return False, f"oltre budget ({l.price:.0f} €)"
    if l.price is not None and l.price < req.get("min_price", 0):
        return False, "prezzo non plausibile"
    return True, ""


def score_all(listings: List[Listing], cfg: dict) -> Dict[str, Tuple[float, dict]]:
    """Return {listing.id: (score 0..100, breakdown)}."""
    w = {**DEFAULT_WEIGHTS, **cfg.get("weights", {})}
    req = cfg["requirements"]
    max_walk = cfg["home"]["max_walk_minutes"]

    prices = [l.price for l in listings if l.price]
    p_lo = min(prices) if prices else req.get("min_price", 10_000)
    p_hi = max(prices) if prices else req.get("max_price", 80_000)
    if p_hi - p_lo < 5_000:
        p_lo, p_hi = p_lo - 2_500, p_hi + 2_500
    max_views = max((l.views or 0) for l in listings) if listings else 0

    out = {}
    for l in listings:
        b = {}
        # 1. distance: 1.0 at the door, 0 at the 10-minute limit; unknown -> pessimistic 0.35
        if l.walk_minutes is None:
            b["distance"] = 0.35
        else:
            b["distance"] = _clamp(1 - l.walk_minutes / max_walk)

        # 2. size: width is the binding constraint (>= 2.5 m ideal), length gives a small extra
        if l.width_m is not None:
            ws = _clamp((l.width_m - req["min_width_m"]) / (req["ideal_width_m"] - req["min_width_m"]))
            ws = 0.5 + 0.5 * ws               # anything passing the hard filter is at least 0.5
        else:
            ws = None
        if l.length_m is not None:
            ls = _clamp((l.length_m - req["min_length_m"]) / 1.5)   # 4.5 -> 0, 6.0 -> 1
        else:
            ls = None
        if ws is not None and ls is not None:
            b["size"] = 0.8 * ws + 0.2 * ls
        elif ws is not None:
            b["size"] = 0.9 * ws
        elif ls is not None:
            b["size"] = 0.3 + 0.3 * ls
        elif l.surface_m2 is not None:
            # 12 m² ~ minimal box, 18 m² and above very likely wide enough
            b["size"] = 0.25 + 0.35 * _clamp((l.surface_m2 - 11) / 7)
        else:
            b["size"] = 0.2                    # unknown: to be verified with the seller

        # 3. price: total cost of ownership = price + 10 years of expenses, lower is better
        if l.price is not None:
            tco = l.price + 10 * (l.annual_expenses or 0)
            b["price"] = _clamp(1 - (tco - p_lo) / (p_hi - p_lo))
        else:
            b["price"] = 0.3

        # 4. freshness: new adverts first (1.0 today -> 0 after 90 days)
        d = l.days_online
        b["freshness"] = _clamp(1 - d / 90) if d is not None else 0.4

        # 5. interest: high view counts = competition, act sooner
        b["interest"] = (l.views / max_views) if (l.views and max_views) else 0.3

        score = 100 * sum(w[k] * b[k] for k in w)
        out[l.id] = (round(score, 1), {k: round(v, 2) for k, v in b.items()})
    return out


def sort_by_priority(listings: List[Listing], scores: Dict[str, Tuple[float, dict]]) -> List[Listing]:
    return sorted(listings, key=lambda l: scores.get(l.id, (0, {}))[0], reverse=True)


def median_price_per_m2(listings: List[Listing]) -> Optional[float]:
    vals = [l.price / l.surface_m2 for l in listings if l.price and l.surface_m2]
    return round(statistics.median(vals)) if vals else None
