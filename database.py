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
            source TEXT,
            url TEXT,
            title TEXT,
            price TEXT,
            price_eur INTEGER,
            rooms TEXT,
            area TEXT,
            image TEXT,
            date_activated TEXT,
            booked_until TEXT,
            scraped_at TEXT
        )
    """)
    # Add source column if it doesn't exist (migration)
    try:
        conn.execute("ALTER TABLE listings ADD COLUMN source TEXT")
        conn.execute("UPDATE listings SET source = 'kv.ee' WHERE source IS NULL")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()


def upsert_listings(listings):
    now = datetime.now().isoformat()
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        for listing in listings:
            conn.execute("""
                INSERT OR REPLACE INTO listings
                    (id, source, url, title, price, price_eur, rooms, area, image, date_activated, booked_until, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                listing["id"],
                listing.get("source", ""),
                listing["url"],
                listing["title"],
                listing.get("price", ""),
                listing.get("price_eur", 0),
                listing.get("rooms", ""),
                listing.get("area", ""),
                listing.get("image", ""),
                listing.get("date_activated", ""),
                listing.get("booked_until", ""),
                now,
            ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
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
        old_price = _normalize_price(db_map[lid].get("price", ""))
        new_price = _normalize_price(current_map[lid].get("price", ""))
        if old_price and new_price and old_price != new_price:
            changed_ids.add(lid)

    booked_changed_ids = set()
    for lid in current_ids & db_ids:
        old_booked = db_map[lid].get("booked_until", "") or ""
        new_booked = current_map[lid].get("booked_until", "") or ""
        if old_booked != new_booked and (old_booked or new_booked):
            booked_changed_ids.add(lid)

    conn.close()

    new_listings = [current_map[lid] for lid in sorted(new_ids)]
    removed_listings = [db_map[lid] for lid in sorted(removed_ids)]
    price_changes = []
    for lid in sorted(changed_ids):
        price_changes.append({
            "id": lid,
            "source": current_map[lid].get("source", ""),
            "title": current_map[lid]["title"],
            "old_price": db_map[lid]["price"],
            "new_price": current_map[lid]["price"],
            "url": current_map[lid]["url"],
            "image": current_map[lid].get("image", ""),
        })

    booked_changes = []
    for lid in sorted(booked_changed_ids):
        is_now_booked = bool(current_map[lid].get("booked_until", ""))
        booked_changes.append({
            "id": lid,
            "source": current_map[lid].get("source", ""),
            "title": current_map[lid]["title"],
            "booked_until": current_map[lid].get("booked_until", ""),
            "was_booked": bool(db_map[lid].get("booked_until", "")),
            "is_now_booked": is_now_booked,
            "url": current_map[lid]["url"],
            "image": current_map[lid].get("image", ""),
        })

    return new_listings, removed_listings, price_changes, booked_changes


def save_changes(listings, removed_ids):
    """Upsert listings and delete removed ones in a single transaction."""
    conn = get_connection()
    now = datetime.now().isoformat()
    try:
        conn.execute("BEGIN")
        if removed_ids:
            conn.executemany("DELETE FROM listings WHERE id = ?", [(lid,) for lid in removed_ids])
        for listing in listings:
            conn.execute("""
                INSERT OR REPLACE INTO listings
                    (id, source, url, title, price, price_eur, rooms, area, image, date_activated, booked_until, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                listing["id"],
                listing.get("source", ""),
                listing["url"],
                listing["title"],
                listing.get("price", ""),
                listing.get("price_eur", 0),
                listing.get("rooms", ""),
                listing.get("area", ""),
                listing.get("image", ""),
                listing.get("date_activated", ""),
                listing.get("booked_until", ""),
                now,
            ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_listings(listing_ids):
    if not listing_ids:
        return
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.executemany("DELETE FROM listings WHERE id = ?", [(lid,) for lid in listing_ids])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _normalize_price(price_str):
    if not price_str:
        return ""
    import re
    match = re.search(r"(\d[\d,.]*)", str(price_str).replace("\u00a0", " "))
    return match.group(1).replace(",", "") if match else ""
