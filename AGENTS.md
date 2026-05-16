# AGENTS.md — Rental Monitor Scraper

## Project Overview

Monitors rental listings on **KV.ee** and **City24** (Estonian real estate sites), detects new/removed/price-changed listings via SQLite diff, and sends HTML email alerts. Runs as a systemd background service performing hourly checks.

**Tech**: Python 3, Playwright (headless Chromium), SQLite, smtplib, systemd.

---

## File Inventory

| File | Purpose |
|------|---------|
| `config.py` | Central configuration: search params, URLs, DB path, check interval, log dir |
| `scraper.py` | KV.ee scraper: Playwright browser + JSON API pagination, HTML regex parsing |
| `city24_scraper.py` | City24 scraper: Playwright browser + REST API, JSON parsing |
| `database.py` | SQLite storage, upsert, change detection (new/removed/price changed) |
| `monitor.py` | Orchestrator: runs both scrapers, merges results, detects changes, sends email |
| `service.py` | Daemon loop: hourly execution, logging, signal handling, graceful shutdown |
| `install-service.sh` | Bash script: installs systemd service for production deployment |
| `kv-monitor.service` | Systemd unit file: defines service startup, restart policy, env vars |
| `.env` | SMTP credentials, email config (not committed, per-environment) |
| `.env.development` | Dev overrides: sets `EMAIL_DISABLED=true` to skip email sending |
| `requirements.txt` | Python deps: playwright, python-dotenv, httpx |

---

## Detailed File Breakdown

### `config.py`

All constants and search parameters. No logic, just configuration.

**Key values:**
- `KV_SEARCH_PARAMS` — dict of KV.ee search filters (2-3 room, Tallinn/Kesklinn, bounding box)
- `CITY24_SEARCH_URL` — full API URL for City24 search (2-3 room, Tallinn bounding box)
- `KV_BASE_URL` / `KV_API_BASE_URL` — KV.ee web and API endpoints
- `CITY24_API_BASE` — City24 API base URL
- `DB_PATH` — `"data/listings.db"`
- `CHECK_INTERVAL_SECONDS` — 3600 (1 hour)
- `LOG_DIR` / `LOG_FILE` — `"logs"` / `"logs/service.log"`

---

### `scraper.py` (KV.ee)

Scrapes KV.ee using Playwright to fetch paginated JSON API data, then parses HTML snippets with regex.

**Key functions:**
- `scrape_all_pages()` — async entrypoint. Opens browser, navigates to KV.ee search, accepts cookies, then paginates through `/map?` API endpoint fetching 20 listings per page until exhausted. Returns flat list of listing dicts.
- `_parse_listings(data)` — parses API response dict. Extracts fields from `showObjects[]`, pulling URL, title, image, price, rooms, area, and date from HTML snippets via regex. Returns list of normalized listing dicts.
- `_build_api_url(params, offset)` — builds KV.ee API URL with offset for pagination.
- `_build_search_url(params)` — builds KV.ee search page URL for initial browser navigation.

**Data shape** (output listing dict):
```python
{
    "id": str,         # object_id
    "source": "kv.ee",
    "url": str,        # full URL
    "title": str,
    "price": str,      # formatted, e.g. "500&nbsp;€"
    "price_eur": int,
    "rooms": str,      # extracted from HTML excerpt
    "area": str,       # extracted from HTML excerpt
    "image": str,
    "date_activated": str,  # date only, YYYY-MM-DD
}
```

---

### `city24_scraper.py`

Scrapes City24 using Playwright to fetch JSON API data (single call, no pagination).

**Key functions:**
- `scrape_all_pages()` — async entrypoint. Opens browser, navigates to city24.ee for cookies, then calls API via `page.evaluate(fetch(...))`. Returns list of listing dicts.
- `_parse_listings(data)` — iterates API response array, normalizes fields. Uses helper functions for slogan extraction, date parsing, image processing, and URL building.
- `_extract_slogan(item)` — extracts slogan from nested `slogans` dict (tries `en_GB` first, falls back to `et_EE`).
- `_parse_date(date_str)` — splits ISO datetime string to date-only format.
- `_process_image(item)` — extracts image URL and replaces `{fmt:em}` placeholder with `"13"`.
- `_build_url(item, slug)` — constructs full listing URL from slug + friendly_id.
- `_slugify(s)` — lowercase, strip special chars, replace spaces with hyphens.

**Data shape** (output listing dict): same schema as `scraper.py`, but `source` is `"city24"` and `price` uses `"€"` suffix format.

---

### `database.py`

SQLite storage layer with change detection logic.

**Schema:** Single `listings` table with columns: `id` (PK), `source`, `url`, `title`, `price`, `price_eur`, `rooms`, `area`, `image`, `date_activated`, `scraped_at`.

**Key functions:**
- `get_connection()` — opens SQLite connection with `row_factory = sqlite3.Row`. Creates parent dir if needed.
- `init_db()` — creates `listings` table if missing. Migrates `source` column if needed (backward compat for old DBs).
- `upsert_listings(listings)` — INSERT OR REPLACE for each listing. Records current ISO timestamp as `scraped_at`.
- `get_changes(current_listings)` — compares current scrape results against DB. Returns tuple of `(new_listings, removed_listings, price_changes)`. Price comparison uses `_normalize_price()` to extract numeric values.
- `delete_listings(listing_ids)` — bulk DELETE by ID for removed listings.
- `_normalize_price(price_str)` — regex extracts numeric portion from formatted price string (handles `&nbsp;`, commas).

