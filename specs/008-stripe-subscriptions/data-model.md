# Data Model: Stripe Subscription Management

**Branch**: `008-stripe-subscriptions` | **Date**: 2026-04-17

---

## New: `subscriptions` Table (Migration 012)

Stores the full Stripe subscription state. Kept in sync with `users.subscription_tier` via atomic DB transactions on every webhook event.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE |
| `stripe_customer_id` | `TEXT` | NO | — | Stripe `cus_*` identifier |
| `stripe_sub_id` | `TEXT` | NO | — | Stripe `sub_*` identifier; UNIQUE |
| `tier` | `TEXT` | NO | — | `basic` / `pro` / `global` / `api` |
| `status` | `TEXT` | NO | `'trialing'` | `trialing` / `active` / `past_due` / `cancelled` |
| `billing_period` | `TEXT` | NO | — | `monthly` / `annual` |
| `current_period_start` | `TIMESTAMPTZ` | NO | — | Stripe `current_period_start` |
| `current_period_end` | `TIMESTAMPTZ` | NO | — | Stripe `current_period_end`; used as next invoice date |
| `trial_end_at` | `TIMESTAMPTZ` | YES | NULL | Stripe `trial_end`; NULL for `api` tier |
| `payment_failed_at` | `TIMESTAMPTZ` | YES | NULL | Timestamp of first payment failure; NULL when resolved |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Updated on every webhook-driven change |

**Indexes**:
- `PRIMARY KEY (id)`
- `UNIQUE (stripe_sub_id)` — direct webhook lookup by Stripe subscription ID
- `UNIQUE (user_id) WHERE status != 'cancelled'` — partial index; one active subscription per user
- `INDEX (user_id)` — for `GET /subscriptions/me` lookup

**Constraints**:
- `CHECK (status IN ('trialing', 'active', 'past_due', 'cancelled'))`
- `CHECK (billing_period IN ('monthly', 'annual'))`
- `CHECK (tier IN ('basic', 'pro', 'global', 'api'))`

---

## Modified: `users` Table

No new columns needed. The following existing columns are updated by webhook handlers:

| Column | Updated On | Value |
|--------|-----------|-------|
| `subscription_tier` | Every status transition | New tier or `'free'` on cancel |
| `stripe_customer_id` | `checkout.session.completed` | Stripe `cus_*` ID |
| `stripe_sub_id` | `checkout.session.completed` | Stripe `sub_*` ID |
| `subscription_ends_at` | Every update/cancel | `current_period_end` or NULL on cancel |
| `alert_limit` | Every tier change | Per-tier limit (3/10/25/50/100) |
| `updated_at` | Every webhook update | `NOW()` |

**Denormalization rationale**: `subscription_tier` on `users` is read on every authenticated API request (rate limit middleware reads it from the JWT context, which is populated at auth time from the DB). Keeping it denormalized on `users` avoids a JOIN on every request.

---

## Updated: `Subscription` Go Struct (`libs/pkg/models/user.go`)

The existing `Subscription` struct is extended with billing state fields:

```go
type Subscription struct {
    ID                 pgtype.UUID         `json:"id" db:"id"`
    UserID             pgtype.UUID         `json:"user_id" db:"user_id"`
    StripeCustomerID   string              `json:"stripe_customer_id" db:"stripe_customer_id"`
    StripeSubID        string              `json:"stripe_sub_id" db:"stripe_sub_id"`
    Tier               SubscriptionTier    `json:"tier" db:"tier"`
    Status             string              `json:"status" db:"status"`
    BillingPeriod      string              `json:"billing_period" db:"billing_period"`
    CurrentPeriodStart pgtype.Timestamptz  `json:"current_period_start" db:"current_period_start"`
    CurrentPeriodEnd   pgtype.Timestamptz  `json:"current_period_end" db:"current_period_end"`
    TrialEndAt         *pgtype.Timestamptz `json:"trial_end_at" db:"trial_end_at"`
    PaymentFailedAt    *pgtype.Timestamptz `json:"payment_failed_at" db:"payment_failed_at"`
    CreatedAt          pgtype.Timestamptz  `json:"created_at" db:"created_at"`
    UpdatedAt          pgtype.Timestamptz  `json:"updated_at" db:"updated_at"`
}
```

> **Note**: The current struct (`StartsAt`, `EndsAt`, `AlertLimit`) is replaced entirely. `AlertLimit` is retained on the `User` struct.

---

## Redis Keys

| Key Pattern | Type | TTL | Purpose |
|-------------|------|-----|---------|
| `stripe:event:{event_id}` | String | 7 days | Idempotency — presence means event already processed |
| `stripe:pending_downgrades` | Sorted Set | None (entries expire by score) | Grace-period downgrade queue; score = Unix timestamp when downgrade fires |

**Sorted set entry format**: member = `{user_id}` (UUID string), score = Unix timestamp (int64).

---

## State Transitions

```
                    checkout.session.completed
[free] ─────────────────────────────────────────► [trialing]
                                                       │
                                            trial ends (auto-charge)
                                               │               │
                                          success          failure
                                               │               │
                                           [active]      [past_due] ──── 3 days ──► [free]
                                               │               │
                              subscription.updated     invoice.payment_succeeded
                                       │               │
                              [tier change]        [active] (downgrade cancelled)
                                               │
                              subscription.deleted
                                               │
                                          [cancelled] → tier = free
```

---

## Config Fields Added (`internal/config/config.go`)

```go
// Stripe
StripeSecretKey        string  // STRIPE_SECRET_KEY (required)
StripeWebhookSecret    string  // STRIPE_WEBHOOK_SECRET (required)
StripeSuccessURL       string  // STRIPE_SUCCESS_URL (required)
StripeCancelURL        string  // STRIPE_CANCEL_URL (required)
StripePortalReturnURL  string  // STRIPE_PORTAL_RETURN_URL (required)

// Price IDs (required; missing = checkout returns 400 for that tier/period)
StripePriceBasicMonthly  string  // STRIPE_PRICE_BASIC_MONTHLY
StripePriceBasicAnnual   string  // STRIPE_PRICE_BASIC_ANNUAL
StripePriceProMonthly    string  // STRIPE_PRICE_PRO_MONTHLY
StripePriceProAnnual     string  // STRIPE_PRICE_PRO_ANNUAL
StripePriceGlobalMonthly string  // STRIPE_PRICE_GLOBAL_MONTHLY
StripePriceGlobalAnnual  string  // STRIPE_PRICE_GLOBAL_ANNUAL
StripePriceAPIMonthly    string  // STRIPE_PRICE_API_MONTHLY
StripePriceAPIAnnual     string  // STRIPE_PRICE_API_ANNUAL
```
