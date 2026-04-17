# Spider Registry Contract: US Portals

**Feature**: 026-us-spiders-country-ml  
**Pattern**: Extends existing auto-registration pattern from feature 011/025

---

## New Spider Registrations

The following spiders are auto-registered via `__init_subclass__` on import:

| Registry Key | Class | File | Playwright? |
|-------------|-------|------|------------|
| `("us", "zillow")` | `ZillowUSSpider` | `us_zillow.py` | Yes (stealth) |
| `("us", "redfin")` | `RedfinUSSpider` | `us_redfin.py` | No |
| `("us", "realtor_com")` | `RealtorComUSSpider` | `us_realtor.py` | No |

---

## Spider Interface (inherits BaseSpider)

```python
class ZillowUSSpider(BaseSpider):
    COUNTRY = "US"
    PORTAL = "zillow"
    RATE_LIMIT_SECONDS = 3.0          # 1 req / 3 s
    REQUIRES_PLAYWRIGHT = True
    USE_RESIDENTIAL_PROXY = True

    async def scrape_search_page(
        self, zone: str, page: int
    ) -> list[RawListing]: ...

    async def scrape_listing_detail(
        self, url: str
    ) -> RawListing | None: ...

    async def detect_new_listings(
        self, zone: str, since_ids: set[str]
    ) -> list[str]: ...  # Returns new URLs
```

---

## Parser Module Interface

Each spider has a companion parser module:

```python
# us_zillow_parser.py
def parse_next_data(next_data: dict) -> RawListing: ...
def parse_search_results(next_data: dict) -> list[dict]: ...

# us_redfin_parser.py  
def parse_above_fold(payload: dict) -> RawListing: ...
def parse_school_data(schools: list[dict]) -> float | None: ...  # avg rating

# us_realtor_parser.py
def parse_json_ld(ld_blocks: list[dict]) -> RawListing: ...
def parse_window_data(html: str) -> dict: ...  # crime index, extra fields
```

---

## Rate Limiting Configuration

Spider rate limits are enforced by the existing `RateLimiter` in `BaseSpider`. Configuration in `services/spider-workers/estategap_spiders/config.py`:

```python
RATE_LIMITS = {
    # ... existing portals ...
    "zillow":      3.0,   # seconds between requests
    "redfin":      2.0,
    "realtor_com": 1.5,
}
```

---

## NATS Subject (existing, no change)

US listings are published to the same ingestion stream as EU listings:

```
listings.raw.ingested   →  payload: RawListing JSON
```

The `country = "US"` field in the payload routes the listing to the US partition after normalisation.