---

### `monitor.py`

Main orchestrator. Runs both scrapers, merges results, detects changes, and sends email alert if there are differences.

**Execution flow:**
1. `load_email_config()` — loads SMTP config from `.env` files (checks `APP_ENV` to load `.env.development` or `.env.production`)
2. `database.init_db()` — ensures DB schema exists
3. `await scraper.scrape_all_pages()` — fetches KV.ee listings
4. `await city24_scraper.scrape_all_pages()` — fetches City24 listings
5. Merges both lists
6. `database.get_changes(all_listings)` — detects new, removed, price-changed listings
7. If changes exist: builds HTML report, sends email, upserts all listings, deletes removed ones
8. If no changes: just upserts, no email sent

**Key functions:**
- `load_email_config()` — reads SMTP settings from env vars. Supports `EMAIL_DISABLED` flag for dev mode.
- `send_email(cfg, subject, body)` — sends HTML email via SMTP. Skips if disabled or config incomplete.
- `_source_badge(l)` — returns colored HTML badge for source (blue for city24, orange for kv.ee).
- `_listing_card(l)` — builds HTML card with image, title, price, area, date, and link.
- `build_report(new, removed, changed)` — assembles full HTML email with sections for new, removed, and price-changed listings.
- `main()` — async entrypoint. Full orchestration flow.

---

### `service.py`

Daemon wrapper. Runs `monitor.main()` in an infinite loop with configurable sleep interval, file logging, and graceful shutdown.

**Key functions:**
- `run_once()` — wraps `monitor.main()` in try/except to prevent crashes from killing the service.
- `main()` — signal handlers for SIGINT/SIGTERM, then infinite loop: run scrape, calculate remaining sleep time, wait with `asyncio.wait_for` (interruptible by shutdown event).
- `signal_handler()` — sets shutdown event for graceful exit.

**Logging:** Writes to both stdout and `logs/service.log` (configured in `config.py`).

---

### `install-service.sh` + `kv-monitor.service`

Production deployment tools.

- `install-service.sh` — copies `kv-monitor.service` to `/etc/systemd/system/`, reloads daemon, enables and starts service.
- `kv-monitor.service` — systemd unit: runs as user `debian`, working dir `/home/debian/apps/rent-scraper`, uses venv Python, restarts always with 30s delay.

---

## Data Flow

```
service.py (daemon loop, every CHECK_INTERVAL_SECONDS)
  └── monitor.py (orchestrator)
        ├── scraper.py ──► KV.ee listings[]
        ├── city24_scraper.py ──► City24 listings[]
        ├── merge lists[]
        └── database.py
              ├── get_changes() ──► new[], removed[], changed[]
              ├── upsert_listings(all)
              └── delete_listings(removed)
        └── build_report(new, removed, changed) ──► HTML email
        └── send_email() ──► SMTP
```

---

## Listing Dict Schema

Both scrapers produce dicts with identical shape:

```python
{
    "id": str,            # unique listing ID from source
    "source": str,        # "kv.ee" or "city24"
    "url": str,           # full listing URL
    "title": str,         # listing title/slogan
    "price": str,         # formatted price (may contain HTML entities)
    "price_eur": int,     # numeric price in EUR
    "rooms": str,         # room count as string (e.g. "2", "3")
    "area": str,          # area with unit (e.g. "45 m²")
    "image": str,         # thumbnail image URL
    "date_activated": str, # YYYY-MM-DD
}
```

---

## Running

```bash
# One-time run (dev)
APP_ENV=development python3 monitor.py

# Background service (prod)
python3 service.py

# As systemd service
bash install-service.sh
systemctl status kv-monitor
journalctl -u kv-monitor -f
```

---

## Env Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `APP_ENV` | Selects `.env.{APP_ENV}` file | `development`, `production` |
| `EMAIL_DISABLED` | Skip email sending if truthy | `true` |
| `SMTP_SERVER` | SMTP host | `51.195.119.32` |
| `SMTP_PORT` | SMTP port | `25` |
| `EMAIL_FROM` | Sender email | `house-scraper@xlipdev.com` |
| `EMAIL_FROM_NAME` | Sender display name | `XlipDev.com` |
| `EMAIL_TO` | Recipient email | `xlip.studio@gmail.com` |

---

## Common Tasks

### Adding a new scraper source
1. Create `newsource_scraper.py` with `scrape_all_pages()` async function
2. Import in `monitor.py`, call it after existing scrapers
3. Add to merged list: `all_listings += newsource_listings`
4. Update `_source_badge()` in `monitor.py` with new color badge

### Changing search filters
Edit `config.py`: `KV_SEARCH_PARAMS` dict or `CITY24_SEARCH_URL` string.

### Adjusting check interval
Edit `CHECK_INTERVAL_SECONDS` in `config.py`.

### Modifying email template
Edit `_listing_card()` and `build_report()` in `monitor.py`.
