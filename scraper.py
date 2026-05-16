import asyncio
import re
import urllib.parse
from playwright.async_api import async_playwright
import config


async def scrape_all_pages():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=config.PLAYWRIGHT_USER_AGENT,
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        search_url = _build_search_url(config.KV_SEARCH_PARAMS)
        await page.goto(search_url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)

        accept_btn = await page.query_selector('#onetrust-accept-btn-handler')
        if accept_btn:
            await accept_btn.click(force=True)
            await asyncio.sleep(1)

        all_listings = []
        page_num = 1
        per_page = 20

        while True:
            offset = (page_num - 1) * per_page
            api_url = _build_api_url(config.KV_SEARCH_PARAMS, offset)

            data = await page.evaluate("""
                async (url) => {
                    const resp = await fetch(url);
                    return await resp.json();
                }
            """, api_url)

            if not data:
                break

            listings = _parse_listings(data)
            if not listings:
                break

            all_listings.extend(listings)
            print(f"  [kv.ee] Scraped {len(all_listings)} listings so far...")

            total = data.get("total", 0)
            if len(all_listings) >= total:
                break

            page_num += 1
            await asyncio.sleep(0.5)

        await browser.close()
        return all_listings


def _parse_listings(data):
    listings = []
    show_objects = data.get("showObjects", [])

    for obj in show_objects:
        obj_id = str(obj.get("object_id", ""))
        if not obj_id:
            continue

        html = obj.get("html", "")
        url_match = re.search(r'href="([^"]+)"', html)
        url = url_match.group(1) if url_match else ""
        if url and not url.startswith("http"):
            url = f"https://www.kv.ee{url}"

        title_match = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        title = re.sub(r'<[^>]+>', '', title).strip()

        price_eur = obj.get("price_eur", 0)
        price = f"{price_eur}&nbsp;€" if price_eur else ""

        img_match = re.search(r'data-src="([^"]+)"', html)
        image = img_match.group(1) if img_match else ""

        excerpt_match = re.search(r'<p class="object-excerpt">(.*?)</p>', html, re.DOTALL)
        excerpt = excerpt_match.group(1) if excerpt_match else ""
        excerpt_clean = re.sub(r'<[^>]+>', '', excerpt).strip()

        rooms = ""
        rooms_match = re.search(r'(\d+)\s*[-–]\s*[rR]ealine', excerpt_clean) or \
                      re.search(r'(\d+)\s*toaline', excerpt_clean)
        if rooms_match:
            rooms = rooms_match.group(1)

        area = ""
        area_match = re.search(r'(\d+\.?\d*)\s*m²', excerpt_clean)
        if area_match:
            area = f"{area_match.group(1)} m²"

        date_activated = obj.get("date_activated", "")
        if date_activated:
            date_activated = date_activated.split(" ")[0]

        listings.append({
            "id": obj_id,
            "source": "kv.ee",
            "url": url,
            "title": title,
            "price": price,
            "price_eur": obj.get("price_eur", 0),
            "rooms": rooms,
            "area": area,
            "image": image,
            "date_activated": date_activated,
        })

    return listings


def _build_api_url(params, offset=0):
    params = params.copy()
    params["offset"] = offset
    query = urllib.parse.urlencode(params)
    return f"{config.KV_API_BASE_URL}/map?{query}"


def _build_search_url(params):
    query = urllib.parse.urlencode(params)
    return f"{config.KV_BASE_URL}?{query}"


async def main():
    print("Starting kv.ee scraper...")
    listings = await scrape_all_pages()
    print(f"Done. Found {len(listings)} listings.")
    for l in listings[:5]:
        print(f"  #{l['id']} - {l['title']} | {l['price']} | {l['area']}")
    if len(listings) > 5:
        print(f"  ... and {len(listings) - 5} more")


if __name__ == "__main__":
    asyncio.run(main())
