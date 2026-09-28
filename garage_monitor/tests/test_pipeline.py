import os

import pytest

from garage_agent.agent import Agent
from garage_agent.config import load_config
from garage_agent.demo import sample_listings
from garage_agent.report import market_stats


@pytest.fixture
def cfg(tmp_path):
    c = load_config()
    c["data_dir"] = str(tmp_path)
    c["email"]["dry_run"] = True
    c["home"]["use_osrm"] = False
    return c


def test_end_to_end(cfg):
    agent = Agent(cfg)
    res = agent.scan(sample_listings())
    kept = res["kept"]
    reasons = {l.title: why for l, why in res["rejected"]}

    # hard filters
    assert any("Lambrate" in t for t in reasons), "far-away box must be rejected"
    assert any("Pisacane" in t for t in reasons), "4.3 m long box must be rejected"
    assert any("Buenos Aires" in t and "stretto" in why for t, why in reasons.items()), "2.10 m wide box must be rejected"
    assert any("AFFITTO" in t for t in reasons), "rental must be rejected"

    # priority: closest, widest, cheapest come first
    titles = [l.title for l in kept]
    assert titles[0].startswith(("Box singolo", "Box auto Via Morgagni")), titles
    assert all(l.walk_minutes is not None and l.walk_minutes <= 11.5 for l in kept)

    # parsed values from text
    plinio = next(l for l in kept if "Plinio" in l.title)
    assert (plinio.length_m, plinio.width_m) == (5.2, 2.6)
    assert plinio.annual_expenses == 240
    morgagni = next(l for l in kept if "Morgagni" in l.title)
    assert morgagni.annual_expenses == 360
    melzo = next(l for l in kept if "Porta Venezia" in l.title)
    assert melzo.price == 27000 and melzo.published is not None and melzo.contact_phone

    # persistence and notification bookkeeping
    assert len(res["new"]) == len(kept)
    assert agent.store.unnotified() == []          # dry-run still marks as notified
    assert os.listdir(os.path.join(cfg["data_dir"], "outbox"))

    # second scan with one listing gone -> marked inactive, no new e-mail
    second = [l for l in sample_listings() if "Morgagni" not in l.title]
    res2 = agent.scan(second)
    assert res2["new"] == [] and len(res2["removed"]) == 1
    assert agent.monthly(force=True) is False      # dry run -> not sent, but generated
    stats = market_stats(agent.store)
    assert stats["active"] == len(kept) - 1
