# Data Model: 017 — Notification Dispatcher

**Phase**: 1 — Design  
**Date**: 2026-04-17

---

## Existing Tables (read by dispatcher)

### `users`
Relevant columns read by the dispatcher to resolve channel configuration:

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID PK` | User identifier |
| `email` | `VARCHAR(255)` | Email delivery target |
| `preferred_language` | `VARCHAR(10)` | NEW — email template locale, default `'en'` |
| `telegram_chat_id` | `BIGINT NULL` | NEW — set on `/start {token}` |
| `telegram_link_token` | `VARCHAR(64) NULL` | NEW — one-time Telegram linking token |
| `push_subscription_json` | `TEXT NULL` | NEW — FCM registration token |
| `webhook_secret` | `VARCHAR(64) NULL` | NEW — HMAC-SHA256 signing key for webhook |
| `phone_e164` | `VARCHAR(20) NULL` | NEW — E.164 phone for WhatsApp (e.g. `+34612345678`) |

### `alert_rules`
Read to resolve `webhook_url` from channels JSONB:

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID PK` | Rule identifier |
| `user_id` | `UUID FK → users.id` | Rule owner |
| `channels` | `JSONB` | Array of `{type, webhook_url?}` channel objects |
| `name` | `VARCHAR(255)` | Rule display name (included in email subject) |

### `alert_history`
Written by the dispatcher to record each delivery attempt:

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID PK` | Delivery record identifier |
| `event_id` | `UUID NOT NULL` | NEW — `NotificationEvent.EventID` for idempotency |
| `rule_id` | `UUID FK → alert_rules.id` | Matched rule |
| `listing_id` | `UUID NULL` | Matched listing (NULL for digests) |
| `channel` | `VARCHAR(20)` | Delivery channel: email/telegram/whatsapp/push/webhook |
| `delivery_status` | `VARCHAR(20)` | enum: pending / sent / delivered / failed / opened / clicked |
| `attempt_count` | `SMALLINT` | NEW — number of delivery attempts, default 1 |
| `error_detail` | `TEXT NULL` | Error message on failure |
| `triggered_at` | `TIMESTAMPTZ` | Time the notification event was received |
| `delivered_at` | `TIMESTAMPTZ NULL` | Time of successful delivery (set by dispatcher) |

**Unique constraint**: `(event_id, channel)` — prevents duplicate records if the NATS message is redelivered before acknowledgement.

---

## New Migration: `019_notification_dispatcher.py`

```python
"""Add notification dispatcher columns to users and alert_history."""

revision = "b1c2d3e4f5a6"
down_revision = "f4b5c6d7e8f9"  # 018_alert_rules_add_frequency


def upgrade():
    # users — channel configuration columns
    op.add_column("users", sa.Column("preferred_language",
        sa.String(10), nullable=False, server_default="'en'"))
    op.add_column("users", sa.Column("telegram_chat_id",
        sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("telegram_link_token",
        sa.String(64), nullable=True))
    op.add_column("users", sa.Column("push_subscription_json",
        sa.Text(), nullable=True))
    op.add_column("users", sa.Column("webhook_secret",
        sa.String(64), nullable=True))
    op.add_column("users", sa.Column("phone_e164",
        sa.String(20), nullable=True))

    # alert_history — idempotency and attempt tracking
    op.add_column("alert_history", sa.Column("event_id",
        postgresql.UUID(as_uuid=True), nullable=True))  # nullable for existing rows
    op.add_column("alert_history", sa.Column("attempt_count",
        sa.SmallInteger(), nullable=False, server_default="1"))
    op.create_unique_constraint(
        "uq_alert_history_event_channel",
        "alert_history",
        ["event_id", "channel"],
        postgresql_where="event_id IS NOT NULL"
    )
    op.create_index("idx_alert_history_event_id",
        "alert_history", ["event_id"])
```

---

## In-Memory / Redis State

### Webhook Retry Counter

```
Key:    webhook:retry:{notification_id}
Type:   String (integer via INCR)
TTL:    300 seconds
Value:  attempt count (1, 2, 3)
```

Used to gate retry attempts for webhook delivery. If the service restarts, the counter survives for 5 minutes — enough to cover the 1s + 4s + 16s retry window.

---

## NATS Contract

### Consumed Subject

```
alerts.notifications.{COUNTRY_CODE}    (wildcard: alerts.notifications.>)
```

### Message Payload: `NotificationEvent`

Defined in `services/alert-engine/internal/model/types.go` — re-imported or duplicated in `services/alert-dispatcher/internal/model/types.go`:

```go
type NotificationEvent struct {
    EventID        string          `json:"event_id"`
    UserID         string          `json:"user_id"`
    RuleID         string          `json:"rule_id"`
    RuleName       string          `json:"rule_name"`
    ListingID      *string         `json:"listing_id,omitempty"`
    CountryCode    string          `json:"country_code"`
    Channel        string          `json:"channel"`
    WebhookURL     *string         `json:"webhook_url,omitempty"`
    Frequency      string          `json:"frequency"`
    IsDigest       bool            `json:"is_digest"`
    DealScore      *float64        `json:"deal_score,omitempty"`
    DealTier       *int            `json:"deal_tier,omitempty"`
    ListingSummary *ListingSummary `json:"listing_summary,omitempty"`
    TotalMatches   *int            `json:"total_matches,omitempty"`
    Listings       []DigestListing `json:"listings,omitempty"`
    TriggeredAt    time.Time       `json:"triggered_at"`
}
```

**Channel values**: `"email"` | `"telegram"` | `"whatsapp"` | `"push"` | `"webhook"`

---

## Sender Interface

```go
// internal/sender/sender.go

type DeliveryResult struct {
    Success      bool
    AttemptCount int
    ErrorDetail  string
    DeliveredAt  *time.Time
}

type Sender interface {
    Send(ctx context.Context, event model.NotificationEvent, user *model.UserChannelProfile) (DeliveryResult, error)
}
```

### `UserChannelProfile`

Resolved from DB before dispatch:

```go
type UserChannelProfile struct {
    UserID              string
    Email               string
    PreferredLanguage   string
    TelegramChatID      *int64
    PushToken           *string   // FCM registration token
    PhoneE164           *string   // WhatsApp destination
    WebhookSecret       *string
}
```

---

## Email Template Data

```go
type EmailTemplateData struct {
    // Listing
    PhotoURL        string
    Address         string    // "{City}, {CountryCode}"
    PriceFormatted  string    // e.g. "€ 245,000"
    DealScore       float64
    DealTier        int
    DealBadgeColor  string    // derived: tier 1="#22c55e", 2="#84cc16", 3="#f59e0b", 4="#ef4444"
    Features        []string

    // Links
    AnalysisURL     string    // https://estategap.com/listings/{id}
    PortalURL       string    // original listing URL (if available in summary)
    TrackOpenURL    string    // /api/v1/alerts/track?id={history_id}&action=open
    TrackClickAnalysis string // /api/v1/alerts/track?id={history_id}&action=click&url={encoded_analysis}
    TrackClickPortal   string // /api/v1/alerts/track?id={history_id}&action=click&url={encoded_portal}

    // Digest
    IsDigest        bool
    Listings        []DigestEmailListing  // populated for digest emails
    TotalMatches    int
    RuleName        string
}
```
