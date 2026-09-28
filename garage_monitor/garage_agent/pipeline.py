"""One monitoring cycle: scrape -> geolocate -> filter -> score -> persist -> notify."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional, Tuple

from . import geo
from .models import Listing
from .parsing import enrich_from_text
from .scoring import passes_hard_filters, score_all, sort_by_priority
from .scrapers import run_all
from .storage import Store

log = logging.getLogger(__name__)


def home_coords(cfg: dict, geocoder: geo.Geocoder) -> Tuple[float, float]:
    h = cfg["home"]
    if h.get("lat") and h.get("lon"):
        return float(h["lat"]), float(h["lon"])
    c = geocoder.geocode(h["address"])
    if c:
        return c
    log.warning("home geocoding failed - using fallback coordinates %s", geo.HOME_FALLBACK)
    return geo.HOME_FALLBACK


def locate(listings: List[Listing], cfg: dict, geocoder: geo.Geocoder, home: Tuple[float, float]) -> None:
    use_osrm = cfg["home"].get("use_osrm", True)
    for l in listings:
        if (l.lat is None or l.lon is None) and l.address:
            c = geocoder.geocode(l.address)
            if c:
                l.lat, l.lon = c
        if l.lat is not None and l.lon is not None:
            # skip the routing call for anything obviously outside the perimeter
            straight = geo.haversine_m(*home, l.lat, l.lon)
            limit_m = cfg["home"]["max_walk_minutes"] * geo.WALK_SPEED_M_PER_MIN * 1.5
            l.distance_m = geo.walking_distance_m(home, (l.lat, l.lon), use_osrm) if straight <= limit_m else straight * geo.DETOUR_FACTOR
            l.walk_minutes = round(geo.walk_minutes(l.distance_m), 1)
            l.distance_m = round(l.distance_m)


def process(listings: List[Listing], cfg: dict, geocoder: geo.Geocoder) -> Tuple[List[Listing], dict, List[Tuple[Listing, str]]]:
    home = home_coords(cfg, geocoder)
    for l in listings:
        enrich_from_text(l)          # idempotent; scrapers already did it, injected lists may not have
    locate(listings, cfg, geocoder, home)
    kept, rejected = [], []
    for l in listings:
        ok, why = passes_hard_filters(l, cfg)
        (kept if ok else rejected).append((l, why) if not ok else l)
    scores = score_all(kept, cfg)
    return sort_by_priority(kept, scores), scores, rejected


def run_cycle(cfg: dict, store: Store, listings: Optional[List[Listing]] = None) -> dict:
    """Full cycle. `listings` can be injected (tests / demo) instead of scraping."""
    started = datetime.now()
    geocoder = geo.Geocoder(os.path.join(cfg["data_dir"], "geocache.json"))
    raw = listings if listings is not None else run_all(cfg)
    ranked, scores, rejected = process(raw, cfg, geocoder)
    new, removed = store.upsert(ranked, scores)
    store.log_run(started, len(raw), len(new), len(removed),
                  notes="; ".join(f"{l.source}: {why}" for l, why in rejected[:20]))
    log.info("cycle done: %d scraped, %d kept, %d new, %d removed, %d rejected",
             len(raw), len(ranked), len(new), len(removed), len(rejected))
    return {"started": started, "scraped": len(raw), "kept": ranked, "scores": scores,
            "new": new, "removed": removed, "rejected": rejected}
