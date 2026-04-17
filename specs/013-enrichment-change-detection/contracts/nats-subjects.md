# NATS Contracts: Enrichment & Change Detection

**Feature**: 013-enrichment-change-detection
**Date**: 2026-04-17

---

## Enricher Service

### Consumed Subjects

| Subject Pattern | Stream | Description |
|---|---|---|
| `listings.deduplicated.{country}` | `normalized-listings` | Deduplicated listings ready for enrichment |

**Consumer config**:
- Durable name: `enricher`
- Ack policy: `AckPolicy.EXPLICIT`
- Max deliver: `5`
- Ack wait: `60s`
- Max ack pending: `100`

**Message format**: JSON-serialized `NormalizedListing` (Pydantic model from `estategap_common.models.listing`)

### Published Subjects

| Subject Pattern | Stream | Description |
|---|---|---|
| `listings.enriched.{country}` | `enriched-listings` | Enriched listing ready for ML scoring |

**Stream config** (pre-existing in Helm values):
- Retention: `720h` (30 days)
- Replicas: `3`
- Storage: `file`

**Message format**: JSON-serialized `NormalizedListing` with enrichment fields populated.

---

## Change Detector Service

### Consumed Subjects

| Subject Pattern | Stream | Description |
|---|---|---|
| `scraper.cycle.completed.{country}.{portal}` | `scraper-commands` | Signals end of a portal scrape cycle |

**Consumer config**:
- Durable name: `change-detector`
- Ack policy: `AckPolicy.EXPLICIT`
- Max deliver: `3`
- Ack wait: `120s`
- Max ack pending: `10`

**Message format** (`ScrapeCycleEvent`):
```json
{
  "cycle_id": "string (UUID)",
  "portal": "string (e.g., idealista)",
  "country": "string (ISO 3166-1 alpha-2, e.g., ES)",
  "completed_at": "ISO 8601 datetime",
  "listing_ids": ["uuid", "uuid", "..."]
}
```
`listing_ids` may be empty if the orchestrator does not populate them; in that case the change detector uses `last_seen_at` to determine cycle membership.

### Published Subjects

| Subject Pattern | Stream | Description |
|---|---|---|
| `listings.price-change.{country}` | `price-changes` | Price drop event for alert engine consumption |

**Stream config** (pre-existing):
- Retention: `2160h` (90 days)
- Replicas: `3`
- Storage: `file`

**Message format** (`PriceChangeEvent`):
```json
{
  "listing_id": "uuid",
  "country": "ES",
  "portal": "idealista",
  "old_price": 300000.00,
  "new_price": 290000.00,
  "currency": "EUR",
  "old_price_eur": 300000.00,
  "new_price_eur": 290000.00,
  "drop_percentage": 3.33,
  "recorded_at": "2026-04-17T10:00:00Z"
}
```

Only price **drops** (new_price < old_price) generate an event. Price increases update the DB only.

---

## Subject Naming Convention

All subjects follow the project-wide pattern:
- `listings.{stage}.{country_lower}` — listing pipeline stages
- `scraper.cycle.completed.{country_lower}.{portal}` — scraper orchestrator events

Country codes are always lowercase ISO 3166-1 alpha-2 (e.g., `es`, `fr`, `pt`).
