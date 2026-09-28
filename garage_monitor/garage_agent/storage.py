"""SQLite persistence: current listings, price history, run log."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime
from typing import Iterable, List, Optional

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    source TEXT, url TEXT, title TEXT, description TEXT,
    price REAL, annual_expenses REAL, length_m REAL, width_m REAL, surface_m2 REAL,
    kind TEXT, address TEXT, lat REAL, lon REAL, distance_m REAL, walk_minutes REAL,
    published TEXT, views INTEGER, interest INTEGER,
    contact_name TEXT, contact_phone TEXT, contact_email TEXT, agency TEXT,
    first_seen TEXT, last_seen TEXT, active INTEGER DEFAULT 1,
    score REAL, score_breakdown TEXT, notified INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS price_history (
    listing_id TEXT, seen TEXT, price REAL,
    PRIMARY KEY (listing_id, seen)
);
CREATE TABLE IF NOT EXISTS runs (
    started TEXT PRIMARY KEY, finished TEXT, n_found INTEGER, n_new INTEGER, n_removed INTEGER, notes TEXT
);
CREATE TABLE IF NOT EXISTS monthly_reports (month TEXT PRIMARY KEY, sent TEXT);
"""

COLS = ["source", "url", "title", "description", "price", "annual_expenses", "length_m", "width_m",
        "surface_m2", "kind", "address", "lat", "lon", "distance_m", "walk_minutes", "published",
        "views", "interest", "contact_name", "contact_phone", "contact_email", "agency"]


class Store:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # ---- upsert --------------------------------------------------------------
    def upsert(self, listings: Iterable[Listing], scores: dict) -> tuple[list[Listing], list[str]]:
        """Insert/update listings seen in this run. Returns (new_listings, removed_ids)."""
        now = datetime.now().isoformat(timespec="seconds")
        today = date.today().isoformat()
        seen_ids, new = set(), []
        for l in listings:
            seen_ids.add(l.id)
            row = l.to_row()
            sc = scores.get(l.id, (None, {}))
            existing = self.conn.execute("SELECT id, price, notified FROM listings WHERE id=?", (l.id,)).fetchone()
            vals = [row[c] for c in COLS]
            if existing is None:
                self.conn.execute(
                    f"INSERT INTO listings (id,{','.join(COLS)},first_seen,last_seen,active,score,score_breakdown,notified)"
                    f" VALUES (?,{','.join('?'*len(COLS))},?,?,1,?,?,0)",
                    [l.id, *vals, now, now, sc[0], json.dumps(sc[1])])
                new.append(l)
            else:
                self.conn.execute(
                    f"UPDATE listings SET {','.join(c+'=?' for c in COLS)}, last_seen=?, active=1, score=?, score_breakdown=? WHERE id=?",
                    [*vals, now, sc[0], json.dumps(sc[1]), l.id])
            if l.price is not None:
                self.conn.execute("INSERT OR IGNORE INTO price_history VALUES (?,?,?)", (l.id, today, l.price))
        # listings not seen in this run are considered withdrawn/sold
        removed = [r["id"] for r in self.conn.execute("SELECT id FROM listings WHERE active=1")
                   if r["id"] not in seen_ids]
        if removed:
            self.conn.executemany("UPDATE listings SET active=0, last_seen=? WHERE id=?", [(now, i) for i in removed])
        self.conn.commit()
        return new, removed

    def mark_notified(self, ids: Iterable[str]):
        self.conn.executemany("UPDATE listings SET notified=1 WHERE id=?", [(i,) for i in ids])
        self.conn.commit()

    def unnotified(self) -> List[Listing]:
        return [Listing.from_row(r) for r in self.conn.execute(
            "SELECT * FROM listings WHERE active=1 AND notified=0")]

    def active(self) -> List[Listing]:
        return [Listing.from_row(r) for r in self.conn.execute(
            "SELECT * FROM listings WHERE active=1 ORDER BY score DESC")]

    def active_rows(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM listings WHERE active=1 ORDER BY score DESC")]

    def all_rows(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM listings")]

    def price_history(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM price_history ORDER BY seen")]

    def log_run(self, started: datetime, n_found: int, n_new: int, n_removed: int, notes: str = ""):
        self.conn.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?)",
                          (started.isoformat(timespec="seconds"), datetime.now().isoformat(timespec="seconds"),
                           n_found, n_new, n_removed, notes))
        self.conn.commit()

    def runs(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM runs ORDER BY started")]

    def monthly_sent(self, month: str) -> bool:
        return self.conn.execute("SELECT 1 FROM monthly_reports WHERE month=?", (month,)).fetchone() is not None

    def mark_monthly_sent(self, month: str):
        self.conn.execute("INSERT OR REPLACE INTO monthly_reports VALUES (?,?)", (month, datetime.now().isoformat()))
        self.conn.commit()
