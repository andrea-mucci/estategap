# API Contracts: Listing & Zone Data Endpoints

**Phase**: 1 — Design  
**Date**: 2026-04-17  
**Base path**: `/api/v1` (served by `services/api-gateway`)  
**Auth**: All endpoints require `Authorization: Bearer <access_token>` (JWT)

---

## Standard Response Envelope

### List Response
```json
{
  "data": [ /* array of resource objects */ ],
  "pagination": {
    "next_cursor": "base64url-opaque-string",
    "has_more": true
  },
  "meta": {
    "total_count": 1234,
    "currency": "EUR"
  }
}
```

### Error Response
```json
{
  "error": "human-readable message",
  "request_id": "uuid"
}
```

---

## GET /api/v1/listings

Search and filter property listings.

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `country` | string | Yes | ISO 3166-1 country code |
| `city` | string | No | Exact city name match |
| `zone_id` | UUID | No | Restrict to listings in this zone (by zone_id column) |
| `property_category` | string | No | `residential`, `commercial`, `industrial`, `land` |
| `property_type` | string | No | Free-form type (e.g. `apartment`, `villa`) |
| `min_price_eur` | number | No | Minimum price in EUR |
| `max_price_eur` | number | No | Maximum price in EUR |
| `min_area_m2` | number | No | Minimum built area in m² |
| `max_area_m2` | number | No | Maximum built area in m² |
| `min_bedrooms` | integer | No | Minimum bedroom count |
| `min_bathrooms` | integer | No | Minimum bathroom count |
| `deal_tier` | integer | No | 1=great, 2=good, 3=fair, 4=overpriced |
| `status` | string | No | `active` (default), `delisted`, `sold` |
| `portal_id` | UUID | No | Filter by source portal |
| `min_days_on_market` | integer | No | |
| `max_days_on_market` | integer | No | |
| `sort_by` | string | No | `recency` (default), `deal_score`, `price`, `price_m2`, `days_on_market` |
| `sort_dir` | string | No | `desc` (default), `asc` |
| `currency` | string | No | ISO 4217 target currency (e.g. `USD`). Default: `EUR` |
| `cursor` | string | No | Opaque cursor from previous response |
| `limit` | integer | No | 1–100, default 20 |

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Currency` | Currency code of converted prices |
| `X-Exchange-Rate-Date` | ISO 8601 date of exchange rate used |

### Response Body (200 OK)

```json
{
  "data": [
    {
      "id": "uuid",
      "source": "idealista",
      "country": "ES",
      "city": "Madrid",
      "address": "Calle Gran Vía 42",
      "asking_price": "450000.00",
      "asking_price_eur": "450000.00",
      "price_converted": "487350.00",
      "currency": "EUR",
      "price_per_m2_eur": "3461.54",
      "area_m2": "130.00",
      "bedrooms": 3,
      "bathrooms": 2,
      "property_category": "residential",
      "property_type": "apartment",
      "deal_score": "0.87",
      "deal_tier": 1,
      "status": "active",
      "days_on_market": 14,
      "photo_url": null,
      "first_seen_at": "2026-04-10T08:22:11Z"
    }
  ],
  "pagination": {
    "next_cursor": "dGltZToxNzQ0...",
    "has_more": true
  },
  "meta": {
    "total_count": 847,
    "currency": "USD"
  }
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 400 | Missing `country`, invalid parameter values |
| 401 | Missing or invalid JWT |
| 503 | Database unavailable |

### Subscription Gating Behaviour

| Tier | Restriction |
|------|------------|
| `free` | Results exclude listings < 48 hours old |
| `basic` | Results restricted to user's allowed countries |
| `pro`, `global`, `api` | Full access |

---

## GET /api/v1/listings/{id}

Retrieve full listing detail.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | Listing ID |

### Response Body (200 OK)

```json
{
  "id": "uuid",
  "source": "idealista",
  "source_url": "https://...",
  "country": "ES",
  "city": "Madrid",
  "address": "Calle Gran Vía 42",
  "zone_id": "uuid",
  "asking_price": "450000.00",
  "asking_price_eur": "450000.00",
  "currency": "EUR",
  "price_per_m2_eur": "3461.54",
  "area_m2": "130.00",
  "usable_area_m2": "120.00",
  "plot_area_m2": null,
  "bedrooms": 3,
  "bathrooms": 2,
  "floor_number": 4,
  "year_built": 1985,
  "condition": "good",
  "energy_rating": "C",
  "has_lift": true,
  "has_pool": false,
  "has_garden": false,
  "property_category": "residential",
  "property_type": "apartment",
  "deal_score": "0.87",
  "deal_tier": 1,
  "confidence_low": "380000.00",
  "confidence_high": "420000.00",
  "estimated_price": "402000.00",
  "model_version": "es-residential-v3.1.0",
  "shap_features": [
    { "feature": "price_vs_zone_median", "value": -0.21, "direction": "positive" },
    { "feature": "days_on_market", "value": 14, "direction": "positive" },
    { "feature": "price_per_m2_vs_city", "value": -0.18, "direction": "positive" },
    { "feature": "bedrooms", "value": 3, "direction": "neutral" },
    { "feature": "year_built", "value": 1985, "direction": "negative" }
  ],
  "status": "active",
  "days_on_market": 14,
  "first_seen_at": "2026-04-10T08:22:11Z",
  "published_at": "2026-04-09T10:00:00Z",
  "price_history": [
    {
      "old_price_eur": null,
      "new_price_eur": "460000.00",
      "change_type": "initial",
      "recorded_at": "2026-04-09T10:00:00Z"
    },
    {
      "old_price_eur": "460000.00",
      "new_price_eur": "450000.00",
      "change_type": "decrease",
      "recorded_at": "2026-04-12T14:30:00Z"
    }
  ],
  "comparable_ids": [
    "uuid-1",
    "uuid-2",
    "uuid-3"
  ],
  "zone_stats": {
    "zone_id": "uuid",
    "zone_name": "Chamberí",
    "listing_count": 412,
    "median_price_m2_eur": 4200.0,
    "deal_count": 23
  }
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 400 | Invalid UUID format |
| 401 | Missing or invalid JWT |
| 404 | Listing not found |

---

## GET /api/v1/zones

List zones with optional filters and summary statistics.

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `country` | string | No | Filter by country code |
| `level` | integer | No | 0–4 hierarchy level |
| `parent_id` | UUID | No | Filter children of this zone |
| `cursor` | string | No | Pagination cursor |
| `limit` | integer | No | 1–100, default 20 |

### Response Body (200 OK)

```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Chamberí",
      "name_local": "Chamberí",
      "country": "ES",
      "level": 4,
      "parent_id": "uuid",
      "slug": "chamberi-madrid",
      "area_km2": 4.67,
      "listing_count": 412,
      "median_price_m2_eur": 4200.0,
      "deal_count": 23,
      "price_trend_pct": -2.1
    }
  ],
  "pagination": {
    "next_cursor": "...",
    "has_more": false
  },
  "meta": {
    "total_count": 847
  }
}
```

---

## GET /api/v1/zones/{id}

Get a single zone with full statistics.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | Zone ID |

### Response Body (200 OK)

Same structure as a single item from `GET /zones` list, with all stats fields populated.

### Error Responses

| Status | Condition |
|--------|-----------|
| 404 | Zone not found |

---

## GET /api/v1/zones/{id}/analytics

Get 12-month monthly time series for a zone.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | Zone ID |

### Response Body (200 OK)

```json
{
  "zone_id": "uuid",
  "months": [
    { "month": "2025-05", "median_price_m2_eur": 4100.0, "listing_volume": 38, "deal_count": 3 },
    { "month": "2025-06", "median_price_m2_eur": 4150.0, "listing_volume": 42, "deal_count": 4 },
    { "month": "2025-07", "median_price_m2_eur": 4080.0, "listing_volume": 29, "deal_count": 2 },
    { "month": "2025-08", "median_price_m2_eur": 0.0,    "listing_volume": 0,  "deal_count": 0 },
    { "month": "2025-09", "median_price_m2_eur": 4120.0, "listing_volume": 35, "deal_count": 3 },
    { "month": "2025-10", "median_price_m2_eur": 4180.0, "listing_volume": 44, "deal_count": 5 },
    { "month": "2025-11", "median_price_m2_eur": 4200.0, "listing_volume": 40, "deal_count": 4 },
    { "month": "2025-12", "median_price_m2_eur": 4220.0, "listing_volume": 37, "deal_count": 4 },
    { "month": "2026-01", "median_price_m2_eur": 4250.0, "listing_volume": 41, "deal_count": 5 },
    { "month": "2026-02", "median_price_m2_eur": 4230.0, "listing_volume": 39, "deal_count": 3 },
    { "month": "2026-03", "median_price_m2_eur": 4210.0, "listing_volume": 43, "deal_count": 4 },
    { "month": "2026-04", "median_price_m2_eur": 4200.0, "listing_volume": 12, "deal_count": 2 }
  ]
}
```

Always returns exactly 12 items. Months with no data return zeros.

---

## GET /api/v1/zones/compare

Side-by-side comparison of 2–5 zones.

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ids` | string | Yes | Comma-separated zone UUIDs (2–5) |

