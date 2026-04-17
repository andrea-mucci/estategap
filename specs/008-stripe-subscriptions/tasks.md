# Tasks: Stripe Subscription Management

**Input**: Design documents from `/specs/008-stripe-subscriptions/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no conflicting dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup

**Purpose**: Add the Stripe dependency and update environment configuration before any implementation begins.

- [X] T001 Add `github.com/stripe/stripe-go/v81` to `services/api-gateway/go.mod` via `go get` and run `go work sync` at repo root
- [X] T002 [P] Update `services/api-gateway/.env.example` with all 13 new Stripe environment variables: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`, `STRIPE_PORTAL_RETURN_URL`, and 8 `STRIPE_PRICE_{TIER}_{PERIOD}` entries

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented — database schema, shared Go models, config, repositories, and the Stripe service layer.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Phase 2a — Parallel foundations (no inter-dependencies)

- [X] T003 [P] Create Alembic migration `services/pipeline/alembic/versions/012_subscriptions.py`: define `subscriptions` table with columns `id`, `user_id` (FK→users), `stripe_customer_id`, `stripe_sub_id` (UNIQUE), `tier`, `status` (CHECK), `billing_period` (CHECK), `current_period_start`, `current_period_end`, `trial_end_at`, `payment_failed_at`, `created_at`, `updated_at`; add partial unique index `UNIQUE (user_id) WHERE status != 'cancelled'`; add index on `user_id`; include `downgrade()` that drops the table
- [X] T004 [P] Replace the existing minimal `Subscription` struct in `libs/pkg/models/user.go` with the full version: add fields `ID`, `Status`, `BillingPeriod`, `CurrentPeriodStart`, `CurrentPeriodEnd`, `TrialEndAt`, `PaymentFailedAt`; remove the old `StartsAt`/`EndsAt`/`AlertLimit` fields; keep `User` struct unchanged
- [X] T005 [P] Extend `services/api-gateway/internal/config/config.go`: add 13 new `Config` struct fields for Stripe (`StripeSecretKey`, `StripeWebhookSecret`, `StripeSuccessURL`, `StripeCancelURL`, `StripePortalReturnURL`, and 8 price ID fields); wire all 13 from `viper.GetString`; add all 5 non-price fields to the missing-vars validation list

### Phase 2b — Depends on T003+T004+T005 (parallel with each other)

- [X] T006 [P] Create `services/api-gateway/internal/repository/subscriptions.go`: implement `SubscriptionsRepo` struct with `primary`/`replica` pools; implement all 7 methods — `Create`, `GetByUserID`, `GetByStripeSubID`, `UpdateStatus`, `SetPaymentFailed`, `ClearPaymentFailed`, `Cancel`; use `pgx.RowToAddrOfStructByNameLax[models.Subscription]` for scanning; all writes on `primary`, reads on `replica`
- [X] T007 [P] Add two methods to `services/api-gateway/internal/repository/users.go`: `UpdateSubscriptionTier(ctx, userID, tier, stripeCustomerID, stripeSubID string, alertLimit int16, endsAt *time.Time) error` (updates `subscription_tier`, `stripe_customer_id`, `stripe_sub_id`, `alert_limit`, `subscription_ends_at`, `updated_at` on primary); `DowngradeToFree(ctx, userID uuid.UUID) error` (sets `subscription_tier='free'`, `alert_limit=3`, `subscription_ends_at=NULL`, `updated_at=NOW()` on primary)
- [X] T008 [P] Create `services/api-gateway/internal/service/stripe.go`: implement `StripeService` struct holding `*config.Config`; implement `NewStripeService(cfg)` that calls `stripe.Key = cfg.StripeSecretKey`; implement `ParseWebhookEvent(payload []byte, sigHeader string) (stripe.Event, error)` using `webhook.ConstructEvent`; implement `CreateCheckoutSession(userID, email, tier, period string) (*stripe.CheckoutSession, error)` — resolves price ID from cfg map, sets `trial_period_days=14` for basic/pro/global (not api), sets `client_reference_id`, `customer_email`, `success_url`, `cancel_url`; implement `CreatePortalSession(stripeCustomerID, returnURL string) (*stripe.BillingPortalSession, error)`; define `TierAlertLimit` map (`free`→3, `basic`→10, `pro`→25, `global`→50, `api`→100)

**Checkpoint**: All foundational components are in place. Run `go build ./...` from `services/api-gateway` — must compile before proceeding.

---

## Phase 3: User Story 1 — Subscribe to a Paid Tier (Priority: P1) 🎯 MVP

**Goal**: A free user can initiate checkout, complete a Stripe-hosted payment with optional 14-day trial, and have their subscription tier activated via webhook within 5 seconds.

