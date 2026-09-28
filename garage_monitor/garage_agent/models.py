from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional


@dataclass
class Listing:
    """A single garage / car-spot advertisement, normalised across portals."""

    source: str                       # e.g. "immobiliare", "idealista"
    url: str
    title: str = ""
    description: str = ""
    price: Optional[float] = None     # EUR
    annual_expenses: Optional[float] = None  # EUR / year (condominium fees etc.)
    length_m: Optional[float] = None
    width_m: Optional[float] = None
    surface_m2: Optional[float] = None
    kind: str = "unknown"             # "box" | "posto_auto" | "unknown"
    address: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    distance_m: Optional[float] = None   # walking distance from home
    walk_minutes: Optional[float] = None
    published: Optional[date] = None
    views: Optional[int] = None
    interest: Optional[int] = None     # saves / favourites / contacts, if exposed
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    agency: str = ""
    raw: dict = field(default_factory=dict)

    # ---- derived -----------------------------------------------------------
    @property
    def id(self) -> str:
        """Stable id: portal + canonical URL."""
        key = f"{self.source}|{self.url.split('?')[0].rstrip('/')}"
        return hashlib.sha1(key.encode()).hexdigest()[:16]

    @property
    def days_online(self) -> Optional[int]:
        if not self.published:
            return None
        return max(0, (date.today() - self.published).days)

    @property
    def contact(self) -> str:
        parts = [p for p in (self.agency or self.contact_name, self.contact_phone, self.contact_email) if p]
        return " · ".join(parts) if parts else "vedi annuncio"

    @property
    def dimensions(self) -> str:
        if self.length_m and self.width_m:
            return f"{self.length_m:.2f} × {self.width_m:.2f} m"
        if self.surface_m2:
            return f"{self.surface_m2:.0f} m²"
        return "n.d."

    def to_row(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        d["published"] = self.published.isoformat() if self.published else None
        d["days_online"] = self.days_online
        d.pop("raw", None)
        return d

    @staticmethod
    def from_row(row: dict) -> "Listing":
        row = dict(row)
        for k in ("id", "days_online", "first_seen", "last_seen", "active", "score", "score_breakdown", "notified"):
            row.pop(k, None)
        if row.get("published"):
            try:
                row["published"] = datetime.fromisoformat(row["published"]).date()
            except ValueError:
                row["published"] = None
        row.setdefault("raw", {})
        return Listing(**row)
