import asyncio
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

import scraper
import city24_scraper
import database
import config


def load_email_config():
    app_env = os.getenv("APP_ENV", "production")
    load_dotenv(f".env.{app_env}")
    load_dotenv()
    return {
        "disabled": os.getenv("EMAIL_DISABLED", "").lower() in ("true", "1", "yes"),
        "server": os.getenv("SMTP_SERVER", ""),
        "port": int(os.getenv("SMTP_PORT", "25")),
        "from": os.getenv("EMAIL_FROM", ""),
        "from_name": os.getenv("EMAIL_FROM_NAME", ""),
        "to": os.getenv("EMAIL_TO", ""),
    }


def send_email(cfg, subject, body):
    if cfg.get("disabled"):
        print("[!] Email disabled (development mode) -- skipping send")
        print(f"    Subject: {subject}")
        return
    if not cfg["server"]:
        print("[!] Email config incomplete -- skipping send. Set values in .env")
        print(f"    Subject: {subject}")
        return

    msg = MIMEMultipart()
    from_name = cfg["from_name"]
    from_email = cfg["from"]
    from_addr = from_name + " <" + from_email + ">" if from_name else from_email
    msg["From"] = from_addr
    msg["To"] = cfg["to"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(cfg["server"], cfg["port"], timeout=30) as s:
            s.send_message(msg)
        print("  Email sent successfully.")
    except Exception as e:
        print(f"  Failed to send email: {e}")


def _source_badge(l):
    src = l.get("source", "")
    if src == "city24":
        return '<span style="background: #4a90d9; color: #fff; font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-left: 4px;">city24</span>'
    elif src == "kv.ee":
        return '<span style="background: #f0ad4e; color: #fff; font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-left: 4px;">kv.ee</span>'
    return ""


def _listing_card(l):
    image_html = ""
    if l.get("image"):
        image_html = f'<img src="{l["image"]}" width="200" height="150" style="object-fit: cover; border-radius: 4px;"><br>'

    date_str = l.get("date_activated", "")
    date_line = f"Published: {date_str}<br>" if date_str else ""

    price_str = l.get("price", "")
    area_str = l.get("area", "")
    badge = _source_badge(l)

    return f"""<div style="border: 1px solid #ddd; border-radius: 6px; padding: 12px; margin: 8px 0; display: inline-block; width: 280px; vertical-align: top;">
    {image_html}
    <strong>#{l['id']}</strong> {badge} - {l['title']}<br>
    <span style="font-size: 18px; color: #c00;">{price_str}</span> &nbsp;|&nbsp; {area_str}<br>
    {date_line}
    <a href="{l['url']}" style="color: #0066cc;">View listing</a>
</div>"""


def build_report(new, removed, changed):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [f"""<html>
<body style="font-family: Arial, sans-serif; font-size: 14px;">
<h2>Rental Monitor -- {now}</h2>
<hr>"""]

    if new:
        parts.append(f"<h3>NEW LISTINGS ({len(new)}):</h3>")
        for l in new:
            parts.append(_listing_card(l))

    if removed:
        parts.append(f"<h3>REMOVED ({len(removed)}):</h3>")
        for l in removed:
            parts.append(_listing_card(l))

    if changed:
        parts.append(f"<h3>PRICE CHANGES ({len(changed)}):</h3>")
        for c in changed:
            image_html = ""
            if c.get("image"):
                image_html = f'<img src="{c["image"]}" width="200" height="150" style="object-fit: cover; border-radius: 4px;"><br>'
            badge = _source_badge(c)
            parts.append(f"""<div style="border: 1px solid #ddd; border-radius: 6px; padding: 12px; margin: 8px 0; display: inline-block; width: 280px; vertical-align: top;">
    {image_html}
    <strong>#{c['id']}</strong> {badge} - {c['title']}<br>
    <span style="color: #999;">{c['old_price']}</span> &rarr; <span style="font-size: 18px; color: #c00;">{c['new_price']}</span><br>
    <a href="{c['url']}" style="color: #0066cc;">View listing</a>
</div>""")

    if not new and not removed and not changed:
        parts.append("<p>No changes detected.</p>")

    parts.append("<hr><p><em>This is an automated alert from rental monitor.</em></p></body></html>")
    return "\n".join(parts)


async def main():
    email_cfg = load_email_config()

    print("=" * 60)
    print("Rental Monitor (kv.ee + city24)")
    print("=" * 60)

    database.init_db()

    print("\n[1/4] Scraping kv.ee listings...")
    kv_listings = await scraper.scrape_all_pages()
    print(f"  Found {len(kv_listings)} listings from kv.ee.")

    print("\n[2/4] Scraping city24 listings...")
    city24_listings = city24_scraper.scrape_all_pages()
    print(f"  Found {len(city24_listings)} listings from city24.")

    all_listings = kv_listings + city24_listings
    print(f"\n[3/4] Total merged: {len(all_listings)} listings.")

    print("\n[4/4] Checking for changes...")
    new, removed, changed = database.get_changes(all_listings)
    print(f"  New: {len(new)}, Removed: {len(removed)}, Price changes: {len(changed)}")

    has_changes = new or removed or changed

    database.upsert_listings(all_listings)

    if has_changes:
        report = build_report(new, removed, changed)
        subject = (
            f"{config.EMAIL_SUBJECT_PREFIX} "
            f"{len(new)} new, {len(removed)} removed, {len(changed)} price changes"
        )
        print("\n" + report)
        print("\nSending email alert...")
        send_email(email_cfg, subject, report)
    else:
        print("  No changes -- no email sent.")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