**Independent Test**: Register a free user → POST `/v1/subscriptions/checkout` with `{"tier":"pro","billing_period":"monthly"}` → open `checkout_url` → pay with test card `4242 4242 4242 4242` → verify `users.subscription_tier = 'pro'` in DB and a `subscriptions` row exists.

- [X] T009 [US1] Replace the stub `SubscriptionsHandler` in `services/api-gateway/internal/handler/subscriptions.go`: redefine the struct to hold `stripe *service.StripeService`, `subsRepo *repository.SubscriptionsRepo`, `usersRepo *repository.UsersRepo`, `redisClient *redis.Client`; update `NewSubscriptionsHandler` constructor signature accordingly; keep the 2 existing stub methods as empty skeletons to be filled in T010 and T011
- [X] T010 [US1] Implement `Checkout` method in `services/api-gateway/internal/handler/subscriptions.go`: decode `{tier, billing_period}` JSON body; validate tier ∈ {basic,pro,global,api} and period ∈ {monthly,annual}; check `subsRepo.GetByUserID` — if active/trialing subscription exists return 400 `already_subscribed`; extract `userID` and `email` from request context; call `stripeService.CreateCheckoutSession`; return 200 `{"checkout_url": session.URL}`
- [X] T011 [US1] Implement `StripeWebhook` method in `services/api-gateway/internal/handler/subscriptions.go`: read raw body with `io.ReadAll` (must happen before any JSON decode); call `stripeService.ParseWebhookEvent(body, r.Header.Get("Stripe-Signature"))` — return 400 on error; attempt `redisClient.SetNX("stripe:event:"+event.ID, "1", 7*24*time.Hour)` — if key already existed return 200 immediately; implement `switch event.Type` with `case "checkout.session.completed"`: unmarshal session, run DB transaction to call `subsRepo.Create` + `usersRepo.UpdateSubscriptionTier` atomically; default case: return 200; add `slog.Info` for each processed event type
- [X] T012 [US1] Wire all new dependencies in `services/api-gateway/cmd/main.go`: instantiate `stripeService := service.NewStripeService(cfg)`; instantiate `subsRepo := repository.NewSubscriptionsRepo(primaryPool, replicaPool)`; update `handler.NewSubscriptionsHandler(stripeService, subsRepo, usersRepo, redisClient)` call; keep the downgrade worker start as a TODO comment (implemented in US4/T022)

**Checkpoint**: POST `/v1/subscriptions/checkout` returns a working Stripe URL. Completing test-mode checkout triggers the webhook and updates DB tier. Verify with: `curl -X POST /v1/subscriptions/checkout -H "Authorization: Bearer $TOKEN" -d '{"tier":"pro","billing_period":"monthly"}'`

---

## Phase 4: User Story 2 — Manage Subscription via Customer Portal (Priority: P2)

**Goal**: An active subscriber can access the Stripe Customer Portal to upgrade, downgrade, cancel, or update payment method. All portal actions are reflected in the database via webhooks.

**Independent Test**: Create an active subscriber (via US1 flow) → POST `/v1/subscriptions/portal` → open `portal_url` → change plan in portal → verify `customer.subscription.updated` webhook updates `users.subscription_tier`; cancel plan → verify `customer.subscription.deleted` sets tier to `free`.

- [X] T013 [US2] Implement `Portal` method in `services/api-gateway/internal/handler/subscriptions.go`: extract `userID` from context; call `usersRepo.GetUserByID` to retrieve `StripeCustomerID`; return 400 `no_subscription` if nil; call `stripeService.CreatePortalSession(customerID, cfg.StripePortalReturnURL)`; return 200 `{"portal_url": session.URL}`
- [X] T014 [US2] Add two cases to the `StripeWebhook` switch in `services/api-gateway/internal/handler/subscriptions.go`: `case "customer.subscription.updated"`: unmarshal subscription object, map Stripe status to internal status, run transaction updating `subscriptions` row (tier, status, billing_period, current_period_start, current_period_end) and `users.subscription_tier` + `alert_limit`; `case "customer.subscription.deleted"`: run transaction calling `subsRepo.Cancel(stripeSubID)` and `usersRepo.DowngradeToFree(userID)`
- [X] T015 [US2] Add `r.Post("/subscriptions/portal", subscriptionsHandler.Portal)` to `mountAuthenticatedV1Routes` in `services/api-gateway/cmd/routes.go`

**Checkpoint**: POST `/v1/subscriptions/portal` returns a working portal URL. Plan changes in portal trigger correct DB updates. Cancellation sets tier to `free`.

---

## Phase 5: User Story 3 — View Current Subscription Status (Priority: P2)

**Goal**: Any authenticated user can retrieve their current subscription tier, status, billing period, and next invoice date in a single API call.

