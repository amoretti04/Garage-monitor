"""HTML e-mail bodies: new-opportunity alerts and the monthly market report."""
from __future__ import annotations

import html
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import List, Optional

from .models import Listing
from .storage import Store

CSS = """
<style>
 body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1c1c1e;font-size:14px}
 table{border-collapse:collapse;width:100%;font-size:12.5px}
 th{background:#f2f2f7;text-align:left;padding:6px 8px;border-bottom:2px solid #d1d1d6;white-space:nowrap}
 td{padding:6px 8px;border-bottom:1px solid #e5e5ea;vertical-align:top}
 tr:nth-child(even) td{background:#fafafa}
 .score{font-weight:700;color:#0a84ff}
 .new{background:#e8f8ee !important}
 .warn{color:#b25000}
 .muted{color:#8e8e93}
 h2{margin-top:28px}
 .kpi{display:inline-block;min-width:150px;margin:6px 12px 6px 0;padding:8px 12px;background:#f2f2f7;border-radius:8px}
 .kpi b{display:block;font-size:20px}
</style>"""


def _e(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def _eur(v: Optional[float]) -> str:
    return f"{v:,.0f} €".replace(",", ".") if v else "n.d."


def _desc(l: Listing, n: int = 220) -> str:
    d = (l.description or "").strip()
    return _e(d[:n] + ("…" if len(d) > n else ""))


def table(listings: List[Listing], scores: dict, new_ids: set | None = None) -> str:
    new_ids = new_ids or set()
    rows = []
    for i, l in enumerate(listings, 1):
        sc, br = scores.get(l.id, (None, {}))
        dist = f"{l.walk_minutes:.0f} min ({l.distance_m:.0f} m)" if l.walk_minutes is not None else '<span class="warn">da verificare</span>'
        dims = _e(l.dimensions)
        if l.width_m is None:
            dims += ' <span class="warn">(larghezza da verificare)</span>'
        flag = " NUOVO" if l.id in new_ids else ""
        rows.append(f"""
<tr class="{'new' if flag else ''}">
 <td>{i}</td>
 <td class="score">{sc if sc is not None else ''}</td>
 <td><a href="{_e(l.url)}">{_e(l.title or l.url)}</a><b>{flag}</b><br><span class="muted">{_e(l.source)} · {_e(l.kind)}</span></td>
 <td>{dist}<br><span class="muted">{_e(l.address)}</span></td>
 <td>{dims}</td>
 <td>{_eur(l.price)}</td>
 <td>{_eur(l.annual_expenses) if l.annual_expenses else 'n.d.'}</td>
 <td>{l.days_online if l.days_online is not None else 'n.d.'}</td>
 <td>{l.views if l.views is not None else 'n.d.'}</td>
 <td>{_e(l.contact)}</td>
 <td>{_desc(l)}</td>
</tr>""")
    if not rows:
        return "<p><i>Nessuna opportunità attiva al momento.</i></p>"
    return f"""
<table>
<tr><th>#</th><th>Punteggio</th><th>Annuncio</th><th>Distanza a piedi</th><th>Dimensioni</th>
<th>Prezzo</th><th>Spese/anno</th><th>Giorni online</th><th>Visite</th><th>Contatto</th><th>Descrizione</th></tr>
{''.join(rows)}
</table>
<p class="muted">Punteggio 0-100: distanza (40%) &gt; dimensioni (28%) &gt; prezzo (20%) &gt; recenza (7%) &gt; interesse (5%).
Le voci "da verificare" indicano dati non dichiarati nell'annuncio: chiedere al venditore.</p>"""


def new_opportunities_email(new: List[Listing], all_active: List[Listing], scores: dict, cfg: dict) -> tuple[str, str]:
    n = len(new)
    subject = f"[Box Viale Abruzzi] {n} nuov{'a opportunità' if n == 1 else 'e opportunità'} – {date.today():%d/%m/%Y}"
    top = sorted(new, key=lambda l: scores.get(l.id, (0,))[0], reverse=True)
    body = f"""<html><head>{CSS}</head><body>
<h1>Nuove opportunità ({n})</h1>
<p>Box / posti auto in vendita entro {cfg['home']['max_walk_minutes']} minuti a piedi da {_e(cfg['home']['address'])},
con lunghezza ≥ {cfg['requirements']['min_length_m']} m e larghezza ≥ {cfg['requirements']['min_width_m']} m
(ideale ≥ {cfg['requirements']['ideal_width_m']} m).</p>
{table(top, scores, {l.id for l in new})}
<h2>Classifica completa ({len(all_active)} annunci attivi)</h2>
{table(all_active, scores, {l.id for l in new})}
<p class="muted">Generato automaticamente da garage-monitor il {datetime.now():%d/%m/%Y %H:%M}.</p>
</body></html>"""
    return subject, body


# ---------------------------------------------------------------------------
def _month_key(iso: str) -> str:
    return iso[:7]


def market_stats(store: Store) -> dict:
    """Per-month statistics from everything ever seen (active or not)."""
    rows = store.all_rows()
    hist = store.price_history()
    by_month: dict[str, dict] = defaultdict(lambda: {"prices": [], "ppm2": [], "new": 0, "removed": 0, "days": []})
    for r in rows:
        fm = _month_key(r["first_seen"])
        by_month[fm]["new"] += 1
        if r["price"]:
            by_month[fm]["prices"].append(r["price"])
            if r["surface_m2"]:
                by_month[fm]["ppm2"].append(r["price"] / r["surface_m2"])
        if not r["active"]:
            lm = _month_key(r["last_seen"])
            by_month[lm]["removed"] += 1
            try:
                d = (datetime.fromisoformat(r["last_seen"]) - datetime.fromisoformat(r["first_seen"])).days
                by_month[lm]["days"].append(d)
            except Exception:
                pass
    # price cuts observed
    cuts = 0
    last: dict[str, float] = {}
    for h in hist:
        if h["listing_id"] in last and h["price"] < last[h["listing_id"]]:
            cuts += 1
        last[h["listing_id"]] = h["price"]
    out = {}
    for m, v in sorted(by_month.items()):
        out[m] = {
            "new": v["new"], "removed": v["removed"],
            "median_price": statistics.median(v["prices"]) if v["prices"] else None,
            "median_ppm2": statistics.median(v["ppm2"]) if v["ppm2"] else None,
            "avg_days_to_sell": statistics.mean(v["days"]) if v["days"] else None,
        }
    return {"months": out, "price_cuts": cuts, "active": sum(1 for r in rows if r["active"]), "total_seen": len(rows)}


def trend_narrative(stats: dict, active: List[Listing]) -> str:
    months = list(stats["months"].items())
    if not months:
        return "<p>Non ci sono ancora dati sufficienti per descrivere l'andamento del mercato.</p>"
    cur_m, cur = months[-1]
    prev = months[-2][1] if len(months) > 1 else None
    parts = []
    parts.append(f"Nel mese {cur_m} sono comparsi <b>{cur['new']}</b> nuovi annunci idonei e ne sono usciti <b>{cur['removed']}</b> "
                 f"(venduti o ritirati). Attualmente ci sono <b>{stats['active']}</b> opportunità attive.")
    if cur["median_price"]:
        s = f"Il prezzo mediano richiesto per i nuovi annunci è <b>{_eur(cur['median_price'])}</b>"
        if cur["median_ppm2"]:
            s += f" (≈ {_eur(cur['median_ppm2'])}/m²)"
        if prev and prev.get("median_price"):
            delta = (cur["median_price"] - prev["median_price"]) / prev["median_price"] * 100
            direction = "in aumento" if delta > 2 else "in calo" if delta < -2 else "stabile"
            s += f", {direction} del {abs(delta):.1f}% rispetto al mese precedente ({_eur(prev['median_price'])})"
        parts.append(s + ".")
    if cur["avg_days_to_sell"]:
        parts.append(f"Gli annunci usciti dal mercato sono rimasti online in media <b>{cur['avg_days_to_sell']:.0f} giorni</b>"
                     + (": il mercato assorbe rapidamente l'offerta." if cur["avg_days_to_sell"] < 30 else "."))
    if stats["price_cuts"]:
        parts.append(f"Sono stati osservati <b>{stats['price_cuts']}</b> ribassi di prezzo su annunci monitorati: "
                     "un segnale di margine di trattativa.")
    wide = [l for l in active if l.width_m and l.width_m >= 2.5]
    if active:
        parts.append(f"Tra gli annunci attivi, <b>{len(wide)}</b> dichiarano una larghezza ≥ 2,5 m (l'obiettivo ideale); "
                     f"{sum(1 for l in active if l.width_m is None)} non dichiarano le misure e vanno verificati telefonicamente.")
    return "<p>" + " ".join(parts) + "</p>"


def _days(v: Optional[float]) -> str:
    return f"{v:.0f}" if v else "n.d."


def month_table(stats: dict) -> str:
    rows = "".join(
        f"<tr><td>{m}</td><td>{v['new']}</td><td>{v['removed']}</td><td>{_eur(v['median_price'])}</td>"
        f"<td>{_eur(v['median_ppm2']) if v['median_ppm2'] else 'n.d.'}</td>"
        f"<td>{_days(v['avg_days_to_sell'])}</td></tr>"
        for m, v in stats["months"].items())
    return f"""<table><tr><th>Mese</th><th>Nuovi annunci</th><th>Usciti</th><th>Prezzo mediano</th><th>€/m² mediano</th><th>Giorni medi online</th></tr>{rows}</table>"""


def monthly_email(store: Store, active: List[Listing], scores: dict, cfg: dict) -> tuple[str, str]:
    stats = market_stats(store)
    prices = [l.price for l in active if l.price]
    subject = f"[Box Viale Abruzzi] Report mensile mercato – {date.today():%B %Y}"
    body = f"""<html><head>{CSS}</head><body>
<h1>Report mensile – box e posti auto vicino a {_e(cfg['home']['address'])}</h1>
<div>
 <div class="kpi"><b>{len(active)}</b>opportunità attive</div>
 <div class="kpi"><b>{_eur(statistics.median(prices)) if prices else 'n.d.'}</b>prezzo mediano</div>
 <div class="kpi"><b>{_eur(min(prices)) if prices else 'n.d.'}</b>prezzo minimo</div>
 <div class="kpi"><b>{stats['total_seen']}</b>annunci monitorati in totale</div>
</div>
<h2>Andamento del mercato</h2>
{trend_narrative(stats, active)}
{month_table(stats)}
<h2>Opportunità attive in ordine di priorità</h2>
{table(active, scores)}
<p class="muted">Generato automaticamente da garage-monitor il {datetime.now():%d/%m/%Y %H:%M}.</p>
</body></html>"""
    return subject, body
