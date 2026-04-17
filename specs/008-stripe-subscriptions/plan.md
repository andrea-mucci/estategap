# Implementation Plan: Stripe Subscription Management

**Branch**: `008-stripe-subscriptions` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/008-stripe-subscriptions/spec.md`

## Summary

Implement Stripe subscription management within the existing `api-gateway` Go service. The feature adds four endpoints (checkout, webhook, subscription status, customer portal), a new `subscriptions` PostgreSQL table (migration 012), a Stripe service layer (`internal/service/stripe.go`), a subscription repository (`internal/repository/subscriptions.go`), and a Redis-backed background goroutine for grace-period downgrades (`internal/worker/stripe_downgrade.go`). All Stripe API calls use `github.com/stripe/stripe-go/v81`. Webhook signature verification uses `stripe.VerifySignature`. Idempotency is enforced via per-event Redis keys (`stripe:event:{id}`, TTL 7 days). Delayed downgrades use a Redis sorted set polled every 60 seconds. Tier changes propagate to rate limiting within one 60-second window via the DB-backed `subscription_tier` field on `users`.

---

## Technical Context

**Language/Version**: Go 1.23  
**Primary Dependencies**: chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, stripe-go/v81 (new), viper v1.19.0, slog (stdlib)  
**Storage**: PostgreSQL 16 (new `subscriptions` table; `users` table updated); Redis 7 (idempotency keys, downgrade sorted set)  
**Testing**: Go table-driven unit tests; testcontainers integration tests; `stripe mock` for Stripe API stubs  
**Target Platform**: Linux (Kubernetes pod — existing `api-gateway` Deployment)  
**Project Type**: web-service (REST API Gateway extension — no new service)  
**Performance Goals**: Webhook processing < 500ms p95; checkout session creation < 1s p95  
**Constraints**: Webhook handler must respond within Stripe's 30-second delivery timeout; all DB writes on primary pool; reads on replica pool; no ORM  
**Scale/Scope**: Extends single existing service; ~7 new/modified files; one new DB migration

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Extends existing Go `api-gateway` only; shared model changes in `libs/pkg/models/`; no new service |
| II. Event-Driven Communication | ✅ PASS | Stripe webhooks are external HTTP (inbound from Stripe, not inter-service); internal services still use NATS/gRPC |
| III. Country-First Data Sovereignty | ✅ PASS | Subscriptions are user-scoped; no country partitioning needed |
| IV. ML-Powered Intelligence | N/A | Not applicable |
| V. Code Quality Discipline | ✅ PASS | pgx (no ORM); slog structured logging; explicit error handling; golangci-lint; table-driven tests |
| VI. Security & Ethical Scraping | ✅ PASS | Webhook signature verification on every request; `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` via Kubernetes Sealed Secrets |
| VII. Kubernetes-Native Deployment | ✅ PASS | Config injected from ConfigMap/Secrets; no manual changes; existing Dockerfile unchanged |

**Gate Result**: ✅ PASS — all principles satisfied.

---

## Project Structure

### Documentation (this feature)

```text
specs/008-stripe-subscriptions/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1 — DB schema, Go structs, Redis keys
├── quickstart.md        # Phase 1 — local dev guide
├── contracts/
│   └── api.md           # Phase 1 — endpoint contracts
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code

```text
services/api-gateway/
├── cmd/
│   ├── main.go                              # Wire StripeService, SubscriptionsRepo, DowngradeWorker
│   └── routes.go                            # Add GET /subscriptions/me, POST /subscriptions/portal
├── internal/
│   ├── config/
│   │   └── config.go                        # Add 13 Stripe config fields (key, secret, URLs, price IDs)
│   ├── handler/
│   │   └── subscriptions.go                 # Replace 2-method stub with 4-method implementation
│   ├── service/
│   │   └── stripe.go                        # New: Stripe API operations (checkout, portal, webhook verify)
│   ├── repository/
│   │   ├── subscriptions.go                 # New: subscriptions table CRUD
│   │   └── users.go                         # Add UpdateSubscriptionTier, DowngradeToFree methods
│   └── worker/
│       └── stripe_downgrade.go              # New: background goroutine; polls Redis sorted set every 60s

services/pipeline/
└── alembic/versions/
    └── 012_subscriptions.py                 # New: subscriptions table + indexes

libs/pkg/models/
└── user.go                                  # Extend Subscription struct (add status, billing_period, periods)
```

