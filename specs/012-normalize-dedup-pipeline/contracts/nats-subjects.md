# NATS Subject Contracts: Normalize & Deduplicate Pipeline

**Feature**: 012-normalize-dedup-pipeline | **Date**: 2026-04-17

## Stream Topology

| Stream | Subjects | Retention | Producer | Consumers |
|--------|----------|-----------|----------|-----------|
| `RAW_LISTINGS` | `raw.listings.*` | WorkQueue (delete on ack) | spider-workers | normalizer |
| `NORMALIZED_LISTINGS` | `normalized.listings.*` | Limits (7 days) | normalizer | deduplicator |
| `DEDUPLICATED_LISTINGS` | `deduplicated.listings.*` | Limits (7 days) | deduplicator | alert-engine, ml-scorer |

`*` wildcard = country code in lowercase (e.g., `raw.listings.es`, `normalized.listings.fr`).

---

## Message Schemas

### `raw.listings.<country>` — Input

Produced by spider-workers. The normalizer consumes this subject.

```json
{
  "external_id": "string (required) — portal's listing ID",
  "portal": "string (required) — portal slug, e.g. 'idealista'",
  "country_code": "string (required) — ISO 3166-1 alpha-2, uppercase",
  "raw_json": "object (required) — full portal-specific payload",
  "scraped_at": "string (required) — ISO 8601 UTC datetime"
}
```

Pydantic model: `estategap_common.models.listing.RawListing`

---

### `normalized.listings.<country>` — Intermediate

Produced by the normalizer after successful DB write.

```json
{
  "id": "string (UUID) — listings.id",
  "canonical_id": "string (UUID) | null",
  "country": "string — ISO 3166-1 alpha-2, uppercase",
  "source": "string — portal slug",
  "source_id": "string — portal's listing ID",
  "source_url": "string — canonical listing URL",
  "asking_price": "string (decimal) — original price",
  "currency": "string — ISO 4217",
  "asking_price_eur": "string (decimal) — EUR-converted price",
  "built_area_m2": "string (decimal) — area in m²",
  "bedrooms": "integer | null",
  "bathrooms": "integer | null",
  "property_category": "string | null — residential|commercial|industrial|land",
  "location_wkt": "string | null — WKT POINT(lon lat)",
  "address": "string | null",
  "city": "string | null",
  "data_completeness": "number — 0.0 to 1.0",
  "first_seen_at": "string — ISO 8601 UTC",
  "last_seen_at": "string — ISO 8601 UTC"
}
```

Pydantic model: `estategap_common.models.listing.NormalizedListing` (subset of fields)

---

### `deduplicated.listings.<country>` — Output

Produced by the deduplicator after `canonical_id` resolution.

Same schema as `normalized.listings.<country>` with one guaranteed field:

```json
{
  "...all fields from normalized.listings...",
  "canonical_id": "string (UUID) — always set; equals id if first in group"
}
```

---

## Consumer Configuration

### Normalizer Consumer

```python
await js.subscribe(
    "raw.listings.*",
    durable="normalizer",
    stream="RAW_LISTINGS",
    manual_ack=True,
    config=nats.js.api.ConsumerConfig(
        ack_policy=nats.js.api.AckPolicy.EXPLICIT,
        max_deliver=5,          # retry up to 5 times before dead-letter
        ack_wait=30,            # 30 seconds before NAK-on-timeout
        max_ack_pending=100,    # limit in-flight messages
    ),
)
```

### Deduplicator Consumer

```python
await js.subscribe(
    "normalized.listings.*",
    durable="deduplicator",
    stream="NORMALIZED_LISTINGS",
    manual_ack=True,
    config=nats.js.api.ConsumerConfig(
        ack_policy=nats.js.api.AckPolicy.EXPLICIT,
        max_deliver=3,
        ack_wait=60,            # dedup query may take up to 50ms * batch
        max_ack_pending=50,
    ),
)
```

---

## Error Handling

| Condition | Normalizer action | Deduplicator action |
|-----------|-------------------|---------------------|
| Invalid JSON | Write quarantine record, ACK (don't redeliver garbage) | Write quarantine record, ACK |
| No mapping config | Write quarantine record, ACK | N/A |
| Pydantic validation failure | Write quarantine record, ACK | N/A |
| DB write failure (transient) | NAK — JetStream redelivers with backoff | NAK — redelivers |
| PostGIS query timeout | N/A | NAK — redelivers |

ACK on quarantine ensures malformed messages are consumed exactly once and don't block the queue.
NAK on transient infra failures ensures at-least-once delivery on DB writes.
