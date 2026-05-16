import sqlite3
import os
from datetime import datetime
import config


def get_connection():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            url TEXT,
            title TEXT,
            price TEXT,
            price_eur INTEGER,
            rooms TEXT,
            area TEXT,
            image TEXT,
            date_activated TEXT,
            scraped_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def upsert_listings(listings):
    now = datetime.now().isoformat()
    conn = get_connection()
    for listing in listings:
        conn.execute("""
            INSERT OR REPLACE INTO listings
                (id, url, title, price, price_eur, rooms, area, image, date_activated, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            listing["id"],
            listing["url"],
            listing["title"],
            listing["price"],
            listing.get("price_eur", 0),
            listing["rooms"],
            listing["area"],
            listing.get("image", ""),
            listing.get("date_activated", ""),
            now,
        ))
    conn.commit()
    conn.close()


def get_changes(current_listings):
    current_ids = {l["id"] for l in current_listings}
    current_map = {l["id"]: l for l in current_listings}

    conn = get_connection()

    db_rows = conn.execute("SELECT * FROM listings").fetchall()
    db_map = {row["id"]: dict(row) for row in db_rows}
    db_ids = set(db_map.keys())

    new_ids = current_ids - db_ids
    removed_ids = db_ids - current_ids
    changed_ids = set()

    for lid in current_ids & db_ids:
        old_price = _normalize_price(db_map[lid]["price"])
        new_price = _normalize_price(current_map[lid]["price"])
        if old_price and new_price and old_price != new_price:
            changed_ids.add(lid)

    conn.close()

    new_listings = [current_map[lid] for lid in sorted(new_ids)]
    removed_listings = [db_map[lid] for lid in sorted(removed_ids)]
    price_changes = []
    for lid in sorted(changed_ids):
        price_changes.append({
            "id": lid,
            "title": current_map[lid]["title"],
            "old_price": db_map[lid]["price"],
            "new_price": current_map[lid]["price"],
            "url": current_map[lid]["url"],
        })

    return new_listings, removed_listings, price_changes


def _normalize_price(price_str):
    if not price_str:
        return ""
    import re
    match = re.search(r"(\d[\d,]*)\s*€", price_str.replace("\u00a0", " "))
    return match.group(1).replace(",", "") if match else ""