**Independent Test**: Create users in states free/trialing/active/past_due → call GET `/v1/subscriptions/me` for each → verify response fields match database state exactly for all states.

- [X] T016 [US3] Implement `Me` method in `services/api-gateway/internal/handler/subscriptions.go`: extract `userID` from context; call `subsRepo.GetByUserID`; if `ErrNotFound` return free-tier response `{"tier":"free","status":"free","billing_period":null,"current_period_end":null,"trial_end_at":null}`; otherwise map `Subscription` fields to response JSON; return 200
- [X] T017 [US3] Add `r.Get("/subscriptions/me", subscriptionsHandler.Me)` to `mountAuthenticatedV1Routes` in `services/api-gateway/cmd/routes.go`

**Checkpoint**: GET `/v1/subscriptions/me` returns accurate data for all subscription states. Test free user returns `{"tier":"free","status":"free",...}`. Test active subscriber returns full billing details.

---

## Phase 6: User Story 4 — Handle Failed Payment & Grace Period (Priority: P3)

**Goal**: When payment fails, a 3-day grace period is scheduled via Redis. If not resolved, the user is automatically downgraded to free. If payment recovers within 3 days, the downgrade is cancelled.

**Independent Test**: Trigger `invoice.payment_failed` → verify `stripe:pending_downgrades` sorted set contains `{user_id}` with score = now+259200 → simulate 3-day expiry (advance score) → verify downgrade worker sets tier to `free` → separately trigger `invoice.payment_succeeded` before expiry → verify `ZREM` removes the entry and tier is retained.

- [X] T018 [US4] Add two cases to the `StripeWebhook` switch in `services/api-gateway/internal/handler/subscriptions.go`: `case "invoice.payment_failed"`: extract subscription ID from invoice, look up subscription via `subsRepo.GetByStripeSubID`, call `subsRepo.SetPaymentFailed(stripeSubID, time.Now())`, then `redisClient.ZAdd("stripe:pending_downgrades", redis.Z{Score: float64(time.Now().Add(72*time.Hour).Unix()), Member: userID.String()})`; `case "invoice.payment_succeeded"`: call `subsRepo.ClearPaymentFailed(stripeSubID)` and `redisClient.ZRem("stripe:pending_downgrades", userID.String())`
- [X] T019 [US4] Create `services/api-gateway/internal/worker/stripe_downgrade.go`: implement `StartDowngradeWorker(ctx context.Context, redisClient *redis.Client, usersRepo *repository.UsersRepo)` as a goroutine; loop with `time.NewTicker(60 * time.Second)`; on each tick call `redisClient.ZRangeByScoreWithScores("stripe:pending_downgrades", &redis.ZRangeBy{Min: "0", Max: strconv.FormatInt(time.Now().Unix(), 10)})`; for each result parse UUID, call `usersRepo.DowngradeToFree(ctx, userID)`, then `redisClient.ZRem("stripe:pending_downgrades", member)`; log each downgrade and each error with `slog`; exit cleanly on `ctx.Done()`
- [X] T020 [US4] Start the downgrade worker in `services/api-gateway/cmd/main.go`: add `go worker.StartDowngradeWorker(ctx, redisClient, usersRepo)` after all repos are initialized (replace the TODO comment left in T012)

**Checkpoint**: `invoice.payment_failed` enqueues a downgrade. Worker executes it after 3 days. `invoice.payment_succeeded` cancels the pending downgrade. Verify Redis state with `redis-cli ZRANGE stripe:pending_downgrades 0 -1 WITHSCORES`.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Kubernetes configuration, lightweight tests for critical logic, and end-to-end validation.

