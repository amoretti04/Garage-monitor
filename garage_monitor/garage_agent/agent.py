"""The long-running agent: one scan per day at the configured hour, alert e-mail whenever
something new appears, monthly market report on the configured day of the month."""
from __future__ import annotations

import logging
import os
import signal
import time
from datetime import date, datetime, timedelta
from typing import Optional

from .config import load_config
from .mailer import send_email
from .pipeline import run_cycle
from .report import monthly_email, new_opportunities_email
from .storage import Store

log = logging.getLogger(__name__)


class Agent:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.store = Store(os.path.join(cfg["data_dir"], "garage.sqlite"))
        self._stop = False
        signal.signal(signal.SIGTERM, self._on_stop)
        signal.signal(signal.SIGINT, self._on_stop)

    def _on_stop(self, *_):
        log.info("stop requested")
        self._stop = True

    # ------------------------------------------------------------------ steps
    def scan(self, listings=None) -> dict:
        res = run_cycle(self.cfg, self.store, listings)
        self.notify_new()
        return res

    def notify_new(self) -> bool:
        pending = self.store.unnotified()
        if not pending:
            log.info("no new opportunities to notify")
            return False
        active = self.store.active()
        scores = {l.id: (r["score"], {}) for l, r in zip(active, self.store.active_rows())}
        subject, body = new_opportunities_email(pending, active, scores, self.cfg)
        sent = send_email(self.cfg, subject, body)
        if sent or self.cfg["email"].get("dry_run"):
            self.store.mark_notified([l.id for l in pending])
        return sent

    def monthly(self, force: bool = False) -> bool:
        key = date.today().strftime("%Y-%m")
        if self.store.monthly_sent(key) and not force:
            return False
        active = self.store.active()
        scores = {l.id: (r["score"], {}) for l, r in zip(active, self.store.active_rows())}
        subject, body = monthly_email(self.store, active, scores, self.cfg)
        sent = send_email(self.cfg, subject, body)
        if sent or self.cfg["email"].get("dry_run"):
            self.store.mark_monthly_sent(key)
        return sent

    # ------------------------------------------------------------------- loop
    def _next_run(self, now: datetime) -> datetime:
        hh, mm = map(int, self.cfg["schedule"]["daily_at"].split(":"))
        nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        return nxt

    def run_forever(self, run_immediately: bool = True):
        log.info("agent started - daily scan at %s, monthly report on day %s",
                 self.cfg["schedule"]["daily_at"], self.cfg["schedule"]["monthly_day"])
        if run_immediately:
            self._tick()
        while not self._stop:
            nxt = self._next_run(datetime.now())
            log.info("next scan at %s", nxt.strftime("%Y-%m-%d %H:%M"))
            while not self._stop and datetime.now() < nxt:
                time.sleep(min(60, max(1, (nxt - datetime.now()).total_seconds())))
            if not self._stop:
                self._tick()

    def _tick(self):
        try:
            self.scan()
        except Exception:
            log.exception("scan failed - will retry at next schedule")
        try:
            if date.today().day >= int(self.cfg["schedule"]["monthly_day"]):
                self.monthly()
        except Exception:
            log.exception("monthly report failed")


def build(config_path: Optional[str] = None) -> Agent:
    return Agent(load_config(config_path))
