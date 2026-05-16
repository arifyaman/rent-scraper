import asyncio
import re
import json
from playwright.async_api import async_playwright
import config


def _slugify(s):
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s]+', '-', s)
    return s


async def scrape_all_pages():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=config.PLAYWRIGHT_USER_AGENT,
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # Load city24 page first to get cookies/session
        await page.goto(
            "https://www.city24.ee/en/real-estate/apartments-for-rent/",
            wait_until="networkidle",
            timeout=60000,
        )
        await asyncio.sleep(2)

        # Fetch API data from within browser context
        data = await page.evaluate("""
            async () => {
                const resp = await fetch("CITY24_URL");
                return await resp.json();
            }
        """.replace("CITY24_URL", config.CITY24_SEARCH_URL))

        await browser.close()

    if not data:
        return []

    listings = _parse_listings(data)
    print(f"  [city24] Scraped {len(listings)} listings.")
    return listings


def _parse_listings(data):
    listings = []

    for item in data:
        item_id = str(item.get("id", ""))
        if not item_id:
            continue

        price_eur = float(item.get("price", 0) or 0)
        price = f"{int(price_eur)} €" if price_eur else ""

        room_count = item.get("room_count", "")
        rooms = str(room_count) if room_count else ""

        property_size = item.get("property_size", "")
        area = f"{property_size} m²" if property_size else ""

        main_image = item.get("main_image", {})
        image = main_image.get("url", "") if isinstance(main_image, dict) else ""
        if image and "{fmt:em}" in image:
            image = image.replace("{fmt:em}", "13")

        date_published = item.get("date_published", "")
        if date_published:
            date_activated = date_published.split("T")[0]
        else:
            date_activated = ""

        slogan = ""
        slogans = item.get("slogans", {})
        if isinstance(slogans, dict):
            en_block = slogans.get("en_GB", {})
            if isinstance(en_block, dict):
                slogan = en_block.get("slogan", "")
            if not slogan:
                et_block = slogans.get("et_EE", {})
                if isinstance(et_block, dict):
                    slogan = et_block.get("slogan", "")

        title = slogan or f"Apartment {rooms}r"

        addr = item.get("address", {})
        parish = addr.get("parish_name", "")
        city = addr.get("city_name", "")
        street = addr.get("street_name", "")
        friendly_id = item.get("friendly_id", item_id)

        slug = _slugify(f"{parish} {city} {street}")
        url = f"https://www.city24.ee/en/real-estate/apartments-for-rent/{slug}/{friendly_id}"

        listings.append({
            "id": item_id,
            "source": "city24",
            "url": url,
            "title": title,
            "price": price,
            "price_eur": int(price_eur),
            "rooms": rooms,
            "area": area,
            "image": image,
            "date_activated": date_activated,
        })

    return listings


async def main():
    print("Starting city24 scraper...")
    listings = await scrape_all_pages()
    print(f"Done. Found {len(listings)} listings.")
    for l in listings[:5]:
        print(f"  #{l['id']} - {l['title']} | {l['price']} | {l['area']}")
    if len(listings) > 5:
        print(f"  ... and {len(listings) - 5} more")


if __name__ == "__main__":
    asyncio.run(main())
