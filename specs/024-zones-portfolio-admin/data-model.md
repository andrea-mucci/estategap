# Data Model: Zone Analytics, Portfolio Tracker & Admin Panel

**Feature**: 024-zones-portfolio-admin  
**Date**: 2026-04-17

---

## New Entities

### 1. `portfolio_properties` (PostgreSQL table — new)

Stores manually-entered owned properties for each user.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, default gen_random_uuid() | |
| `user_id` | UUID | NOT NULL, FK → users.id ON DELETE CASCADE | |
| `address` | TEXT | NOT NULL | Free-text address as entered |
| `lat` | DOUBLE PRECISION | NULLABLE | Geocoded by server at creation |
| `lng` | DOUBLE PRECISION | NULLABLE | Geocoded by server at creation |
| `zone_id` | UUID | NULLABLE, FK → zones.id | Matched zone (for ML estimate) |
| `country` | VARCHAR(2) | NOT NULL | ISO 3166-1 alpha-2 |
| `purchase_price` | NUMERIC(18, 4) | NOT NULL, CHECK > 0 | In `purchase_currency` |
| `purchase_currency` | VARCHAR(3) | NOT NULL | ISO 4217 (e.g., EUR, GBP) |
| `purchase_price_eur` | NUMERIC(18, 4) | NOT NULL | EUR-normalised at creation time |
| `purchase_date` | DATE | NOT NULL, CHECK ≤ CURRENT_DATE | |
| `monthly_rental_income` | NUMERIC(18, 4) | NOT NULL, default 0, CHECK ≥ 0 | In `purchase_currency` |
| `monthly_rental_income_eur` | NUMERIC(18, 4) | NOT NULL, default 0 | EUR-normalised |
| `area_m2` | NUMERIC(10, 2) | NULLABLE | Optional, used for ML estimate |
| `property_type` | VARCHAR(20) | NOT NULL, default 'residential' | residential/commercial/land/industrial |
| `notes` | TEXT | NULLABLE | User free-text |
| `created_at` | TIMESTAMPTZ | NOT NULL, default NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default NOW() | Auto-updated via trigger |

**Indexes**:
- `idx_portfolio_properties_user_id` on `user_id`
- `idx_portfolio_properties_country` on `country`

**Validation rules**:
- `purchase_date` must not be in the future
- `purchase_price` and `monthly_rental_income` must be non-negative numbers
- `purchase_currency` must be a valid 3-letter ISO 4217 code

---

### 2. `PortfolioProperty` (Go struct — api-gateway)

```go
type PortfolioProperty struct {
    ID                      uuid.UUID  `json:"id"`
    UserID                  uuid.UUID  `json:"user_id"`
    Address                 string     `json:"address"`
    Lat                     *float64   `json:"lat,omitempty"`
    Lng                     *float64   `json:"lng,omitempty"`
    ZoneID                  *uuid.UUID `json:"zone_id,omitempty"`
    Country                 string     `json:"country"`
    PurchasePrice           float64    `json:"purchase_price"`
    PurchaseCurrency        string     `json:"purchase_currency"`
    PurchasePriceEUR        float64    `json:"purchase_price_eur"`
    PurchaseDate            string     `json:"purchase_date"` // RFC3339 date
    MonthlyRentalIncome     float64    `json:"monthly_rental_income"`
    MonthlyRentalIncomeEUR  float64    `json:"monthly_rental_income_eur"`
    AreaM2                  *float64   `json:"area_m2,omitempty"`
    PropertyType            string     `json:"property_type"`
    Notes                   *string    `json:"notes,omitempty"`
    EstimatedValueEUR       *float64   `json:"estimated_value_eur,omitempty"` // from ML, nullable
    EstimatedAt             *string    `json:"estimated_at,omitempty"`         // RFC3339
    CreatedAt               string     `json:"created_at"`
    UpdatedAt               string     `json:"updated_at"`
}
```

---

### 3. `PortfolioSummary` (Go struct — computed, not persisted)

```go
type PortfolioSummary struct {
    TotalProperties        int     `json:"total_properties"`
    TotalInvestedEUR       float64 `json:"total_invested_eur"`
    TotalCurrentValueEUR   float64 `json:"total_current_value_eur"`   // sum of estimated_value_eur where available
    UnrealizedGainLossEUR  float64 `json:"unrealized_gain_loss_eur"`   // current - invested
    UnrealizedGainLossPct  float64 `json:"unrealized_gain_loss_pct"`   // gain_loss / invested * 100
    AverageRentalYieldPct  float64 `json:"average_rental_yield_pct"`   // (annual_rental / purchase_price) * 100
    PropertiesWithEstimate int     `json:"properties_with_estimate"`
}
```

---

### 4. Extensions to `ZoneAnalytics` schema

The `ZoneMonthStat` struct in `services/api-gateway/internal/repository/zones.go` gains:

| New Field | Type | Description |
|-----------|------|-------------|
| `avg_days_on_market` | float64 | Average days active listings have been listed in this zone for this month |

