# Data Model: Listing & Zone Data Endpoints

**Phase**: 1 — Design  
**Date**: 2026-04-17  
**Feature**: specs/007-listing-zone-endpoints

---

## Existing Models (Read-Only)

All models are read from existing database tables. No new tables are created by this feature.

### `listings` (partitioned by country)

Key columns used in this feature:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `country` | text | Partition key, always required |
| `source` | text | Portal slug (e.g. "idealista") |
| `portal_id` | UUID? | FK to portals |
| `zone_id` | UUID? | FK to zones; populated by pipeline |
| `location` | geometry(Point) | PostGIS point; used for ST_Within fallback |
| `asking_price` | numeric | Original currency |
| `currency` | text | ISO 4217 |
| `asking_price_eur` | numeric | EUR-normalised |
| `price_per_m2_eur` | numeric | EUR per m² |
| `property_category` | text | residential/commercial/industrial/land |
| `property_type` | text | Free-form (e.g. "apartment", "villa") |
| `built_area_m2` | numeric | |
| `bedrooms` | int2 | |
| `bathrooms` | int2 | |
| `deal_score` | numeric | 0–1 ML score |
| `deal_tier` | int2 | 1=great, 2=good, 3=fair, 4=overpriced |
| `confidence_low` | numeric | Lower bound of price estimate |
| `confidence_high` | numeric | Upper bound |
| `shap_features` | jsonb | Array of `{feature, value, direction}` |
| `days_on_market` | int4 | Computed; may be NULL |
| `status` | text | active/delisted/sold |
| `first_seen_at` | timestamptz | Used for recency sort and free-tier gate |
| `published_at` | timestamptz | Portal publish date |

### `price_history` (partitioned by country)

| Column | Type | Notes |
|--------|------|-------|
| `id` | int8 | |
| `listing_id` | UUID | FK to listings |
| `country` | text | Partition key |
| `old_price` | numeric? | |
| `new_price` | numeric | |
| `currency` | text | |
| `old_price_eur` | numeric? | |
| `new_price_eur` | numeric? | |
| `change_type` | text | initial/increase/decrease/status_change |
| `old_status` | text? | |
| `new_status` | text? | |
| `recorded_at` | timestamptz | Used for 12-month grouping |

### `zones`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | |
| `name` | text | English name |
| `name_local` | text? | Local-language name |
| `country_code` | text | ISO 3166-1 |
| `level` | int2 | 0=country, 1=region, 2=province, 3=city, 4=neighbourhood |
| `parent_id` | UUID? | Self-referential |
| `geometry` | geometry(MultiPolygon) | PostGIS; used for ST_Within |
| `area_km2` | numeric? | |
| `slug` | text? | URL-friendly |

### `zone_statistics` (materialized view)

| Column | Type | Notes |
|--------|------|-------|
| `zone_id` | UUID | |
| `country_code` | text | |
| `listing_count` | int8 | Active listings |
| `median_price_m2_eur` | numeric | |
| `deal_count` | int8 | deal_tier IN (1,2) |
| `price_trend_pct` | numeric? | Month-over-month % change |

### `countries`

| Column | Type | Notes |
|--------|------|-------|
| `code` | text | ISO 3166-1 (PK) |
| `name` | text | |
| `currency` | text | ISO 4217 |
| `active` | bool | Filter: active = true |
| `config` | jsonb | |

### `portals`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | |
| `name` | text | |
| `country_code` | text | |
| `base_url` | text | |
| `spider_class` | text | Internal identifier |
| `enabled` | bool | |
| `config` | jsonb | Health metadata (last_scrape_at if populated by orchestrator) |

### `exchange_rates`

| Column | Type | Notes |
|--------|------|-------|
| `currency` | text | ISO 4217 |
| `date` | date | |
| `rate_to_eur` | numeric | 1 unit of currency = rate_to_eur EUR |

---

## New Go Structs (Handler Layer)

These are response payload structs in `internal/handler/`. They are not DB models.

### Listing Summary (search results)

