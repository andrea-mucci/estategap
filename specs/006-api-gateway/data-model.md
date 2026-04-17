# Data Model: API Gateway

**Date**: 2026-04-17  
**Branch**: `006-api-gateway`

The gateway does not own its own database schema — it consumes the shared schema defined in `epic-01-database/feature-01-schema-and-migrations`. This document describes the entities the gateway reads/writes and the ephemeral Redis structures it manages.

---

## PostgreSQL Entities (existing schema)

### users

Primary entity for authentication and authorization.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | Generated |
| `email` | TEXT UNIQUE NOT NULL | Registration and OAuth identifier |
| `password_hash` | TEXT NULLABLE | NULL for OAuth-only accounts |
| `oauth_provider` | TEXT NULLABLE | e.g., `"google"` |
| `oauth_subject` | TEXT NULLABLE | Google `sub` claim |
| `display_name` | TEXT NULLABLE | From OAuth profile or user-set |
| `avatar_url` | TEXT NULLABLE | From OAuth profile |
| `subscription_tier` | ENUM | `free` \| `basic` \| `pro` \| `global` \| `api` |
| `stripe_customer_id` | TEXT NULLABLE | Stripe billing reference |
| `stripe_sub_id` | TEXT NULLABLE | Active Stripe subscription ID |
| `subscription_ends_at` | TIMESTAMPTZ NULLABLE | For billing cutoff enforcement |
| `alert_limit` | SMALLINT | Max concurrent active alert rules |
| `email_verified` | BOOLEAN DEFAULT FALSE | Email verification state |
| `email_verified_at` | TIMESTAMPTZ NULLABLE | When verification was confirmed |
| `last_login_at` | TIMESTAMPTZ NULLABLE | Updated on every successful login |
| `deleted_at` | TIMESTAMPTZ NULLABLE | Soft delete; excluded from queries when set |
| `created_at` | TIMESTAMPTZ NOT NULL | Auto-set |
| `updated_at` | TIMESTAMPTZ NOT NULL | Auto-updated |

**Write queries** (primary pool):
- `INSERT INTO users (email, password_hash, ...) RETURNING *` — register
- `UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE id = $1` — login
- `UPDATE users SET oauth_provider = $1, oauth_subject = $2, ... WHERE id = $3` — link OAuth
- `INSERT INTO users (email, oauth_provider, oauth_subject, ...) RETURNING *` — OAuth register

**Read queries** (replica pool):
- `SELECT * FROM users WHERE email = $1 AND deleted_at IS NULL` — login lookup
- `SELECT * FROM users WHERE oauth_provider = $1 AND oauth_subject = $2` — OAuth lookup
- `SELECT id, subscription_tier, alert_limit FROM users WHERE id = $1` — token validation enrichment

---

### alert_rules

Alert CRUD managed by the gateway.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | Generated |
| `user_id` | UUID FK → users.id | Owner |
| `name` | TEXT NOT NULL | User-defined label |
| `filters` | JSONB | Search filter criteria |
| `channels` | JSONB | Delivery channels (email, push, etc.) |
| `active` | BOOLEAN DEFAULT TRUE | Enabled/disabled |
| `last_triggered_at` | TIMESTAMPTZ NULLABLE | Populated by alert engine via NATS |
| `trigger_count` | INT DEFAULT 0 | Lifetime trigger counter |
| `created_at` | TIMESTAMPTZ NOT NULL | Auto-set |
| `updated_at` | TIMESTAMPTZ NOT NULL | Auto-updated |

**Access pattern**: Full CRUD on primary; list/get on replica.

---

### listings (read-only at gateway)

Queried but never mutated by the gateway. All writes come from the data pipeline service.

Key fields surfaced in API responses: `id`, `country`, `city`, `address`, `asking_price`, `asking_price_eur`, `price_per_m2_eur`, `property_category`, `built_area_m2`, `bedrooms`, `bathrooms`, `deal_score`, `deal_tier`, `status`, `images_count`, `first_seen_at`.

**Access pattern**: Read replica only. Queries are filtered by `country`, `city`, `status`, price range, area range, `deal_tier`. Pagination via keyset (cursor on `(first_seen_at, id)`).

---

### zones (read-only at gateway)

Zone reference data and analytics. Written by the data pipeline; read by the gateway.

**Access pattern**: Read replica. GET by ID, list with country filter, analytics aggregates.

---

## Redis Structures (gateway-owned)

### Refresh Token Store

```
Key:   refresh:{uuid}
Value: {user_id}           (string, UUID)
TTL:   7 days (604800s)
```

Set on login/register. Deleted on logout. Checked on token refresh. SETNX not required — overwrite is acceptable (rotation replaces the old key).

---

### Access Token Blacklist

```
Key:   blacklist:{jti}
Value: "1"
TTL:   remaining access token lifetime (max 900s)
```

Set on logout. Checked in auth middleware on every request. Using the JWT ID claim (`jti`) as the blacklist key, which is a random UUID embedded in every access token.

---

### OAuth2 State Nonce

```
Key:   oauth:state:{nonce}
Value: {redirect_url}      (optional, for post-login redirect)
TTL:   10 minutes (600s)
```

Set when `/v1/auth/google` is called. Deleted (via GET + DEL) when callback is received. GETDEL ensures atomic read-and-delete.

---

### Rate Limit Counter

```
Key:   ratelimit:{user_id}
Value: integer counter
TTL:   60 seconds (set via EXPIRE on first INCR)
```

INCR on each authenticated request. If result > tier limit → reject with 429. `Retry-After` = key remaining TTL from Redis `PTTL`.

**Tier limits**:

| Tier   | Max count/window |
|--------|-----------------|
| free   | 30              |
| basic  | 120             |
| pro    | 300             |
| global | 600             |
| api    | 1200            |

---

## JWT Access Token Payload

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "tier": "pro",
  "jti": "random-uuid-for-blacklist",
  "iat": 1713340800,
  "exp": 1713341700
}
```

| Claim | Type | Notes |
|-------|------|-------|
| `sub` | string | User UUID |
| `email` | string | User email |
| `tier` | string | Subscription tier (for rate limit lookup in middleware) |
| `jti` | string | Random UUID for blacklist key |
| `iat` | int64 | Issued-at Unix timestamp |
| `exp` | int64 | Expiry Unix timestamp (iat + 900) |

The auth middleware extracts `sub`, `email`, `tier`, and `jti` and stores them in the request context. Rate limit middleware reads `sub` and `tier` from context.

---

## State Transitions

### Session Lifecycle

```
[unauthenticated]
      │  POST /v1/auth/register or /v1/auth/login or OAuth2 callback
      ▼
[tokens issued]  ─── access token valid 15min ──► [access token expired]
      │                                                    │
      │  POST /v1/auth/refresh (valid refresh token)       │  POST /v1/auth/refresh
      ▼                                                    ▼
[new tokens issued]                               [401 - must re-login]
      │
      │  POST /v1/auth/logout
      ▼
[refresh token deleted, access token blacklisted]
```

### Rate Limit State per User per Minute

```
[counter = 0, no key in Redis]
      │  first request in window
      ▼
[counter = 1, TTL = 60s]
      │  subsequent requests
      ▼
[counter increments ...]
      │  counter > tier_limit
      ▼
[429 returned, Retry-After = remaining TTL]
      │  TTL expires
      ▼
[counter = 0, no key in Redis]  (window resets)
```