- [X] T021 [P] Add Stripe environment variable entries to the Helm `ConfigMap` and `Secret` templates in `helm/estategap/`: non-sensitive vars (`STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`, `STRIPE_PORTAL_RETURN_URL`, 8 price IDs) go in `ConfigMap`; sensitive vars (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`) go in `Secret` (Sealed Secrets pattern)
- [X] T022 [P] Write table-driven unit tests in `services/api-gateway/internal/service/stripe_test.go`: test `TierAlertLimit` map covers all 5 tiers; test trial days logic (basic/pro/global → 14, api → 0); test price ID resolution for all 8 tier+period combinations; test `ParseWebhookEvent` rejects invalid signatures
- [ ] T023 Run the full end-to-end validation sequence from `specs/008-stripe-subscriptions/quickstart.md`: checkout flow, idempotency check via `stripe events resend`, portal session creation, and grace-period downgrade queue inspection
- [X] T024 [P] Update `CLAUDE.md` Recent Changes section: replace `008-stripe-subscriptions` placeholder with final tech entry `Go 1.23 + chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, stripe-go/v81 (new), viper v1.19.0, slog (stdlib)`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2a (T003–T005)**: Depends on Phase 1 — can all run in parallel
- **Phase 2b (T006–T008)**: Depends on Phase 2a — T006 needs T003+T004, T007 needs T004, T008 needs T005; T006/T007/T008 can run in parallel with each other
- **Phase 3 (US1)**: Depends on ALL of Phase 2 — BLOCKS phases 4–6
- **Phase 4 (US2)**: Depends on Phase 3 (same handler file, incremental additions)
- **Phase 5 (US3)**: Depends on Phase 3 (can start in parallel with Phase 4)
- **Phase 6 (US4)**: Depends on Phase 3 (can start in parallel with Phases 4–5)
- **Phase 7 (Polish)**: Depends on Phases 3–6 complete

### User Story Dependencies

| Story | Depends On | Notes |
|-------|-----------|-------|
| US1 (P1) — Checkout | Phase 2 complete | First story; wires all new dependencies |
| US2 (P2) — Portal | US1 (shared handler file, adds to webhook switch) | Route + handler additions |
| US3 (P2) — Status | US1 (shared handler file) | Independent of US2 |
| US4 (P3) — Failed Payment | US1 (webhook switch additions + worker start) | Independent of US2/US3 |

### Within Each User Story

- Struct/foundation changes before handler implementation
- Handler constructor update (T009) before any method implementations (T010, T011)
- Repository implementations before handlers that call them
- Handler methods before route registration

### Parallel Opportunities

Within Phase 2a: T003 [P] + T004 [P] + T005 [P] can all run simultaneously  
Within Phase 2b: T006 [P] + T007 [P] + T008 [P] can all run simultaneously  
Within US2–US4 (after US1 complete): T013–T015 + T016–T017 + T018–T020 can proceed in parallel across stories  
Within Phase 7: T021 [P] + T022 [P] + T024 [P] can all run simultaneously  

---

## Parallel Example: Phase 2

```bash
# All Phase 2a tasks simultaneously (different files, no deps):
Task: "T003 [P] Create Alembic migration 012_subscriptions.py"
Task: "T004 [P] Update Subscription struct in libs/pkg/models/user.go"
Task: "T005 [P] Extend Config struct in internal/config/config.go"

# After T003+T004+T005 complete — Phase 2b simultaneously:
Task: "T006 [P] Create SubscriptionsRepo in internal/repository/subscriptions.go"
Task: "T007 [P] Add UpdateSubscriptionTier/DowngradeToFree to internal/repository/users.go"
Task: "T008 [P] Create StripeService in internal/service/stripe.go"
```

## Parallel Example: US2 + US3 + US4 (after US1 complete)

```bash
# After T012 complete, three stories in parallel:
Task: "T013 [US2] Implement Portal handler method"
Task: "T016 [US3] Implement Me handler method"
Task: "T018 [US4] Add invoice.payment_failed/succeeded cases to webhook switch"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001–T002)
2. Complete Phase 2 (T003–T008) — foundation blocks everything
3. Complete Phase 3 / US1 (T009–T012)
4. **STOP and VALIDATE**: Working checkout + webhook → subscription created in DB
5. Stripe test-mode payment completes → `users.subscription_tier` updated

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready (compile check passes)
2. Phase 3 (US1) → Checkout flow + webhook skeleton working (MVP)
3. Phase 4 (US2) → Portal + subscription lifecycle webhooks
4. Phase 5 (US3) → Status endpoint live
5. Phase 6 (US4) → Failed payment + grace period worker
6. Phase 7 → Helm config + tests + final validation

### Parallel Team Strategy

With 2+ developers, after Phase 2:
- **Developer A**: US1 (T009–T012) → then US4 (T018–T020)
- **Developer B**: US2 (T013–T015) + US3 (T016–T017) in parallel after US1

---

## Notes

- **Same file, sequential tasks**: T009 → T010 → T011 all modify `internal/handler/subscriptions.go` and must run in order; later T013, T014, T016, T018 add to the same file but each builds on a stable prior state
- **DB transaction requirement**: `checkout.session.completed` handler MUST update `subscriptions` table and `users` table atomically — use `primaryPool.BeginTx`
- **Raw body for webhook**: `io.ReadAll(r.Body)` MUST happen before any JSON parsing; `stripe.webhook.ConstructEvent` requires the raw bytes
- **Stripe idempotency key**: `SetNX` is atomic; if it returns `false` (key existed), return 200 immediately without executing business logic
- **`go work sync`** must be run after adding stripe-go to ensure the workspace resolves correctly
- **Commit after each checkpoint** to maintain a clean bisectable history