```go
type listingSummaryPayload struct {
    ID               string           `json:"id"`
    Source           string           `json:"source"`
    Country          string           `json:"country"`
    City             *string          `json:"city,omitempty"`
    Address          *string          `json:"address,omitempty"`
    AskingPrice      *decimal.Decimal `json:"asking_price,omitempty"`
    AskingPriceEUR   *decimal.Decimal `json:"asking_price_eur,omitempty"`
    PriceConverted   *decimal.Decimal `json:"price_converted,omitempty"`
    Currency         string           `json:"currency"`
    PricePerM2EUR    *decimal.Decimal `json:"price_per_m2_eur,omitempty"`
    BuiltAreaM2      *decimal.Decimal `json:"area_m2,omitempty"`
    Bedrooms         *int16           `json:"bedrooms,omitempty"`
    Bathrooms        *int16           `json:"bathrooms,omitempty"`
    PropertyCategory *string          `json:"property_category,omitempty"`
    PropertyType     *string          `json:"property_type,omitempty"`
    DealScore        *decimal.Decimal `json:"deal_score,omitempty"`
    DealTier         *models.DealTier `json:"deal_tier,omitempty"`
    Status           string           `json:"status"`
    DaysOnMarket     *int32           `json:"days_on_market,omitempty"`
    PhotoURL         *string          `json:"photo_url,omitempty"`
    FirstSeenAt      string           `json:"first_seen_at"`
}
```

### Listing Detail

```go
type listingDetailPayload struct {
    listingSummaryPayload
    // Extra fields for detail view
    ZoneID          *string              `json:"zone_id,omitempty"`
    SourceURL       string               `json:"source_url"`
    UsableAreaM2    *decimal.Decimal     `json:"usable_area_m2,omitempty"`
    PlotAreaM2      *decimal.Decimal     `json:"plot_area_m2,omitempty"`
    FloorNumber     *int16               `json:"floor_number,omitempty"`
    YearBuilt       *int16               `json:"year_built,omitempty"`
    Condition       *string              `json:"condition,omitempty"`
    EnergyRating    *string              `json:"energy_rating,omitempty"`
    HasLift         *bool                `json:"has_lift,omitempty"`
    HasPool         *bool                `json:"has_pool,omitempty"`
    HasGarden       *bool                `json:"has_garden,omitempty"`
    EstimatedPrice  *decimal.Decimal     `json:"estimated_price,omitempty"`
    ConfidenceLow   *decimal.Decimal     `json:"confidence_low,omitempty"`
    ConfidenceHigh  *decimal.Decimal     `json:"confidence_high,omitempty"`
    ShapFeatures    json.RawMessage      `json:"shap_features,omitempty"`
    ModelVersion    *string              `json:"model_version,omitempty"`
    PublishedAt     *string              `json:"published_at,omitempty"`
    PriceHistory    []priceHistoryItem   `json:"price_history"`
    Comparables     []string             `json:"comparable_ids"`
    ZoneStats       *zoneSummaryStats    `json:"zone_stats,omitempty"`
}

type priceHistoryItem struct {
    OldPriceEUR *decimal.Decimal `json:"old_price_eur,omitempty"`
    NewPriceEUR *decimal.Decimal `json:"new_price_eur,omitempty"`
    ChangeType  string           `json:"change_type"`
    RecordedAt  string           `json:"recorded_at"`
}

type zoneSummaryStats struct {
    ZoneID          string   `json:"zone_id"`
    ZoneName        string   `json:"zone_name"`
    ListingCount    int64    `json:"listing_count"`
    MedianPriceM2   float64  `json:"median_price_m2_eur"`
    DealCount       int64    `json:"deal_count"`
}
```

### Zone Detail

```go
type zoneDetailPayload struct {
    ID             string   `json:"id"`
    Name           string   `json:"name"`
    NameLocal      *string  `json:"name_local,omitempty"`
    Country        string   `json:"country"`
    Level          int16    `json:"level"`
    ParentID       *string  `json:"parent_id,omitempty"`
    Slug           *string  `json:"slug,omitempty"`
    AreaKm2        *float64 `json:"area_km2,omitempty"`
    ListingCount   int64    `json:"listing_count"`
    MedianPriceM2  float64  `json:"median_price_m2_eur"`
    DealCount      int64    `json:"deal_count"`
    PriceTrendPct  *float64 `json:"price_trend_pct,omitempty"`
}
```

### Zone Monthly Stat (analytics)