---

## Phase 0: Research

**Status**: Complete. See [research.md](./research.md).

Key decisions:
- **Stripe SDK**: `github.com/stripe/stripe-go/v81`
- **Idempotency**: `SET NX EX 604800` on `stripe:event:{event_id}` key
- **Delayed downgrade**: Redis sorted set `stripe:pending_downgrades`, polled every 60s by background goroutine
- **Schema**: New `subscriptions` table (migration 012); `users` table denormalizes `subscription_tier` for rate-limit reads
- **Trials**: `trial_period_days=14` on Checkout Session for `basic`/`pro`/`global`; none for `api`
- **Price IDs**: ConfigMap env vars `STRIPE_PRICE_{TIER}_{PERIOD}`

---

## Phase 1: Design & Contracts

**Status**: Complete.

### 1.1 Data Model

See [data-model.md](./data-model.md).

**New `subscriptions` table** (migration 012):
- Columns: `id`, `user_id`, `stripe_customer_id`, `stripe_sub_id`, `tier`, `status`, `billing_period`, `current_period_start`, `current_period_end`, `trial_end_at`, `payment_failed_at`, `created_at`, `updated_at`
- Partial unique index: `UNIQUE (user_id) WHERE status != 'cancelled'`
- Unique index on `stripe_sub_id` for fast webhook lookup

**`users` table**: no schema changes; existing `subscription_tier`, `stripe_customer_id`, `stripe_sub_id`, `subscription_ends_at` updated atomically with `subscriptions` table via transaction.

**`Subscription` Go struct** in `libs/pkg/models/user.go`: replace existing minimal struct with full version including `Status`, `BillingPeriod`, `CurrentPeriodStart`, `CurrentPeriodEnd`, `TrialEndAt`, `PaymentFailedAt`.

### 1.2 API Contracts

See [contracts/api.md](./contracts/api.md).

| Method | Path | Auth | Handler |
|--------|------|------|---------|
| `POST` | `/v1/subscriptions/checkout` | JWT | `SubscriptionsHandler.Checkout` |
| `POST` | `/v1/webhooks/stripe` | None | `SubscriptionsHandler.StripeWebhook` |
| `GET` | `/v1/subscriptions/me` | JWT | `SubscriptionsHandler.Me` |
| `POST` | `/v1/subscriptions/portal` | JWT | `SubscriptionsHandler.Portal` |

### 1.3 Implementation Details

#### `internal/config/config.go`

Add fields and required-variable validation:
```
STRIPE_SECRET_KEY           (required, marked as secret)
STRIPE_WEBHOOK_SECRET       (required, marked as secret)
STRIPE_SUCCESS_URL          (required)
STRIPE_CANCEL_URL           (required)
STRIPE_PORTAL_RETURN_URL    (required)
STRIPE_PRICE_BASIC_MONTHLY  (required)
STRIPE_PRICE_BASIC_ANNUAL   (required)
STRIPE_PRICE_PRO_MONTHLY    (required)
STRIPE_PRICE_PRO_ANNUAL     (required)
STRIPE_PRICE_GLOBAL_MONTHLY (required)
STRIPE_PRICE_GLOBAL_ANNUAL  (required)
STRIPE_PRICE_API_MONTHLY    (required)
STRIPE_PRICE_API_ANNUAL     (required)
```

#### `internal/service/stripe.go`

```go
type StripeService struct { cfg *config.Config }

func (s *StripeService) CreateCheckoutSession(userID, email, tier, period string) (*stripe.CheckoutSession, error)
// - Looks up price ID from cfg
// - Sets trial_period_days=14 for basic/pro/global
// - Sets client_reference_id=userID, customer_email=email
// - Sets success_url, cancel_url from cfg

func (s *StripeService) CreatePortalSession(stripeCustomerID, returnURL string) (*stripe.BillingPortalSession, error)

func (s *StripeService) ParseWebhookEvent(payload []byte, sigHeader string) (stripe.Event, error)
// - Calls stripe.ConstructEvent(payload, sigHeader, webhookSecret)
```

#### `internal/repository/subscriptions.go`

