"""Registry of portal adapters. Each returns a list of Listing objects."""
from __future__ import annotations

import logging
from typing import Callable, Dict, List

from ..models import Listing
from . import casa, generic, idealista, immobiliare, subito
from .base import Fetcher

log = logging.getLogger(__name__)

BUILTIN: Dict[str, Callable] = {
    "immobiliare": immobiliare.search,
    "idealista": idealista.search,
    "casa": casa.search,
    "subito": subito.search,
}


def run_all(cfg: dict) -> List[Listing]:
    """Run every enabled source; one failing portal never stops the others."""
    results: List[Listing] = []
    fetcher = Fetcher(delay=cfg.get("request_delay_s", 2.0), proxies=cfg.get("proxies"))
    for name, sc in cfg["sources"].items():
        if not sc.get("enabled", True):
            continue
        try:
            if sc.get("adapter", name) == "generic":
                found = generic.search(cfg, name, fetcher)
            elif name in BUILTIN:
                found = BUILTIN[name](cfg, fetcher)
            else:
                log.warning("unknown source %s (no adapter) - skipped", name)
                continue
            log.info("[%s] %d listings", name, len(found))
            results.extend(found)
        except Exception:
            log.exception("[%s] adapter crashed", name)
    return results
