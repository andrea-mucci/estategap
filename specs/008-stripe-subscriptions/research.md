# Research: Stripe Subscription Management

**Branch**: `008-stripe-subscriptions` | **Date**: 2026-04-17  
**Phase**: 0 — Research & Unknowns Resolution

---

## Decision 1: Stripe Go SDK Version

**Decision**: `github.com/stripe/stripe-go/v81`

**Rationale**: v81 is the current major series of the official Stripe Go library. It supports all required Stripe resources (Checkout Session, Billing Portal Session, Subscription, Invoice, Event). The `stripe.VerifySignature` function for webhook verification is included. Module path uses the `/v81` suffix per Go module versioning conventions.

**Alternatives considered**:
- v76–v80: Older majors; no functional gap but not current.
- Third-party wrappers: No ecosystem advantage; official SDK is authoritative.

---

## Decision 2: Webhook Idempotency Mechanism

**Decision**: Per-event Redis key `stripe:event:{event_id}` with `SET NX EX 604800` (7 days). If the key already exists, return `200 OK` immediately without processing.

**Rationale**: Stripe guarantees each event has a stable unique ID (e.g., `evt_1PXxxx`). Using `SET NX` (set-if-not-exists) is atomic and avoids race conditions under concurrent delivery. A 7-day TTL matches Stripe's retry window (they retry for ~72 hours) with headroom. Using individual keys instead of a Redis SET gives per-key TTL control and avoids unbounded set growth.

**Alternatives considered**:
- PostgreSQL `processed_events` table: Durable but adds a DB write to every webhook before any business logic. Redis is sufficient given Stripe's own delivery guarantees.
- Redis SET with single TTL: `SADD stripe:processed_events {event_id}` + `EXPIRE` on the whole set. The global `EXPIRE` resets on every call, causing premature expiry under high load. Individual keys are safer.
- In-memory deduplication: Not durable across pod restarts.

---

## Decision 3: Grace-Period Downgrade Mechanism

**Decision**: Redis sorted set `stripe:pending_downgrades`, scored by Unix timestamp of when the downgrade should execute. A background goroutine polls every 60 seconds using `ZRANGEBYSCORE 0 <now>`, executes downgrades, and removes processed entries with `ZREM`.

**Rationale**: Sorted sets allow `ZRANGEBYSCORE` to efficiently retrieve all due entries in O(log N + M). The background goroutine runs inside the same `api-gateway` process — no new service is needed. On payment recovery (`invoice.payment_succeeded`), the entry is removed with `ZREM` before it fires.

**Alternatives considered**:
- Redis keyspace notifications (TTL expiry): Requires `notify-keyspace-events = Ex` on the Redis server, which is not guaranteed in managed Redis. Not reliable for production scheduling.
- Separate scheduler service: Over-engineered for a single use case; adding a service violates constitution principle I (no unnecessary services).
- PostgreSQL `pg_cron`: Available but adds infra complexity; Redis sorted set is simpler given Redis is already a hard dependency.
- NATS JetStream delayed publish: Valid architecture pattern per constitution II, but adds NATS coupling to billing logic and requires JetStream-aware consumer. Overkill for this single use case.

**Grace period cancellation**: On `invoice.payment_succeeded` (or `customer.subscription.updated` where status goes back to active), call `ZREM stripe:pending_downgrades {user_id}`.

---

## Decision 4: Subscriptions Table vs. Augmenting Users Table

**Decision**: Create a new `subscriptions` table (migration 012). Keep `users.subscription_tier` as a denormalized cache for rate-limit lookups. Both are kept in sync on every webhook event.

**Rationale**: The `users` table already holds `subscription_tier`, `stripe_customer_id`, `stripe_sub_id`, `subscription_ends_at`. These are needed by the rate-limit middleware on every authenticated request. Adding more columns (`status`, `billing_period`, `trial_end_at`, `payment_failed_at`, `current_period_start`) to `users` would widen the hot row scanned on every auth. A separate `subscriptions` table isolates billing state from auth state. The existing `Subscription` struct in `libs/pkg/models/user.go` maps to this table.