```go
type zoneMonthlyStatPayload struct {
    Month           string  `json:"month"`           // "2025-05"
    MedianPriceM2   float64 `json:"median_price_m2_eur"`
    ListingVolume   int64   `json:"listing_volume"`
    DealCount       int64   `json:"deal_count"`
}

type zoneAnalyticsResponse struct {
    ZoneID  string                   `json:"zone_id"`
    Months  []zoneMonthlyStatPayload `json:"months"`  // always 12 items
}
```

### Zone Compare

```go
type zoneComparePayload struct {
    Zones []zoneCompareItem `json:"zones"`
}

type zoneCompareItem struct {
    zoneDetailPayload
    LocalCurrency   string   `json:"local_currency"`
    MedianPriceM2Local *float64 `json:"median_price_m2_local,omitempty"`
}
```

### Country Summary

```go
type countryPayload struct {
    Code         string `json:"code"`
    Name         string `json:"name"`
    Currency     string `json:"currency"`
    ListingCount int64  `json:"listing_count"`
    DealCount    int64  `json:"deal_count"`
    PortalCount  int64  `json:"portal_count"`
}
```

### Portal

```go
type portalPayload struct {
    ID           string  `json:"id"`
    Name         string  `json:"name"`
    Country      string  `json:"country"`
    BaseURL      string  `json:"base_url"`
    Enabled      bool    `json:"enabled"`
    LastScrapeAt *string `json:"last_scrape_at,omitempty"`
}
```

---

## New Repository Structs

### `repository.ListingFilter` — extended

```go
type ListingFilter struct {
    // Existing
    Country          string
    City             string
    MinPriceEUR      *float64
    MaxPriceEUR      *float64
    MinAreaM2        *float64
    MaxAreaM2        *float64
    PropertyCategory *models.PropertyCategory
    DealTier         *models.DealTier
    Status           *models.ListingStatus
    Cursor           string
    Limit            int
    // New
    ZoneID           *uuid.UUID
    PropertyType     string
    MinBedrooms      *int
    MinBathrooms     *int
    PortalID         *uuid.UUID
    MinDaysOnMarket  *int
    MaxDaysOnMarket  *int
    SortBy           string   // "recency" | "deal_score" | "price" | "price_m2" | "days_on_market"
    SortDir          string   // "asc" | "desc"
    Currency         string   // ISO 4217; empty = EUR
    FreeTierGate     bool     // true = add 48h filter
    AllowedCountries []string // non-nil = restrict to these countries (basic tier)
}
```

### `repository.ListingDetail`

```go
type ListingDetail struct {
    Listing      models.Listing
    PriceHistory []models.PriceHistory
    Comparables  []uuid.UUID
    ZoneStats    *ZoneStats
}

type ZoneStats struct {
    ZoneID        uuid.UUID
    ZoneName      string
    ListingCount  int64
    MedianPriceM2 float64
    DealCount     int64
}
```

### `repository.ZoneMonthStat`

```go
type ZoneMonthStat struct {
    Month         time.Time
    MedianPriceM2 float64
    ListingVolume int64
    DealCount     int64
}
```

### `repository.CountrySummary`

```go
type CountrySummary struct {
    Code         string
    Name         string
    Currency     string
    ListingCount int64
    DealCount    int64
    PortalCount  int64
}
```

---

## Standard Response Envelope

All list endpoints use this envelope structure:

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "base64string",
    "has_more": true
  },
  "meta": {
    "total_count": 1234,
    "currency": "EUR"
  }
}
```

Single-resource endpoints (`GET /listings/{id}`, `GET /zones/{id}`) return the object directly (no envelope).

---

## State Transitions

No state mutations occur in this feature. All endpoints are read-only.

---

## Validation Rules

| Parameter | Rule |
|-----------|------|
| `country` | Required for `/listings`, optional for `/zones` |
| `currency` | Must be 3-letter ISO 4217 code; unknown codes fall back to EUR |
| `sort_by` | Must be one of: `recency`, `deal_score`, `price`, `price_m2`, `days_on_market` |
| `sort_dir` | Must be `asc` or `desc`; default `desc` |
| `limit` | 1–100; default 20 |
| `zone_id` (compare) | 2–5 valid UUIDs; comma-separated |
| `level` (zones) | 0–4 integer |
| `deal_tier` | 1–4 integer |
| `status` | `active`, `delisted`, or `sold` |