### Response Body (200 OK)

```json
{
  "zones": [
    {
      "id": "uuid-1",
      "name": "Chamberí",
      "country": "ES",
      "level": 4,
      "local_currency": "EUR",
      "listing_count": 412,
      "median_price_m2_eur": 4200.0,
      "median_price_m2_local": 4200.0,
      "deal_count": 23,
      "price_trend_pct": -2.1
    },
    {
      "id": "uuid-2",
      "name": "Baixa",
      "country": "PT",
      "level": 4,
      "local_currency": "EUR",
      "listing_count": 187,
      "median_price_m2_eur": 3800.0,
      "median_price_m2_local": 3800.0,
      "deal_count": 11,
      "price_trend_pct": 1.4
    }
  ]
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 400 | Fewer than 2 or more than 5 IDs; invalid UUID format |
| 404 | Any zone ID not found |

---

## GET /api/v1/countries

List active countries with summary statistics.

### Response Body (200 OK)

```json
{
  "data": [
    {
      "code": "ES",
      "name": "Spain",
      "currency": "EUR",
      "listing_count": 48231,
      "deal_count": 3104,
      "portal_count": 4
    },
    {
      "code": "PT",
      "name": "Portugal",
      "currency": "EUR",
      "listing_count": 12044,
      "deal_count": 892,
      "portal_count": 2
    }
  ],
  "meta": {
    "total_count": 5
  }
}
```

No pagination (expected < 50 active countries).

---

## GET /api/v1/portals

List active portals with health information.

### Response Body (200 OK)

```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Idealista",
      "country": "ES",
      "base_url": "https://www.idealista.com",
      "enabled": true,
      "last_scrape_at": "2026-04-17T06:00:00Z"
    },
    {
      "id": "uuid",
      "name": "Imovirtual",
      "country": "PT",
      "base_url": "https://www.imovirtual.com",
      "enabled": true,
      "last_scrape_at": null
    }
  ],
  "meta": {
    "total_count": 6
  }
}
```

No pagination (expected < 100 active portals). `last_scrape_at` is null if health metadata is not populated.

---

## Route Registration Order (chi)

Routes must be registered in this order to prevent `/zones/compare` being captured by `/zones/{id}`:

```go
r.Get("/zones/compare", zonesHandler.Compare)   // static path first
r.Get("/zones", zonesHandler.List)
r.Get("/zones/{id}", zonesHandler.Get)
r.Get("/zones/{id}/analytics", zonesHandler.Analytics)
```
