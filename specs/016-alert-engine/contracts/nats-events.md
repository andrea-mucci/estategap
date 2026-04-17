# NATS Event Contracts: Alert Engine (016)

**Date**: 2026-04-17
**Branch**: `016-alert-engine`

---

## Consumed Events

### `scored.listings`

Published by: `ml-scorer` service
Stream: `scored-listings`
Durable consumer: `alert-engine-scored`

```json
{
  "listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "country_code": "ES",
  "lat": 40.4168,
  "lon": -3.7038,
  "property_type": "residential",
  "price_eur": 320000.00,
  "area_m2": 95.0,
  "bedrooms": 3,
  "features": ["parking", "garden"],
  "deal_score": 0.87,
  "deal_tier": 1,
  "estimated_price_eur": 380000.00,
  "model_version": "lgbm-es-v3",
  "scored_at": "2026-04-17T10:30:00Z"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `listing_id` | UUID string | yes | |
| `country_code` | string (ISO 3166-1 alpha-2) | yes | Used for rule index lookup |
| `lat` | float64 | yes | WGS84 |
| `lon` | float64 | yes | WGS84 |
| `property_type` | string | yes | residential / commercial / industrial / land |
| `price_eur` | float64 | yes | Current asking price in EUR |
| `area_m2` | float64 | yes | |
| `bedrooms` | integer | no | null for commercial/industrial/land |
| `features` | string[] | no | e.g., parking, garden, pool |
| `deal_score` | float64 [0,1] | yes | Higher = better deal |
| `deal_tier` | integer [1,4] | yes | 1=great, 2=good, 3=fair, 4=overpriced |
| `estimated_price_eur` | float64 | yes | ML fair-value estimate |
| `model_version` | string | yes | |
| `scored_at` | RFC3339 | yes | |

---

### `listings.price-change.{country_code}`

Published by: `change-detector` service (Python pipeline)
Stream: `price-changes` (subject pattern: `listings.price-change.>`)
Durable consumer: `alert-engine-price`

```json
{
  "listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "country_code": "ES",
  "old_price_eur": 350000.00,
  "new_price_eur": 320000.00,
  "change_pct": -8.57,
  "changed_at": "2026-04-17T09:00:00Z"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `listing_id` | UUID string | yes | |
| `country_code` | string | yes | Redundant with subject suffix; included for convenience |
| `old_price_eur` | float64 | yes | |
| `new_price_eur` | float64 | yes | |
| `change_pct` | float64 | yes | Negative = price drop |
| `changed_at` | RFC3339 | yes | |

**Alert engine action**: Remove `listing_id` from `alerts:sent:{user_id}` SET for all users who have been previously alerted, enabling re-evaluation on the next scored listing event.

---

## Published Events

### `alerts.notifications.{country_code}`

Published by: `alert-engine`
Stream: `alerts-notifications`
Consumed by: `alert-dispatcher`

#### Instant notification

```json
{
  "event_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "rule_id": "550e8400-e29b-41d4-a716-446655440002",
  "rule_name": "Barcelona apartments under 350k",
  "listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "country_code": "ES",
  "channel": "email",
  "webhook_url": null,
  "frequency": "instant",
  "is_digest": false,
  "deal_score": 0.87,
  "deal_tier": 1,
  "listing_summary": {
    "title": "Bright 3BR apartment in Eixample",
    "price_eur": 320000,
    "area_m2": 95,
    "bedrooms": 3,
    "city": "Barcelona",
    "image_url": "https://cdn.estategap.com/listings/abc/thumb.jpg"
  },
  "triggered_at": "2026-04-17T10:30:05Z"
}
```

#### Digest notification

```json
{
  "event_id": "7c9e6679-7425-40de-944b-e07fc1f90ae8",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "rule_id": "550e8400-e29b-41d4-a716-446655440003",
  "rule_name": "Daily Spain deals",
  "country_code": "ES",
  "channel": "email",
  "webhook_url": null,
  "frequency": "daily",
  "is_digest": true,
  "total_matches": 5,
  "listings": [
    {
      "listing_id": "...",
      "deal_score": 0.92,
      "deal_tier": 1,
      "title": "...",
      "price_eur": 285000,
      "area_m2": 78,
      "bedrooms": 2,
      "city": "Madrid",
      "image_url": null
    }
  ],
  "triggered_at": "2026-04-17T08:00:03Z"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `event_id` | UUID string | yes | Idempotency key for dispatcher |
| `user_id` | UUID string | yes | |
| `rule_id` | UUID string | yes | |
| `rule_name` | string | yes | For human-readable notification |
| `listing_id` | UUID string | if `is_digest=false` | |
| `country_code` | string | yes | Matches subject suffix |
| `channel` | string | yes | email / push / webhook |
| `webhook_url` | string or null | if channel=webhook | |
| `frequency` | string | yes | instant / hourly / daily |
| `is_digest` | boolean | yes | |
| `deal_score` | float64 | if `is_digest=false` | |
| `deal_tier` | integer | if `is_digest=false` | |
| `listing_summary` | object | if `is_digest=false` | |
| `total_matches` | integer | if `is_digest=true` | Count before top-20 truncation |
| `listings` | array | if `is_digest=true` | Up to 20, sorted desc by deal_score |
| `triggered_at` | RFC3339 | yes | |

---

## Stream Configuration (Helm values reference)

Existing streams (already declared in `helm/estategap/values.yaml`):

| Stream | Subjects | Retention | Storage |
|--------|----------|-----------|---------|
| `scored-listings` | `listings.scored.>`, `scored.listings` | 48h | file |
| `price-changes` | `listings.price-change.>` | 48h | file |
| `alerts-notifications` | `alerts.notifications.>` | 168h (7d) | file |

New durable consumers to add:
- Stream `scored-listings` → consumer `alert-engine-scored` (pull, durable, `MaxAckPending=100`)
- Stream `price-changes` → consumer `alert-engine-price` (pull, durable, `MaxAckPending=50`)
