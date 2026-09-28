"""Command line entry point.

  python -m garage_agent run            # run forever (daily scans, monthly report)
  python -m garage_agent scan           # one scan now, e-mail if new opportunities
  python -m garage_agent monthly        # send the monthly report now
  python -m garage_agent demo           # offline demo with sample adverts (no network, no e-mail)
  python -m garage_agent list           # print the current ranked table in the terminal
  python -m garage_agent test-email     # send a test e-mail to check SMTP credentials
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from .config import load_config, load_dotenv


def _setup_logging(data_dir: str, verbose: bool):
    os.makedirs(data_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(os.path.join(data_dir, "agent.log"), encoding="utf-8")],
    )


def main(argv=None):
    load_dotenv()
    ap = argparse.ArgumentParser(prog="garage_agent", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["run", "scan", "monthly", "demo", "list", "test-email"])
    ap.add_argument("-c", "--config", default=None, help="path to config.yaml")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--no-immediate", action="store_true", help="with `run`: wait for the schedule instead of scanning now")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    _setup_logging(cfg["data_dir"], args.verbose)
    from .agent import Agent   # after logging setup

    if args.command == "demo":
        from .demo import sample_listings
        cfg["email"]["dry_run"] = True
        cfg["data_dir"] = os.path.join(cfg["data_dir"], "demo")
        os.makedirs(cfg["data_dir"], exist_ok=True)
        cfg["home"]["use_osrm"] = False
        agent = Agent(cfg)
        res = agent.scan(sample_listings())
        agent.monthly(force=True)
        _print_table(agent)
        print(f"\nDemo complete: {res['scraped']} adverts, {len(res['kept'])} kept, {len(res['rejected'])} rejected.")
        print(f"E-mails were NOT sent (demo) - HTML copies are in {os.path.join(cfg['data_dir'], 'outbox')}")
        return

    agent = Agent(cfg)
    if args.command == "run":
        agent.run_forever(run_immediately=not args.no_immediate)
    elif args.command == "scan":
        res = agent.scan()
        _print_table(agent)
        print(f"\n{res['scraped']} adverts scraped, {len(res['kept'])} match, {len(res['new'])} new, {len(res['removed'])} removed.")
    elif args.command == "monthly":
        ok = agent.monthly(force=True)
        print("monthly report sent" if ok else "monthly report NOT sent (see log / data/outbox)")
    elif args.command == "list":
        _print_table(agent)
    elif args.command == "test-email":
        from .mailer import send_email
        ok = send_email(cfg, "[Box Viale Abruzzi] Test e-mail", "<p>Configurazione SMTP funzionante ✅</p>")
        print("sent" if ok else "NOT sent - check SMTP_* variables in .env")
        sys.exit(0 if ok else 1)


def _print_table(agent):
    rows = agent.store.active_rows()
    if not rows:
        print("no active listings")
        return
    print(f"\n{'#':>2} {'score':>5} {'walk':>6} {'dims':>14} {'price':>9} {'exp/y':>6} {'days':>4} {'source':<11} title")
    for i, r in enumerate(rows, 1):
        walk = f"{r['walk_minutes']:.0f} min" if r["walk_minutes"] is not None else "  ?   "
        dims = f"{r['length_m']:.2f}x{r['width_m']:.2f}" if r["length_m"] and r["width_m"] else (f"{r['surface_m2']:.0f} m2" if r["surface_m2"] else "?")
        price = f"{r['price']:,.0f}" if r["price"] else "?"
        exp = f"{r['annual_expenses']:.0f}" if r["annual_expenses"] else "?"
        days = "?"
        if r["published"]:
            from datetime import date
            days = str((date.today() - date.fromisoformat(r["published"])).days)
        print(f"{i:>2} {r['score']:>5} {walk:>6} {dims:>14} {price:>9} {exp:>6} {days:>4} {r['source']:<11} {r['title'][:60]}")


if __name__ == "__main__":
    main()
