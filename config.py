PLAYWRIGHT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)

BASE_URL = "https://www.kv.ee/et/search"
API_BASE_URL = "https://www.kv.ee/en/api/search"

SEARCH_PARAMS = {
    "deal_type": "2",
    "rooms_min": "2",
    "rooms_max": "3",
    "county": "1",
    "parish": "1061",
    "city[0]": "1003",
    "cluster": "true",
    "zoom": "16.09032008642905",
    "nelat": "59.43296909968546",
    "nelng": "24.770517743598795",
    "swlat": "59.42466558149462",
    "swlng": "24.74637145669501",
    "orderby": "cdwl",
}

DB_PATH = "data/listings.db"

EMAIL_SUBJECT_PREFIX = "[kv.ee]"

# Service settings
CHECK_INTERVAL_SECONDS = 3600  # 1 hour
LOG_DIR = "logs"
LOG_FILE = "logs/service.log"
