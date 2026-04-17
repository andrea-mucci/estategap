# JSON Contract: Python ↔ Go Serialisation

**Feature**: 005-shared-data-models | **Date**: 2026-04-17

This document defines the exact JSON wire format that Python models produce and Go structs consume (and vice versa). Both sides MUST conform to these rules. Any deviation is a bug.

---

## Encoding Rules

| Concern | Rule | Python | Go |
|---------|------|--------|----|
| Datetimes | RFC 3339 with UTC offset | `AwareDatetime` → `"2026-04-17T10:30:00Z"` | `pgtype.Timestamptz` → marshals as RFC 3339 string |
| UUIDs | Lowercase hyphenated `8-4-4-4-12` | `UUID` → `"550e8400-e29b-41d4-a716-446655440000"` | `pgtype.UUID` → same format |
| Decimals / Prices | JSON number (not string) | `Decimal("450000.12")` → `450000.12` | `decimal.Decimal` → same |
| Nullable fields | JSON `null` | `None` → `null` | `*T` → `null` when nil |
| Booleans | JSON `true` / `false` | `True/False` → `true/false` | `bool` → same |
| Enums | Lowercase string value | `ListingStatus.ACTIVE` → `"active"` | `string` constant → same |
| JSONB blobs | Nested JSON object | `dict` → `{}` | `json.RawMessage` → pass-through |
| Integer IDs (PriceHistory) | JSON number | `int` → `1234` | `int64` → same |

---

## Field Name Mapping

Python uses `snake_case` field names in `model_dump(mode="json")`. Go `json` tags MUST match exactly.

**Critical mappings** (non-obvious):

| Python field | Go tag | DB column |
|-------------|--------|-----------|
| `source_id` | `json:"source_id"` | `source_id` |
| `asking_price_eur` | `json:"asking_price_eur"` | `asking_price_eur` |
| `price_per_m2_eur` | `json:"price_per_m2_eur"` | `price_per_m2_eur` |
| `built_area_m2` | `json:"built_area_m2"` | `built_area_m2` |
| `property_category` | `json:"property_category"` | `property_category` |
| `deal_tier` | `json:"deal_tier"` | `deal_tier` |
| `shap_features` | `json:"shap_features"` | `shap_features` |
| `last_triggered_at` | `json:"last_triggered_at"` | `last_triggered_at` |
| `trigger_count` | `json:"trigger_count"` | `trigger_count` |
| `feature_name` | `json:"feature_name"` | — (JSONB sub-field) |
| `oauth_provider` | `json:"oauth_provider"` | `oauth_provider` |
| `stripe_customer_id` | `json:"stripe_customer_id"` | `stripe_customer_id` |
| `subscription_ends_at` | `json:"subscription_ends_at"` | `subscription_ends_at` |
| `email_verified` | `json:"email_verified"` | `email_verified` |

---

## Canonical JSON Fixtures

Static fixture files in `tests/cross_language/fixtures/` serve as the ground-truth contract. These are the reference values both test suites verify against.

### `listing.json`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "canonical_id": null,
  "country": "ES",
  "source": "idealista",
  "source_id": "abc-123",
  "source_url": "https://www.idealista.com/inmueble/abc-123/",
  "portal_id": null,
  "address": "Calle Mayor 1",
  "neighborhood": null,
  "district": null,
  "city": "Madrid",
  "region": "Comunidad de Madrid",
  "postal_code": "28013",
  "zone_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "asking_price": 450000.00,
  "currency": "EUR",
  "asking_price_eur": 450000.00,
  "price_per_m2_eur": 5625.00,
  "property_category": "residential",
  "property_type": "apartment",
  "built_area_m2": 80.00,
  "usable_area_m2": 75.00,
  "plot_area_m2": null,
  "bedrooms": 3,
  "bathrooms": 2,
  "estimated_price": 420000.00,
  "deal_score": 72.50,
  "deal_tier": 2,
  "confidence_low": 395000.00,
  "confidence_high": 445000.00,
  "shap_features": [
    {"feature_name": "zone_price_median", "value": 15234.5},
    {"feature_name": "area_m2", "value": 8102.3}
  ],
  "model_version": "es-lgbm-v2.1.0",
  "scored_at": "2026-04-17T08:00:00Z",
  "days_on_market": 14,
  "status": "active",
  "images_count": 12,
  "first_seen_at": "2026-04-03T09:15:00Z",
  "last_seen_at": "2026-04-17T06:00:00Z",
  "published_at": "2026-04-03T09:15:00Z",
  "delisted_at": null,
  "created_at": "2026-04-03T09:15:00Z",
  "updated_at": "2026-04-17T06:00:00Z"
}
```

### `alert_rule.json`

```json
{
  "id": "b1c2d3e4-f5a6-7890-bcde-f12345678901",
  "user_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
  "name": "Madrid 3BR under 500k",
  "filters": {
    "country": "ES",
    "city": "Madrid",
    "bedrooms_min": 3,
    "price_max": 500000,
    "deal_tier_max": 2
  },
  "channels": {"email": true},
  "active": true,
  "last_triggered_at": null,
  "trigger_count": 0,
  "created_at": "2026-04-01T12:00:00Z",
  "updated_at": "2026-04-01T12:00:00Z"
}
```

### `scoring_result.json`

```json
{
  "listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "country": "ES",
  "estimated_price": 420000.00,
  "deal_score": 72.50,
  "deal_tier": 2,
  "confidence_low": 395000.00,
  "confidence_high": 445000.00,
  "shap_features": [
    {"feature_name": "zone_price_median", "value": 15234.5},
    {"feature_name": "area_m2", "value": 8102.3},
    {"feature_name": "floor_number", "value": -1203.7}
  ],
  "model_version": "es-lgbm-v2.1.0",
  "scored_at": "2026-04-17T08:00:00Z"
}
```

### `user.json`

```json
{
  "id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
  "email": "user@example.com",
  "password_hash": null,
  "oauth_provider": "google",
  "oauth_subject": "104824398127364892",
  "display_name": "Alice",
  "avatar_url": null,
  "subscription_tier": "pro",
  "stripe_customer_id": "cus_abc123",
  "stripe_sub_id": "sub_xyz789",
  "subscription_ends_at": "2027-04-01T00:00:00Z",
  "alert_limit": 50,
  "email_verified": true,
  "email_verified_at": "2026-03-01T10:00:00Z",
  "last_login_at": "2026-04-16T08:30:00Z",
  "deleted_at": null,
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-04-16T08:30:00Z"
}
```

---

## Round-Trip Test Requirements

### Python test (`tests/cross_language/test_roundtrip.py`)

For each fixture file:
1. Load JSON string from `fixtures/<name>.json`
2. Deserialise into the corresponding Pydantic model
3. Re-serialise with `model_dump_json()`
4. Parse both JSONs and assert all key-value pairs are equal (field-level, not byte-level)

### Go test (`libs/pkg/models/models_test.go` — `TestRoundTrip*`)

For each fixture file:
1. Load JSON bytes from the same fixture path (relative from test binary)
2. `json.Unmarshal` into the corresponding Go struct
3. `json.Marshal` back to bytes
4. Assert field values match expected (use `require.Equal` from `testify`)

---

## Breaking Change Policy

Any change to the JSON contract (field rename, type change, removal) is a **breaking change** and requires:
1. Version bump in `libs/common` and `libs/pkg`
2. Update to the affected fixture(s) in `tests/cross_language/fixtures/`
3. All consuming services updated in the same PR or a coordinated migration
