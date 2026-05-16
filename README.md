# KV.ee Rental Scraper

Monitors rental listings on [KV.ee](https://www.kv.ee) and sends email notifications for new, removed, or price-changed listings.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

## Configuration

Set your SMTP credentials in `.env`:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_TO=recipient@example.com
```

Edit `config.py` to adjust search filters, check interval, and DB path.

## Usage

**One-off run:**
```bash
python3 monitor.py
```

**Background service:**
```bash
python3 service.py
```

Runs hourly checks with file logging to `logs/service.log`. Handles SIGINT/SIGTERM for graceful shutdown.

## Files

| File | Description |
|------|-------------|
| `scraper.py` | Playwright-based scraper using KV.ee's JSON API |
| `database.py` | SQLite storage and change detection |
| `monitor.py` | Orchestration and HTML email reporting |
| `service.py` | Daemon loop with hourly execution and logging |
| `config.py` | Search params, paths, and service settings |

## Deployment

Package and transfer to VPS:

```bash
tar czf rent-scraper.tar.gz --exclude='data' --exclude='logs' --exclude='__pycache__' --exclude='venv' --exclude='.env' *.py requirements.txt
scp -P <port> rent-scraper.tar.gz user@host:/path/to/
```

On the target machine, extract, create venv, install deps, and set up the systemd service using `install-service.sh`.