```go
type SubscriptionsRepo struct { primary, replica *pgxpool.Pool }

func (r *SubscriptionsRepo) Create(ctx, sub *models.Subscription) error
func (r *SubscriptionsRepo) GetByUserID(ctx, userID uuid.UUID) (*models.Subscription, error)
func (r *SubscriptionsRepo) GetByStripeSubID(ctx, stripeSubID string) (*models.Subscription, error)
func (r *SubscriptionsRepo) UpdateStatus(ctx, stripeSubID, status, tier string, periodStart, periodEnd time.Time) error
func (r *SubscriptionsRepo) SetPaymentFailed(ctx, stripeSubID string, failedAt time.Time) error
func (r *SubscriptionsRepo) ClearPaymentFailed(ctx, stripeSubID string) error
func (r *SubscriptionsRepo) Cancel(ctx, stripeSubID string) error
```

#### `internal/repository/users.go` additions

```go
func (r *UsersRepo) UpdateSubscriptionTier(ctx, userID uuid.UUID, tier SubscriptionTier, stripeCustomerID, stripeSubID string, endsAt *time.Time) error
func (r *UsersRepo) DowngradeToFree(ctx, userID uuid.UUID) error
```

#### `internal/handler/subscriptions.go`

Constructor changes:
```go
type SubscriptionsHandler struct {
    stripe        *service.StripeService
    subsRepo      *repository.SubscriptionsRepo
    usersRepo     *repository.UsersRepo
    redisClient   *redis.Client
}
```

**Webhook handler flow**:
1. Read raw body (preserve for signature verification)
2. `stripe.ConstructEvent(body, r.Header.Get("Stripe-Signature"), secret)` → 400 on error
3. `SetNX stripe:event:{event.ID}` → if already set, return 200 immediately
4. `switch event.Type { case "checkout.session.completed": ... }`
5. Execute DB transaction: update `subscriptions` + `users` atomically
6. Return 200

**Checkout handler flow**:
1. Decode `{tier, billing_period}` from JSON body
2. Validate tier + billing_period values
3. Check if user already has active subscription → 400 if so
4. Call `stripeService.CreateCheckoutSession(userID, email, tier, period)`
5. Return `{checkout_url: session.URL}`

**Me handler flow**:
1. Extract `userID` from context
2. `subsRepo.GetByUserID` — if not found, return free-tier response
3. Map subscription fields to response struct
4. Return 200

**Portal handler flow**:
1. Extract `userID` from context
2. `usersRepo.GetUserByID` to get `stripe_customer_id`
3. If nil → 400 `no_subscription`
4. `stripeService.CreatePortalSession(stripeCustomerID, returnURL)`
5. Return `{portal_url: session.URL}`

#### `internal/worker/stripe_downgrade.go`

```go
func StartDowngradeWorker(ctx context.Context, redisClient *redis.Client, usersRepo *repository.UsersRepo)
// Goroutine: tick every 60s
// ZRANGEBYSCORE stripe:pending_downgrades 0 <now>
// For each user_id: usersRepo.DowngradeToFree(ctx, userID)
// ZREM stripe:pending_downgrades <user_id>
// Logs each downgrade with slog
```

Started in `cmd/main.go` after all repos/services are wired.

#### `cmd/main.go` wiring

```go
stripeService := service.NewStripeService(cfg)
subsRepo := repository.NewSubscriptionsRepo(primaryPool, replicaPool)
subscriptionsHandler := handler.NewSubscriptionsHandler(stripeService, subsRepo, usersRepo, redisClient)
go worker.StartDowngradeWorker(ctx, redisClient, usersRepo)
```

#### `cmd/routes.go` additions

```go
r.Get("/subscriptions/me", subscriptionsHandler.Me)
r.Post("/subscriptions/portal", subscriptionsHandler.Portal)
```

(Inside `mountAuthenticatedV1Routes` — POST `/subscriptions/checkout` already registered there)

### 1.4 Alert Limit Per Tier

| Tier | Alert Limit |
|------|------------|
| `free` | 3 |
| `basic` | 10 |
| `pro` | 25 |
| `global` | 50 |
| `api` | 100 |

Defined as a constant map in `internal/service/stripe.go` (or `libs/pkg/models/enums.go`); used when updating `users.alert_limit` on tier change.

---

## Complexity Tracking

> No Constitution violations to justify.

---

## Open Questions for Task Generation

None. All design decisions resolved in research.md.
