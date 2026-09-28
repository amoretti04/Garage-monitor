"""Geocoding (Nominatim / OpenStreetMap, cached) and walking-distance estimates."""
from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from typing import Optional, Tuple

import requests

log = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/foot/{lon1},{lat1};{lon2},{lat2}?overview=false"
WALK_SPEED_M_PER_MIN = 80.0      # ~4.8 km/h, the usual urban planning figure
DETOUR_FACTOR = 1.30             # straight line -> street network (Milan grid)

# Approximate fallback if geocoding is unavailable (Viale Abruzzi 51, 20131 Milano)
HOME_FALLBACK = (45.4783, 9.2143)


class Geocoder:
    def __init__(self, cache_path: str, user_agent: str = "garage-monitor/1.0 (personal use)"):
        self.cache_path = cache_path
        self.ua = user_agent
        self._cache: dict = {}
        self._last_call = 0.0
        if os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=1)

    def geocode(self, address: str, city: str = "Milano") -> Optional[Tuple[float, float]]:
        if not address:
            return None
        q = normalise_address(address, city)
        if q in self._cache:
            v = self._cache[q]
            return tuple(v) if v else None
        # Nominatim usage policy: max 1 request / second, identify yourself
        wait = 1.1 - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get(NOMINATIM, params={"q": q, "format": "json", "limit": 1, "countrycodes": "it"},
                             headers={"User-Agent": self.ua}, timeout=20)
            self._last_call = time.time()
            r.raise_for_status()
            data = r.json()
            res = (float(data[0]["lat"]), float(data[0]["lon"])) if data else None
        except Exception as e:  # network / rate-limit: don't cache failures
            log.warning("geocode failed for %r: %s", q, e)
            return None
        self._cache[q] = list(res) if res else None
        self._save()
        return res


def normalise_address(address: str, city: str = "Milano") -> str:
    a = re.sub(r"\s+", " ", address).strip(" ,")
    if city.lower() not in a.lower():
        a = f"{a}, {city}"
    if "ital" not in a.lower():
        a += ", Italia"
    return a


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def walking_distance_m(home: Tuple[float, float], target: Tuple[float, float], use_osrm: bool = True) -> float:
    """Street walking distance in metres; OSRM if reachable, else haversine x detour factor."""
    if use_osrm:
        try:
            url = OSRM.format(lat1=home[0], lon1=home[1], lat2=target[0], lon2=target[1])
            r = requests.get(url, timeout=10, headers={"User-Agent": "garage-monitor/1.0"})
            if r.ok:
                routes = r.json().get("routes") or []
                if routes:
                    return float(routes[0]["distance"])
        except Exception as e:
            log.debug("OSRM unavailable (%s) - falling back to haversine", e)
    return haversine_m(*home, *target) * DETOUR_FACTOR


def walk_minutes(distance_m: float) -> float:
    return distance_m / WALK_SPEED_M_PER_MIN
