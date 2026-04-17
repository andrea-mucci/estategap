# Contract: API Endpoints Coverage (E2E Test Reference)

**Source of truth**: `services/api-gateway/cmd/routes.go` + `services/api-gateway/internal/docs/openapi.yaml`  
**Base URL**: `http://localhost:8080/api/v1`

This document maps every documented endpoint to its corresponding E2E test file and key scenarios.

---

## Auth Endpoints (`tests/e2e/api/test_auth.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `POST` | `/auth/register` | No | Happy path, duplicate email → 409, invalid email → 400 |
| `POST` | `/auth/login` | No | Valid credentials → 200 + tokens, wrong password → 401, unknown email → 401 |
| `POST` | `/auth/refresh` | No | Valid refresh token → new access token, expired refresh → 401 |
| `POST` | `/auth/logout` | Yes | Valid token → 200 + blacklist, no token → 401 |
| `GET` | `/auth/me` | Yes | Returns user profile, expired token → 401, invalid signature → 401, missing token → 401 |
| `PATCH` | `/auth/me` | Yes | Update display_name, update preferred_currency, invalid field → 400 |
| `GET` | `/auth/google` | No | Redirects to Google OAuth URL |
| `GET` | `/auth/google/callback` | No | Mocked callback with `code` param → JWT issued, invalid `state` → 400 |

---

## Listings Endpoints (`tests/e2e/api/test_listings.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `GET` | `/listings` | Yes | Happy path with no filters, each filter in isolation, filter combinations, pagination (empty, single page, exact boundary), `?currency=USD`, free tier delay verified |
| `GET` | `/listings/{id}` | Yes | Known ID → 200, unknown ID → 404, basic tier country restriction |
| `GET` | `/listings/top-deals` | Yes | Returns top-scored listings, tier gating |

### Listing Filters (each tested in isolation and in combination)

- `country_code` — single value, multiple values
- `city` — exact match
- `min_price`, `max_price` — boundary values
- `min_area_m2`, `max_area_m2`
- `min_bedrooms`, `max_bedrooms`
- `property_type` — `residential`, `commercial`, `land`
- `portal_id`
- `sort_by` — `price_asc`, `price_desc`, `area_asc`, `deal_score_desc`
- `page`, `page_size` — pagination cursor

---

## Zones Endpoints (`tests/e2e/api/test_zones.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `GET` | `/zones` | Yes | List with country filter, pagination |
| `POST` | `/zones` | Yes | Create custom zone with GeoJSON, duplicate name → 409 |
| `GET` | `/zones/{id}` | Yes | Known ID, unknown ID → 404 |
| `GET` | `/zones/{id}/stats` | Yes | Returns zone statistics |
| `GET` | `/zones/{id}/analytics` | Yes | Returns time-series analytics |
| `GET` | `/zones/{id}/price-distribution` | Yes | Returns histogram data |
| `GET` | `/zones/{id}/geometry` | Yes | Returns GeoJSON |
| `GET` | `/zones/compare` | Yes | Two zone IDs → comparison response |

---

## Dashboard Endpoints (`tests/e2e/api/test_listings.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `GET` | `/dashboard/summary` | Yes | Returns cards with numeric counts, country tab filter |

---

## Reference Endpoints (`tests/e2e/api/test_reference.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `GET` | `/countries` | Yes | Non-empty list with `code`, `name` fields |
| `GET` | `/portals` | Yes | Non-empty list with `id`, `name`, `country_code` fields |

---

## ML Endpoints (`tests/e2e/api/test_ml.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `GET` | `/model/estimate` | Yes | Valid listing params → score + SHAP values, missing required param → 400 |

---

## Alert Rule Endpoints (`tests/e2e/api/test_alerts.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `GET` | `/alerts/rules` | Yes | List rules for current user |
| `POST` | `/alerts/rules` | Yes | Create rule, free tier limit enforcement |
| `PUT` | `/alerts/rules/{id}` | Yes | Update rule, other user's rule → 403 |
| `DELETE` | `/alerts/rules/{id}` | Yes | Delete own rule, other user's rule → 403 |
| `GET` | `/alerts/history` | Yes | List past trigger events |

---

## Subscription Endpoints (`tests/e2e/api/test_subscriptions.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `POST` | `/subscriptions/checkout` | Yes | Returns Stripe Checkout URL |
| `POST` | `/subscriptions/portal` | Yes | Returns Stripe Customer Portal URL |
| `GET` | `/subscriptions/me` | Yes | Returns current tier, renewal date |

---

## Portfolio Endpoints (`tests/e2e/api/test_portfolio.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `GET` | `/portfolio/properties` | Yes | List user's portfolio, empty state |
| `POST` | `/portfolio/properties` | Yes | Add listing to portfolio |
| `PUT` | `/portfolio/properties/{id}` | Yes | Update CRM status |
| `DELETE` | `/portfolio/properties/{id}` | Yes | Remove from portfolio |

---

## Admin Endpoints (`tests/e2e/api/test_admin.py`)

| Method | Path | Auth Required | Admin Required | Test Scenarios |
|--------|------|---------------|----------------|----------------|
| `GET` | `/admin/scraping/stats` | Yes | Yes | Returns scraping metrics; non-admin → 403 |
| `GET` | `/admin/ml/models` | Yes | Yes | Returns model versions; non-admin → 403 |
| `POST` | `/admin/ml/retrain` | Yes | Yes | Triggers retrain job; non-admin → 403 |
| `GET` | `/admin/users` | Yes | Yes | Paginated user list; non-admin → 403 |
| `GET` | `/admin/countries` | Yes | Yes | Returns country config |
| `PUT` | `/admin/countries/{code}` | Yes | Yes | Update country settings |
| `GET` | `/admin/system/health` | Yes | Yes | System health summary |

---

## GDPR Endpoints (`tests/e2e/api/test_auth.py`)

| Method | Path | Auth Required | Test Scenarios |
|--------|------|---------------|----------------|
| `GET` | `/me/export` | Yes | Returns data export ZIP; unauthenticated → 401 |
| `DELETE` | `/me` | Yes | Soft-deletes user account; requires confirmation body |

---

## Rate Limiting (`tests/e2e/api/test_rate_limiting.py`)

| Tier | Limit | Test: Requests Sent | Expected: First N | Expected: N+1 |
|------|-------|--------------------|--------------------|----------------|
| Free | 30/min | 35 | 200 OK | 429 + Retry-After |
| Basic | 120/min | 125 | 200 OK | 429 + Retry-After |
| Pro | 300/min | 305 | 200 OK | 429 + Retry-After |
| Global | 600/min | 605 | 200 OK | 429 + Retry-After |
| API | 1200/min | 1205 | 200 OK | 429 + Retry-After |

The `Retry-After` header must be present and contain a positive integer (seconds until reset).

---

## Error Response Shape (`tests/e2e/api/test_errors.py`)

All error responses must match:

```json
{
  "error": {
    "code": "VALIDATION_ERROR | NOT_FOUND | FORBIDDEN | CONFLICT | INTERNAL_ERROR",
    "message": "Human-readable description",
    "details": [ ]
  }
}
```

- `400`: `code = "VALIDATION_ERROR"`, `details` array with field-level errors
- `401`: `code = "UNAUTHORIZED"`
- `403`: `code = "FORBIDDEN"`
- `404`: `code = "NOT_FOUND"`
- `409`: `code = "CONFLICT"`
- `429`: `code = "RATE_LIMITED"` + `Retry-After` header
- `500`: `code = "INTERNAL_ERROR"` — message must not expose stack traces
