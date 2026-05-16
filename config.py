PLAYWRIGHT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)

# KV.ee settings
KV_BASE_URL = "https://www.kv.ee/et/search"
KV_API_BASE_URL = "https://www.kv.ee/en/api/search"

KV_SEARCH_PARAMS = {
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

# City24 settings
CITY24_API_BASE = "https://api.city24.ee/en_GB"

CITY24_SEARCH_URL = (
    "https://api.city24.ee/en_GB/search/realties"
    "?address[cc]=1"
    "&address[parish][]=181"
    "&tsType=rent"
    "&unitType=Apartment"
    "&roomCount=2%2C3"
    "&boundingBox[nw]=59.431207,24.751760"
    "&boundingBox[se]=59.428029,24.765685"
)

DB_PATH = "data/listings.db"

EMAIL_SUBJECT_PREFIX = "[rentals]"

# Service settings
CHECK_INTERVAL_SECONDS = 3600  # 1 hour
LOG_DIR = "logs"
LOG_FILE = "logs/service.log"