**users table role**: Holds the denormalized `subscription_tier` (and Stripe IDs for portal lookup). Updated atomically with the `subscriptions` table in a transaction.

**Alternatives considered**:
- Single `users` table with added columns: Simpler but widens a high-contention row. Also makes `subscription_tier` harder to audit over time.
- Event-sourced subscription log: Over-engineered; read models would add complexity without benefit at this scale.

---

## Decision 5: Trial Configuration

**Decision**: `trial_period_days=14` passed as a parameter to the Stripe Checkout Session creation. Applies to `basic`, `pro`, `global` tiers only. `api` tier has no trial.

**Rationale**: Stripe natively supports `trial_period_days` on Checkout Sessions. During trial, Stripe does not charge the customer but the subscription is created in `trialing` state. When the trial ends, Stripe auto-attempts payment. If it fails, `invoice.payment_failed` fires and the standard grace-period flow applies.

**Alternatives considered**:
- Free tier → paid tier manual upgrade flow: The spec calls for trial at checkout, so trial is Stripe-native, not application-managed.
- `subscription_data.trial_settings`: Not needed; `trial_period_days` is sufficient.

---

## Decision 6: Price ID Configuration

**Decision**: Price IDs stored as environment variables in Kubernetes ConfigMap (not Secrets, as they are not sensitive). Variable names: `STRIPE_PRICE_{TIER}_{PERIOD}` (e.g., `STRIPE_PRICE_BASIC_MONTHLY`, `STRIPE_PRICE_PRO_ANNUAL`). Config struct gains 8 new optional string fields; missing price IDs result in a checkout error for that tier/period combination.

**Rationale**: Stripe Price IDs are not sensitive data (they are public-facing identifiers in checkout URLs). ConfigMap injection is standard Kubernetes practice. Storing them in code would require a deploy on every price change.

**Alternatives considered**:
- Fetch prices dynamically from Stripe API: Adds latency to every checkout call; unnecessary given stable price configuration.
- Single `STRIPE_PRICE_MAP` JSON blob: Harder to override individual prices in staging vs production.

---

## Decision 7: Subscription Status Mapping (Stripe → Database)

| Stripe Subscription Status | Internal Status | Action |
|---------------------------|-----------------|--------|
| `trialing` | `trialing` | Set tier, set `trial_end_at` |
| `active` | `active` | Set tier, clear payment failure |
| `past_due` | `past_due` | Set `payment_failed_at`, queue downgrade |
| `canceled` | `cancelled` | Set tier to `free` |
| `unpaid` | `past_due` | Same as past_due |
| `incomplete` | (ignored) | Checkout incomplete; no state change |
| `incomplete_expired` | (ignored) | Checkout expired; no state change |

**Rationale**: `incomplete` / `incomplete_expired` indicate a checkout that was never completed — no subscription state should be written. `unpaid` is treated identically to `past_due` to trigger the grace period flow.

---

## Decision 8: Alert Limit Per Tier

| Tier | Alert Limit |
|------|-------------|
| free | 3 |
| basic | 10 |
| pro | 25 |
| global | 50 |
| api | 100 |

**Rationale**: Alert limits scale with tier price/capability. The `users.alert_limit` column is updated alongside `subscription_tier` on every tier change. Values chosen to provide meaningful step-ups per tier.

---

## Decision 9: Checkout Success/Cancel Redirect URLs

**Decision**: `STRIPE_SUCCESS_URL` and `STRIPE_CANCEL_URL` are environment variables injected from ConfigMap. These are the frontend URLs Stripe redirects to after checkout completion or cancellation. Format: `https://app.estategap.com/dashboard?checkout=success` / `https://app.estategap.com/pricing?checkout=cancelled`.

**Rationale**: URLs must be configurable per environment (staging vs production). Not sensitive, so ConfigMap is appropriate.

---

## Decision 10: Webhook Route Path

**Decision**: Webhook at `POST /v1/webhooks/stripe`. This is already registered in `main.go` outside the JWT auth middleware group. The route bypasses `Authenticator` and `RequireAuth` but passes through `CORS`, `RequestLogger`, and `MetricsMiddleware`.

**Rationale**: Already scaffolded correctly in existing code. No changes to route registration needed — only the handler implementation.
