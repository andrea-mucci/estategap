# Data Model: OpenAPI, gRPC Clients & Alert Rules

**Branch**: `009-openapi-grpc-alerts` | **Date**: 2026-04-17

---

## New Database Tables

### `alert_rules`

Stores user-configured alert rule definitions. Each rule targets one or more zones and defines filter criteria for matching property listings.

| Column       | Type          | Constraints                            | Description                                        |
|--------------|---------------|----------------------------------------|----------------------------------------------------|
| `id`         | UUID          | PRIMARY KEY, DEFAULT gen_random_uuid() | Rule identifier                                    |
| `user_id`    | UUID          | NOT NULL, FK → users(id) ON DELETE CASCADE | Owning user                                    |
| `name`       | VARCHAR(255)  | NOT NULL                               | Human-readable rule name                           |
| `zone_ids`   | UUID[]        | NOT NULL                               | Array of target zone IDs (validated on write)      |
| `category`   | VARCHAR(50)   | NOT NULL                               | Property category: residential/commercial/industrial/land |
| `filter`     | JSONB         | NOT NULL, DEFAULT '{}'                 | Structured filter criteria (validated against allowed-field schema) |
| `channels`   | JSONB         | NOT NULL, DEFAULT '[]'                 | Notification channel configs, e.g. `[{"type":"email"},{"type":"push"}]` |
| `is_active`  | BOOLEAN       | NOT NULL, DEFAULT TRUE                 | Soft-delete flag; FALSE = rule disabled/deleted    |
| `created_at` | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()                | Creation timestamp                                 |
| `updated_at` | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()                | Last modification timestamp                        |

**Indexes**:
- `idx_alert_rules_user_id` on `(user_id)` — list by user
- `idx_alert_rules_user_active` on `(user_id)` WHERE `is_active = TRUE` — tier limit COUNT query

**Relationships**:
- Belongs to `users` (FK on `user_id`)
- Zone IDs reference `zones(id)` — validated at write time, no FK enforced (zones may be deleted without cascading rule removal)

---

### `alert_history`

Immutable log of alert rule firings. Written by the Alert Engine service (via NATS event); read by the API Gateway. Append-only; no updates or deletes.

| Column            | Type         | Constraints                              | Description                                       |
|-------------------|--------------|------------------------------------------|---------------------------------------------------|
| `id`              | UUID         | PRIMARY KEY, DEFAULT gen_random_uuid()   | History entry identifier                          |
| `rule_id`         | UUID         | NOT NULL, FK → alert_rules(id) ON DELETE CASCADE | Parent rule                              |
| `listing_id`      | UUID         | NOT NULL                                 | Listing that triggered the rule                   |
| `triggered_at`    | TIMESTAMPTZ  | NOT NULL, DEFAULT NOW()                  | When the rule matched                             |
| `channel`         | VARCHAR(50)  | NOT NULL                                 | Notification channel used: email/push/webhook     |
| `delivery_status` | VARCHAR(20)  | NOT NULL, DEFAULT 'pending'              | pending / delivered / failed                      |
| `error_detail`    | TEXT         |                                          | Error message if delivery_status = 'failed'       |
| `delivered_at`    | TIMESTAMPTZ  |                                          | Timestamp of successful delivery                  |

**Indexes**:
- `idx_alert_history_rule_id` on `(rule_id, triggered_at DESC)` — paginated history per rule
- `idx_alert_history_user_rule` on `(rule_id)` — user-scoped history queries (join with alert_rules on user_id)

**Relationships**:
- Belongs to `alert_rules` (FK on `rule_id`)

---

## In-Memory State

### Circuit Breaker (`internal/grpc/circuit_breaker.go`)

Not persisted. Resets on API Gateway restart. One instance per upstream gRPC target.

| Field              | Go Type    | Description                                             |
|--------------------|------------|---------------------------------------------------------|
| `state`            | `int32`    | Atomic: 0=closed, 1=open, 2=half-open                  |
| `failures`         | `int32`    | Atomic: consecutive failure count within the window     |
| `lastFailureUnix`  | `int64`    | Atomic: Unix timestamp of most recent failure           |
| `threshold`        | `int`      | Config: failures before opening (default: 5)           |
| `windowSecs`       | `int64`    | Config: failure counting window in seconds (default: 30)|
| `cooldownSecs`     | `int64`    | Config: open→half-open cooldown in seconds (default: 30)|

---

## JSONB Filter Schema

The `filter` column in `alert_rules` is validated at write time against a per-category allowlist. The schema is not stored in the database; it is enforced by the API Gateway handler.

### Filter Document Structure
```json
{
  "<field_name>": {
    "<operator>": <value>
  }
}
```

### Allowed Fields by Category

| Category      | Allowed Fields                                                                 |
|---------------|--------------------------------------------------------------------------------|
| residential   | price_eur, area_m2, bedrooms, bathrooms, floor, has_parking, has_elevator, property_type, listing_age_days |
| commercial    | price_eur, area_m2, floor, has_parking, property_type, listing_age_days        |
| industrial    | price_eur, area_m2, property_type, listing_age_days                            |
| land          | price_eur, area_m2, listing_age_days                                           |

### Supported Operators

| Operator | Meaning         | Applicable Types              |
|----------|-----------------|-------------------------------|
| `eq`     | equals          | number, boolean, string       |
| `lt`     | less than       | number                        |
| `lte`    | ≤               | number                        |
| `gt`     | greater than    | number                        |
| `gte`    | ≥               | number                        |
| `in`     | value in list   | string (property_type)        |

---

## Existing Tables (referenced, not modified)

| Table         | Columns used                                    | Purpose                                       |
|---------------|-------------------------------------------------|-----------------------------------------------|
| `users`       | `id`, `subscription_tier`                       | Authenticated user identity + tier limit lookup |
| `zones`       | `id`, `is_active`                               | Zone ID validation on alert rule write        |
| `subscriptions` | `tier`, `status`                              | Tier information (read via `subscription_tier` denorm on users) |

---

## API Response Shapes

### `AlertRule` (response)
```json
{
  "id": "uuid",
  "name": "Berlin Apartments Under 500k",
  "zone_ids": ["uuid", "uuid"],
  "category": "residential",
  "filter": {
    "price_eur": {"lte": 500000},
    "bedrooms": {"gte": 3}
  },
  "channels": [{"type": "email"}, {"type": "push"}],
  "is_active": true,
  "created_at": "2026-04-17T10:00:00Z",
  "updated_at": "2026-04-17T10:00:00Z"
}
```

### `AlertHistoryEntry` (response)
```json
{
  "id": "uuid",
  "rule_id": "uuid",
  "rule_name": "Berlin Apartments Under 500k",
  "listing_id": "uuid",
  "triggered_at": "2026-04-17T09:30:00Z",
  "channel": "email",
  "delivery_status": "delivered",
  "delivered_at": "2026-04-17T09:30:05Z",
  "error_detail": null
}
```

### `MLEstimate` (response)
```json
{
  "listing_id": "uuid",
  "estimated_value": 487500.00,
  "currency": "EUR",
  "confidence": 0.87,
  "shap_values": {
    "price_eur": 0.42,
    "area_m2": 0.31,
    "bedrooms": 0.15,
    "location": 0.12
  },
  "model_version": "v2.3.1-de"
}
```

### Paginated List Envelope
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 87,
    "total_pages": 5
  }
}
```