The `months` array item in the API response gains `avg_days_on_market: number`.

New endpoint response type:

```typescript
// ZonePriceDistribution — returned by GET /api/v1/zones/{id}/price-distribution
{
  zone_id: string;
  prices_eur: number[]; // up to 500 current listing price_per_m2_eur values
  listing_count: number; // total active listings (may exceed 500)
}
```

---

### 5. Admin data structures (Go structs — not persisted, query-time assembled)

```go
// ScrapingPortalStat — one row per portal per country
type ScrapingPortalStat struct {
    PortalID     string    `json:"portal_id"`
    PortalName   string    `json:"portal_name"`
    Country      string    `json:"country"`
    Status       string    `json:"status"`    // "active" | "error" | "paused"
    LastScrapeAt *string   `json:"last_scrape_at,omitempty"`
    Listings24h  int64     `json:"listings_24h"`
    SuccessRate  float64   `json:"success_rate"` // 0.0–1.0
    Blocks24h    int64     `json:"blocks_24h"`
}

// MLModelVersion — one row per country × model version
type MLModelVersion struct {
    ID          uuid.UUID `json:"id"`
    Country     string    `json:"country"`
    Version     string    `json:"version"`
    MAPE        float64   `json:"mape"`
    MAE         float64   `json:"mae"`
    R2          float64   `json:"r2"`
    TrainedAt   string    `json:"trained_at"`
    IsActive    bool      `json:"is_active"`
    TrainStatus string    `json:"train_status"` // "idle" | "training" | "failed"
}

// AdminUser — one row per user
type AdminUser struct {
    ID               uuid.UUID  `json:"id"`
    Email            string     `json:"email"`
    Name             *string    `json:"name,omitempty"`
    Role             string     `json:"role"`
    SubscriptionTier string     `json:"subscription_tier"`
    LastActiveAt     *string    `json:"last_active_at,omitempty"`
    CreatedAt        string     `json:"created_at"`
}

// CountryConfig — one row per country
type CountryConfig struct {
    Code        string          `json:"code"`
    Name        string          `json:"name"`
    Enabled     bool            `json:"enabled"`
    Portals     []PortalConfig  `json:"portals"`
}

type PortalConfig struct {
    ID      string `json:"id"`
    Name    string `json:"name"`
    Enabled bool   `json:"enabled"`
    Config  any    `json:"config"` // arbitrary JSON from DB
}

// SystemHealth — aggregated system snapshot
type SystemHealth struct {
    NATS     NATSHealth     `json:"nats"`
    Database DatabaseHealth `json:"database"`
    Redis    RedisHealth    `json:"redis"`
}

type NATSHealth struct {
    Subjects []NATSSubjectStat `json:"subjects"`
}
type NATSSubjectStat struct {
    Subject      string `json:"subject"`
    ConsumerLag  int64  `json:"consumer_lag"`
    MessageCount int64  `json:"message_count"`
}

type DatabaseHealth struct {
    SizeBytes        int64 `json:"size_bytes"`
    ActiveConns      int   `json:"active_connections"`
    MaxConns         int   `json:"max_connections"`
    WaitingConns     int   `json:"waiting_connections"`
}

type RedisHealth struct {
    UsedMemoryBytes  int64   `json:"used_memory_bytes"`
    MaxMemoryBytes   int64   `json:"max_memory_bytes"`
    HitRate          float64 `json:"hit_rate"`      // keyspace_hits / (hits + misses)
    ConnectedClients int     `json:"connected_clients"`
}
```

---

### 6. JWT Claims Extension

`AccessTokenClaims` in `services/api-gateway/internal/service/auth.go` gains:

```go
Role string `json:"role"` // "user" | "admin"
```

Populated at login/register: `role = "admin"` if `email` ends with `@estategap.com`, else `"user"`.

---

### 7. Users table extension

New column on the `users` table (Alembic migration):

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `preferred_currency` | VARCHAR(3) | `'EUR'` | ISO 4217 currency code |

Exposed in `GET /api/v1/auth/me` response. Settable via `PATCH /api/v1/auth/me { preferred_currency: string }`.

---

## State Transitions

### Portfolio Property lifecycle

```
(none) → CREATED (POST /portfolio/properties)
       → UPDATED (PUT /portfolio/properties/{id})
       → DELETED (DELETE /portfolio/properties/{id})
```

ML estimate is fetched on-demand; it is not a state but an optional derived field populated when `lat`/`lng`/`area_m2` are available and a zone is matched.

### Admin Retrain lifecycle

```
idle → QUEUED (POST /admin/ml/retrain → publishes NATS msg)
     → TRAINING (ml-trainer picks up message, updates model_versions.train_status)
     → idle (training complete) or FAILED (training error)
```

The api-gateway does not track retrain status beyond the initial `{ job_id, status: "queued" }` response. The admin ML tab polls `GET /admin/ml/models` to see `train_status` updates.
