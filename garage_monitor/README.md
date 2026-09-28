# garage-monitor — box / posto auto near Viale Abruzzi 51, Milano

An autonomous Python agent that, **once a day**, scans the main Italian real-estate portals
(immobiliare.it, idealista.it, casa.it, subito.it) and online bulletins (secondamanoitalia.it,
bakeca.it, plus any site you add), keeps only garages / car spots for sale that are

* within **10 minutes on foot** of Viale Abruzzi 51 (street distance, not straight line),
* at least **4.50 m long** and **2.15 m wide** (2.50 m or wider is rewarded),

ranks them by **distance › size › price › days online › interest (views)**, stores everything
in a local SQLite database and

* **e-mails `alexmrt@icloud.com` every time a new opportunity appears** (with the full ranked table), and
* **e-mails a monthly market report** (KPIs, trend narrative, month-by-month statistics, ranked list).

Each row of the table carries: title + link, portal, walk time and street distance, dimensions,
price, annual expenses, days online, views, contact (agency / name / phone / e-mail) and a
description excerpt. Items whose width is not stated are kept but flagged *"da verificare"* —
most adverts don't print measurements, so a phone call is often required.

---

## 1. Quick start (5 minutes)

```bash
git clone <this folder>  # or unzip garage_monitor.zip
cd garage_monitor
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env         # then edit .env with the SMTP credentials (see §3)
python -m garage_agent demo  # offline demo with sample adverts, no network, no e-mail
python -m garage_agent test-email
python -m garage_agent scan  # one real scan now
python -m garage_agent run   # run forever: scan daily at 08:30, monthly report on the 1st
```

`demo` prints the ranked table and writes the two e-mails it *would* send to
`data/demo/outbox/*.html` so you can open them in a browser.

## 2. Commands

| command | what it does |
|---|---|
| `run` | daemon: scans immediately, then every day at `schedule.daily_at`; sends the monthly report on the first run on/after `schedule.monthly_day`. `--no-immediate` waits for the schedule. |
| `scan` | one scan, e-mail if there is anything new, prints the ranked table |
| `monthly` | send the monthly market report now |
| `list` | print the current ranked table from the database |
| `demo` | offline end-to-end run with synthetic adverts |
| `test-email` | send a test message to verify SMTP |

Add `-v` for debug logging. Logs go to stdout and `data/agent.log`.

## 3. E-mail (iCloud)

The recipient is `alexmrt@icloud.com` (config.yaml → `email.recipient`). The sender account is
whatever you put in `.env`:

```
SMTP_HOST=smtp.mail.me.com
SMTP_PORT=587
SMTP_USER=your_apple_id@icloud.com
SMTP_PASSWORD=app-specific-password     # appleid.apple.com → Sign-In and Security → App-Specific Passwords
SMTP_SENDER=your_apple_id@icloud.com
```

Gmail works the same way (`smtp.gmail.com`, port 587, app password). Every e-mail is also archived
to `data/outbox/` as HTML; if SMTP is not configured the agent keeps working and only archives.

## 4. Running it 24/7

**Docker (recommended):**
```bash
docker compose up -d --build       # uses .env and mounts ./data
docker compose logs -f
```

**systemd (Linux server / Raspberry Pi):** edit paths in `garage-monitor.service`, then
```bash
sudo cp garage-monitor.service /etc/systemd/system/
sudo systemctl enable --now garage-monitor
```

**macOS:** `nohup python -m garage_agent run &` or a launchd plist calling the same command.

The daemon survives crashes of individual portals (each adapter is isolated) and restarts of the
host (state is in `data/garage.sqlite`; nothing is re-notified).

## 5. Configuration (`config.yaml`)

| key | meaning |
|---|---|
| `home.address` / `lat` / `lon` | reference point; geocoded via OpenStreetMap unless pinned |
| `home.max_walk_minutes`, `tolerance` | perimeter (10 min) and slack (1.15 → up to 11.5 min kept) |
| `home.use_osrm` | true = real pedestrian routing through OSRM; otherwise straight line × 1.3 |
| `requirements.*` | min length 4.5 m, min width 2.15 m, ideal width 2.5 m, price sanity bounds |
| `weights.*` | scoring weights (distance 0.40, size 0.28, price 0.20, freshness 0.07, interest 0.05) |
| `schedule.daily_at`, `monthly_day` | when to scan / report (machine local time; Docker image uses Europe/Rome) |
| `sources.*` | portals and their search URLs (see below) |

### Search URLs — please verify them once

Portals change their URL schemes and zone names now and then. Each `urls:` entry is simply a
search-results page: open it in a browser, adjust the zone/sorting as you like (the 10-minute
perimeter is enforced by the agent afterwards, so a wider search is fine) and paste the final URL
back into `config.yaml`. The zones around Viale Abruzzi are *Città Studi*, *Loreto*,
*Buenos Aires / Porta Venezia* and *Piazzale Bacone / Argonne*.

To add another site (agency website, another bulletin), copy the `generic` template at the bottom
of `config.yaml` and give it the CSS selector of an advert card and of its link.

### Scoring

Each criterion is normalised 0–1 and weighted in the client's order of importance:

1. **distance** – 1.0 at the door, 0 at 10 minutes (unknown address → 0.35)
2. **size** – width drives it (2.15 m → 0.5, ≥ 2.5 m → 1.0); length adds up to 20 %; surface-only or
   unknown dimensions score low and are flagged for verification
3. **price** – total cost of ownership (price + 10 years of expenses), relative to the current market range
4. **freshness** – 1.0 today, 0 after 90 days
5. **interest** – views relative to the most-viewed listing (higher = more competition, act sooner)

Rentals, motorbike spots, boxes that are too short/narrow or too far are discarded before scoring
(reasons are logged in the `runs` table).

## 6. Bot protection & good citizenship

* Requests are throttled (`request_delay_s`) and rotate a browser User-Agent.
* **idealista.it** (DataDome) and sometimes **immobiliare.it** may answer 403/429 to servers in data
  centres. Running from a home connection normally works; otherwise set `proxies:` in `config.yaml`
  or disable the source. A failing portal never blocks the others — the run log says which ones
  returned nothing.
* Geocoding uses OpenStreetMap Nominatim at ≤ 1 request/second with a persistent cache
  (`data/geocache.json`), well within its usage policy.
* Check each portal's terms of service; this tool is intended for personal, low-volume use.

## 7. Project layout

```
garage_agent/
  agent.py        daemon loop, alert + monthly scheduling
  pipeline.py     scrape → geolocate → filter → score → persist
  scoring.py      hard filters and weighted priority score
  parsing.py      regexes for dimensions, prices, expenses, dates, views (Italian adverts)
  geo.py          Nominatim geocoder (cached), OSRM walking distance, haversine fallback
  storage.py      SQLite (listings, price history, runs, monthly reports)
  report.py       HTML e-mails: new-opportunity alert, monthly market report with trends
  mailer.py       SMTP + outbox archive
  demo.py         synthetic adverts for the demo/tests
  scrapers/       immobiliare, idealista, casa, subito, generic (bulletins) + registry
tests/            pytest suite (parsers, scrapers with canned HTML, end-to-end pipeline)
config.yaml       all settings           .env.example  SMTP secrets template
Dockerfile, docker-compose.yml, garage-monitor.service
```

Run the tests with `pip install pytest && python -m pytest -q tests`.
