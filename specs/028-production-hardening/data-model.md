# Data Model: Production Hardening (028)

**Branch**: `028-production-hardening` | **Date**: 2026-04-17

## Overview

No new tables. All changes are additive:
- One new nullable column on the existing `users` table (`anonymized_at`)
- New Redis key namespaces (no schema, TTL-managed)
- New client cookie (`eg_consent`, no server-side persistence)

## PostgreSQL Changes

### `users` table — new column

```sql
ALTER TABLE users
  ADD COLUMN anonymized_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN users.anonymized_at IS
  'Set when PII fields are overwritten during GDPR account deletion. NULL = not anonymised.';
```

**Existing columns used by this feature (no change):**

| Column | Type | Role in this feature |
|--------|------|----------------------|
| `id` | UUID | Export + deletion identifier |
| `email` | TEXT | Overwritten to `deleted-{uuid}@deleted.invalid` on anonymisation |
| `name` | TEXT | Overwritten to `Deleted User` on anonymisation |
| `avatar_url` | TEXT | Set to NULL on anonymisation |
| `deleted_at` | TIMESTAMPTZ | Soft-delete timestamp (already present); CronJob filter for hard-delete |

### New Alembic migration

File: `services/pipeline/alembic/versions/028_add_performance_indexes.py`

```python
"""028 add performance indexes and anonymized_at column

Revision ID: 028
"""

def upgrade():
    # anonymized_at for GDPR deletion tracking
    op.add_column('users', sa.Column('anonymized_at', sa.TIMESTAMPTZ(), nullable=True))

    # Listing search: country + status + recency
    op.create_index(
        'ix_listings_country_status_created',
        'listings',
        ['country_code', 'status', sa.text('created_at DESC')]
    )

    # Top deals: zone + score, active listings only (partial index)
    op.execute("""
        CREATE INDEX CONCURRENTLY ix_listings_zone_score_active
        ON listings (zone_id, score_value DESC)
        WHERE status = 'active'
    """)

    # Alert rules hot path: active rules only (partial index)
    op.execute("""
        CREATE INDEX CONCURRENTLY ix_alert_rules_user_active
        ON alert_rules (user_id)
        WHERE is_active = true
    """)

    # Alert history: user + recency for export and dashboard
    op.create_index(
        'ix_alert_history_user_created',
        'alert_history',
        ['user_id', sa.text('created_at DESC')]
    )


def downgrade():
    op.drop_index('ix_alert_history_user_created', table_name='alert_history')
    op.drop_index('ix_alert_rules_user_active', table_name='alert_rules')
    op.drop_index('ix_listings_zone_score_active', table_name='listings')
    op.drop_index('ix_listings_country_status_created', table_name='listings')
    op.drop_column('users', 'anonymized_at')
```

*Note: Partial indexes use `CREATE INDEX CONCURRENTLY` to avoid table locks on a live system. `op.execute` is used because SQLAlchemy's `op.create_index` doesn't support `WHERE` clauses on all backends.*

## Redis Key Spaces (new)

All keys are set by the API Gateway cache middleware. No persistence — ephemeral by design.

| Key Pattern | TTL | Value | Set By |
|-------------|-----|-------|--------|
| `cache:zone-stats:{sha256_hex}` | 300s | JSON (zone statistics response) | api-gateway zone-stats handler |
| `cache:top-deals:{sha256_hex}` | 60s | JSON (top deals response) | api-gateway top-deals handler |
| `cache:alert-rules:{sha256_hex}` | 60s | JSON (alert rules response) | api-gateway alert-rules handler |
| `auth:attempts:{client_ip}` | 60s | Integer (attempt count) | api-gateway auth_ratelimit middleware |

**Cache key construction:**
```go
// sorted query params → canonical string → SHA-256 → hex
params := r.URL.Query()
keys := make([]string, 0, len(params))
for k := range params { keys = append(keys, k) }
sort.Strings(keys)
var b strings.Builder
for _, k := range keys { b.WriteString(k + "=" + params.Get(k) + "&") }
hash := sha256.Sum256([]byte(b.String()))
cacheKey := fmt.Sprintf("cache:zone-stats:%x", hash)
```

## Client-Side State

### Cookie: `eg_consent`

| Attribute | Value |
|-----------|-------|
| Name | `eg_consent` |
| Values | `granted` or `denied` |
| Max-Age | `31536000` (1 year) |
| SameSite | `Lax` |
| Secure | `true` (production) |
| Path | `/` |
| HttpOnly | `false` (must be readable by client JS for conditional script loading) |

## GDPR Export Schema

Response body for `GET /api/v1/me/export`:

```json
{
  "exported_at": "2026-04-17T12:00:00Z",
  "schema_version": "1",
  "profile": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "Full Name",
    "created_at": "2025-01-15T09:00:00Z",
    "subscription_tier": "pro"
  },
  "alert_rules": [
    {
      "id": "uuid",
      "name": "Paris Studio Deals",
      "filters": {},
      "created_at": "...",
      "is_active": true
    }
  ],
  "portfolio_properties": [
    {
      "id": "uuid",
      "listing_id": "uuid",
      "notes": "...",
      "added_at": "..."
    }
  ],
  "alert_history": [
    {
      "id": "uuid",
      "rule_id": "uuid",
      "listing_id": "uuid",
      "triggered_at": "...",
      "channel": "email"
    }
  ],
  "conversations": [
    {
      "session_id": "uuid",
      "messages": [
        { "role": "user", "content": "...", "timestamp": "..." },
        { "role": "assistant", "content": "...", "timestamp": "..." }
      ]
    }
  ]
}
```

## Entity Relationships Affected

```
users (1) ──< alert_rules (many)
users (1) ──< portfolio_properties (many)
users (1) ──< alert_history (many)
users (1) ──< conversations (many, Redis)

Deletion cascade (CronJob hard-delete):
  DELETE FROM alert_rules WHERE user_id IN (deleted_users)
  DELETE FROM portfolio_properties WHERE user_id IN (deleted_users)
  DELETE FROM alert_history WHERE user_id IN (deleted_users)
  DELETE FROM users WHERE deleted_at < NOW() - INTERVAL '30 days'
  DEL Redis keys: chat:session:{user_id}:*
```
