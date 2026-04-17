# Tasks: Notification Dispatcher

**Input**: Design documents from `/specs/017-notification-dispatcher/`  
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5, maps to spec.md)

---

## Phase 1: Setup

**Purpose**: Bootstrap the `alert-dispatcher` Go module with all dependencies and project skeleton.

- [X] T001 Initialize `services/alert-dispatcher/go.mod` with module `github.com/estategap/services/alert-dispatcher` and all required dependencies: `nats.go v1.37`, `go-chi/chi v5`, `pgx/v5`, `go-redis/v9`, `aws-sdk-go-v2/ses`, `go-telegram-bot-api/v5`, `twilio/twilio-go`, `firebase.google.com/go/v4`, `prometheus/client_golang`, `spf13/viper`, `golang.org/x/sync`
- [X] T002 Create directory skeleton in `services/alert-dispatcher/`: `cmd/`, `internal/config/`, `internal/consumer/`, `internal/dispatcher/`, `internal/sender/`, `internal/repository/`, `internal/model/`, `internal/templates/`, `internal/metrics/`, `internal/router/`
- [X] T003 [P] Copy and adapt `.golangci.yml` from `services/alert-engine/.golangci.yml` to `services/alert-dispatcher/.golangci.yml`
- [X] T004 [P] Create `services/alert-dispatcher/.env.example` with all variables from `specs/017-notification-dispatcher/quickstart.md` (DATABASE_URL, NATS_URL, REDIS_URL, AWS_*, TELEGRAM_*, TWILIO_*, FIREBASE_*, BASE_URL, HEALTH_PORT, WORKER_POOL_SIZE, BATCH_SIZE, LOG_LEVEL)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure — migration, config, models, repositories, consumer loop, dispatcher skeleton, and health server. All user story phases depend on this phase being complete.

**⚠️ CRITICAL**: No channel sender work can begin until this phase is complete.

- [X] T005 Write Alembic migration `services/pipeline/alembic/versions/019_notification_dispatcher.py`: add `preferred_language VARCHAR(10) DEFAULT 'en'`, `telegram_chat_id BIGINT NULL`, `telegram_link_token VARCHAR(64) NULL`, `push_subscription_json TEXT NULL`, `webhook_secret VARCHAR(64) NULL`, `phone_e164 VARCHAR(20) NULL` to `users`; add `event_id UUID NULL`, `attempt_count SMALLINT DEFAULT 1` to `alert_history`; add unique constraint `uq_alert_history_event_channel (event_id, channel) WHERE event_id IS NOT NULL`; set `down_revision = "f4b5c6d7e8f9"` (018)
- [X] T006 [P] Implement `services/alert-dispatcher/internal/model/types.go`: `NotificationEvent` (copy from alert-engine — no cross-module import), `ListingSummary`, `DigestListing`, `UserChannelProfile` (UserID, Email, PreferredLanguage, TelegramChatID *int64, PushToken *string, PhoneE164 *string, WebhookSecret *string), `DeliveryResult` (Success bool, AttemptCount int, ErrorDetail string, DeliveredAt *time.Time), `EmailTemplateData` (all fields from data-model.md)
- [X] T007 [P] Implement `services/alert-dispatcher/internal/config/config.go`: Viper with `AutomaticEnv()`; typed struct for all env vars from `.env.example`; fail fast if `DATABASE_URL` or `NATS_URL` empty; parse `WORKER_POOL_SIZE` defaulting to `runtime.NumCPU() * 4`; parse `BATCH_SIZE` defaulting to `50`
- [X] T008 Implement `services/alert-dispatcher/internal/repository/user.go`: `GetChannelProfile(ctx context.Context, userID string) (*model.UserChannelProfile, error)` — SELECT from `users` joining all dispatcher columns; `StoreTelegramChatID(ctx context.Context, userID string, chatID int64) error` — UPDATE `telegram_chat_id`, clear `telegram_link_token`; `ClearPushToken(ctx context.Context, userID string) error` — SET `push_subscription_json = NULL`; use `pgxpool.Pool` (primary for writes, replica for reads)
- [X] T009 Implement `services/alert-dispatcher/internal/repository/history.go`: `Insert(ctx, historyID, eventID, ruleID, listingID, channel string) error` — `INSERT INTO alert_history … ON CONFLICT (event_id, channel) WHERE event_id IS NOT NULL DO NOTHING`; `UpdateStatus(ctx, historyID, status, errorDetail string, attempts int, deliveredAt *time.Time) error` — UPDATE delivery_status, error_detail, attempt_count, delivered_at
- [X] T010 [P] Implement `services/alert-dispatcher/internal/metrics/metrics.go`: Prometheus `Counter` `dispatcher_notifications_total{channel,status}`, `Histogram` `dispatcher_delivery_latency_seconds{channel}`, `Counter` `dispatcher_retry_attempts_total{channel}`, `Gauge` `dispatcher_consumer_lag`; register on default registry
- [X] T011 [P] Implement `services/alert-dispatcher/internal/router/router.go`: chi router with `GET /healthz` (always 200), `GET /readyz` (check NATS + DB + Redis connections), `GET /metrics` (promhttp.Handler()); accept dependency handles via constructor
- [X] T012 Implement `services/alert-dispatcher/internal/sender/sender.go`: `Sender` interface (`Send(ctx, event, user) (DeliveryResult, error)`); `withRetry(ctx context.Context, maxAttempts int, delays []time.Duration, fn func() (DeliveryResult, error)) (DeliveryResult, error)` — standard retry helper with context-aware sleep; exported `RetryDelays = []time.Duration{time.Second, 4*time.Second, 16*time.Second}`
- [X] T013 Implement `services/alert-dispatcher/internal/dispatcher/dispatcher.go`: `Dispatcher` struct holding `map[string]sender.Sender` registry and `*repository.HistoryRepo` and `*repository.UserRepo` and `*metrics.Registry`; `Dispatch(ctx, event)` — load UserChannelProfile, pre-insert history record (status `pending`), call registered Sender, UpdateStatus to `sent`/`failed`, emit Prometheus metrics and slog structured log
- [X] T014 Implement `services/alert-dispatcher/internal/consumer/consumer.go`: connect to NATS JetStream; ensure durable pull consumer `alert-dispatcher` on stream `ALERTS` with `FilterSubject: alerts.notifications.>`, `AckPolicy: AckExplicit`, `MaxDeliver: 1`, `AckWait: 60s`, `MaxAckPending: 500`; bounded goroutine worker pool (`WORKER_POOL_SIZE`); fetch loop `js.Fetch(batchSize)` → dispatch → ack/nack; graceful shutdown via `context.Done()`; update `dispatcher_consumer_lag` gauge
- [X] T015 Implement `services/alert-dispatcher/cmd/main.go`: load config; init pgxpool (primary + replica); init Redis; init NATS + JetStream; init HistoryRepo + UserRepo; init Dispatcher with empty sender map; init metrics registry; init chi health router; wire consumer; start health HTTP server and consumer using `golang.org/x/sync/errgroup`; handle SIGTERM/SIGINT graceful shutdown
- [X] T016 [P] Create `services/alert-dispatcher/Dockerfile`: multi-stage build (golang:1.23-alpine builder, gcr.io/distroless/static-debian12 runtime); copy binary; expose port 8081; non-root user

**Checkpoint**: `cmd/main.go` compiles and boots; `/healthz` returns 200; NATS consumer loop starts; messages are consumed and nack'd (no senders registered yet).

---

## Phase 3: User Story 1 — Email Alert (Priority: P1) 🎯 MVP

**Goal**: Users receive a formatted HTML email within 30s of a matching deal, with open/click tracking and correct locale rendering.

**Independent Test**: Publish a `NotificationEvent` with `channel: "email"` to `alerts.notifications.ES`. Verify the user receives an HTML email with photo, address, price, deal score badge, CTA buttons, and a 1×1 tracking pixel. Verify `alert_history` record with `delivery_status = 'sent'` is written.

- [X] T017 Create `services/alert-dispatcher/internal/templates/email_en.html`: table-based layout (no CSS Grid/Flexbox for Outlook); inline CSS only; sections: logo header, property hero `<img src="{{.PhotoURL}}">`, address + price (`{{.Address}}`, `{{.PriceFormatted}}`), deal score badge (`background-color: {{.DealBadgeColor}}`), features `<ul>` (range `.Features`), two CTA buttons linking to `{{.TrackClickAnalysis}}` and `{{.TrackClickPortal}}`, 1×1 transparent tracking pixel `<img src="{{.TrackOpenURL}}" width="1" height="1">`; digest variant: `{{if .IsDigest}}` loop over `.Listings`; wrap in `{{define "email"}}…{{end}}`
- [X] T018 [P] Create `services/alert-dispatcher/internal/templates/email_es.html`: identical structure to `email_en.html` with Spanish UI strings (headings, button labels, captions)
- [X] T019 [P] Create `services/alert-dispatcher/internal/templates/email_de.html`: identical structure, German UI strings
- [X] T020 [P] Create `services/alert-dispatcher/internal/templates/email_fr.html`: identical structure, French UI strings
- [X] T021 [P] Create `services/alert-dispatcher/internal/templates/email_pt.html`: identical structure, Portuguese UI strings
- [X] T022 Implement `services/alert-dispatcher/internal/sender/email.go`: embed templates with `//go:embed templates/*.html`; parse all at startup into `map[string]*template.Template`; `Send` method: resolve template by `user.PreferredLanguage` (fallback `"en"`); build `EmailTemplateData` from event + pre-inserted `history_id`; compute `DealBadgeColor` (tier 1=`#22c55e`, 2=`#84cc16`, 3=`#f59e0b`, 4=`#ef4444`); format `PriceFormatted` with `shopspring/decimal`; render to `bytes.Buffer`; call `ses.SendEmail` with HTML body and text/plain fallback; use `withRetry(RetryDelays)` skipping retry on `SenderFault`; return `DeliveryResult`
- [X] T023 Write unit tests in `services/alert-dispatcher/internal/sender/email_test.go`: table-driven test for template rendering with each supported locale (en, es, de, fr, pt); assert tracking pixel URL contains `action=open`; assert CTA URL contains `action=click`; assert deal badge color matches tier; assert digest renders listing loop; assert fallback to `"en"` when locale has no template

**Checkpoint**: Register `EmailSender` in dispatcher (`cmd/main.go`); send a test NATS message; verify email delivered and `alert_history` record written.

---

## Phase 4: User Story 2 — Telegram Alert (Priority: P2)

**Goal**: Users with a linked Telegram account receive a photo message with inline keyboard within 30s. Users can link their account via `/start {token}`.

**Independent Test**: With a user having `telegram_chat_id` set in DB, publish a `NotificationEvent` with `channel: "telegram"`. Verify bot sends `sendPhoto` with MarkdownV2 caption and three inline keyboard buttons. Verify `alert_history` written. Separately: send `/start {token}` to bot; verify `telegram_chat_id` stored and `telegram_link_token` cleared.

- [X] T024 Implement `services/alert-dispatcher/internal/sender/telegram.go`: init `tgbotapi.NewBotAPI(token)` in constructor; start long-poll goroutine (`GetUpdatesChan`) that handles `/start {token}` commands by calling `userRepo.StoreTelegramChatID`; `Send` method: if `user.TelegramChatID == nil` return failed `DeliveryResult{ErrorDetail: "account not linked"}`; build `PhotoConfig` with `FileURL = *event.ListingSummary.ImageURL`; build MarkdownV2 caption with bold price, deal score, city; build `InlineKeyboardMarkup` with three buttons (View Analysis → `analysis_url`, View on Portal → `portal_url`, Dismiss → callback `dismiss:{historyID}`); call `bot.Send(SendPhotoConfig{…, ReplyMarkup: keyboard})`; on `RetryAfter` error honour the wait; use `withRetry(RetryDelays)`
- [X] T025 Write unit tests in `services/alert-dispatcher/internal/sender/telegram_test.go`: nil `TelegramChatID` → `DeliveryResult{Success: false, ErrorDetail: "account not linked"}` without calling bot API; caption formatting includes bold price and deal score; inline keyboard has exactly 3 buttons with correct labels

**Checkpoint**: Register `TelegramSender` in dispatcher; publish NATS test message; verify bot message received in test Telegram chat.

---

## Phase 5: User Story 3 — WhatsApp Notification (Priority: P3)

**Goal**: Users with a verified phone number receive a Twilio WhatsApp template message with property summary and link.

**Independent Test**: With a user having `phone_e164` set in DB, publish a `NotificationEvent` with `channel: "whatsapp"`. Verify Twilio `CreateMessage` is called with `ContentSid` and correct `ContentVariables` JSON. Verify `alert_history` written.

- [X] T026 Implement `services/alert-dispatcher/internal/sender/whatsapp.go`: init `twilio.NewRestClient(accountSid, authToken)` in constructor; `Send` method: if `user.PhoneE164 == nil` return failed `DeliveryResult{ErrorDetail: "no phone number"}`; build `ContentVariables` JSON `{"1": address, "2": price_formatted, "3": deal_score_str, "4": analysis_url}`; call `client.Api.CreateMessage` with `From: "whatsapp:+{from_number}"`, `To: "whatsapp:{user.PhoneE164}"`, `ContentSid: templateSID`, `ContentVariables: json_str`; no retry on 4xx; use `withRetry(RetryDelays)` for 5xx/network errors
- [X] T027 Write unit tests in `services/alert-dispatcher/internal/sender/whatsapp_test.go`: nil `PhoneE164` → `DeliveryResult{Success: false}`; `ContentVariables` JSON contains all 4 template variables with correct values; 4xx response from mock → immediate fail (no retry); 5xx → retried up to 3 times

**Checkpoint**: Register `WhatsAppSender` in dispatcher; publish NATS test message; verify Twilio API call made with correct params (use Twilio test credentials).

---

## Phase 6: User Story 4 — Web Push Notification (Priority: P4)

**Goal**: Users with an FCM registration token receive a web push notification with title, body, image, and click URL.

**Independent Test**: With a user having `push_subscription_json` (FCM token) set in DB, publish a `NotificationEvent` with `channel: "push"`. Verify Firebase `messaging.Send` is called with correct `Token`, `Notification` fields, and `Webpush.FCMOptions.Link`. Verify token-expiry error clears `push_subscription_json` in DB without retrying.

- [X] T028 Implement `services/alert-dispatcher/internal/sender/push.go`: init `firebase.NewApp(ctx, nil, option.WithCredentialsJSON(credsJSON))` and `app.Messaging(ctx)` in constructor; `Send` method: if `user.PushToken == nil` return failed `DeliveryResult{ErrorDetail: "no push subscription"}`; build `messaging.Message{Token: *user.PushToken, Notification: &messaging.Notification{Title, Body, ImageURL}, Webpush: &messaging.WebpushConfig{FCMOptions: &messaging.WebpushFCMOptions{Link: analysisURL}}}`; call `client.Send(ctx, msg)`; on `messaging/registration-token-not-registered` error call `userRepo.ClearPushToken` and return failed result without retrying; use `withRetry(RetryDelays)` for other transient errors
- [X] T029 Write unit tests in `services/alert-dispatcher/internal/sender/push_test.go`: nil `PushToken` → `DeliveryResult{Success: false}` without Firebase call; token-not-registered error → `ClearPushToken` called, no retry, `Success: false`; successful send → `DeliveryResult{Success: true, AttemptCount: 1}`

**Checkpoint**: Register `PushSender` in dispatcher; publish NATS test message; verify Firebase API call made (use Firebase emulator or mock client).

---

## Phase 7: User Story 5 — Webhook Delivery with Retry (Priority: P5)

**Goal**: Users with a webhook URL receive a signed HTTP POST. Transient 5xx responses trigger up to 3 retries with exponential backoff. Redis persists the retry counter across pod restarts.

**Independent Test**: Configure a test HTTP server returning 503 on first two requests, 200 on third. Publish a `NotificationEvent` with `channel: "webhook"`. Verify: three total HTTP calls; `X-Webhook-Signature` header present and valid on each; Redis key `webhook:retry:{event_id}` increments correctly; `alert_history` updated to `sent`. Separately: 4xx response → immediate fail, no retry.

- [X] T030 Implement `services/alert-dispatcher/internal/sender/webhook.go`: `http.Client` with 10s timeout; `Send` method: if `event.WebhookURL == nil` return failed `DeliveryResult{ErrorDetail: "no webhook URL"}`; marshal `event` to JSON body; compute `X-Webhook-Signature: sha256={hex(hmac.New(sha256, secret, body))}`; set headers `Content-Type: application/json`, `X-Estategap-Event: alert.notification`, `X-Delivery-ID: {historyID}`; INCR Redis key `webhook:retry:{event.EventID}` with `EXPIRE 300`; POST and check response: 2xx → success, 4xx → return failed (no retry), 5xx/network error → retry via `withRetry(RetryDelays)` up to 3 retries; if `user.WebhookSecret == nil` skip HMAC (sign with empty secret, log warning)
- [X] T031 Write unit tests in `services/alert-dispatcher/internal/sender/webhook_test.go`: HMAC-SHA256 signature computed correctly (compare against reference implementation); 5xx response → retried exactly 3 times before returning failed; 4xx response → immediate fail, zero retries; nil `WebhookURL` on event → `DeliveryResult{Success: false}` without HTTP call; Redis INCR increments on each attempt

**Checkpoint**: Register `WebhookSender` in dispatcher; run `webhook_test.go`; publish NATS test message to a local HTTP server; verify all retry and signing behaviour.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Integration tests, Helm deployment, linting validation.

- [X] T032 Write integration test in `services/alert-dispatcher/internal/consumer/consumer_integration_test.go` (build tag `integration`): spin up NATS + PostgreSQL with testcontainers-go; publish a `NotificationEvent` to `alerts.notifications.ES`; assert `alert_history` record created with correct `event_id`, `channel`, `delivery_status`; assert idempotent: publish same event again, verify only one record exists
- [X] T033 Write unit tests in `services/alert-dispatcher/internal/repository/history_test.go`: `Insert` with duplicate `event_id+channel` → second insert is no-op (ON CONFLICT DO NOTHING); `UpdateStatus` correctly sets all fields including `delivered_at`
- [X] T034 Write unit tests in `services/alert-dispatcher/internal/dispatcher/dispatcher_test.go`: unknown channel → `DeliveryResult{Success: false, ErrorDetail: "unknown channel"}`; `GetChannelProfile` DB error → dispatch fails gracefully without panic; successful dispatch → history UpdateStatus called with `sent`
- [X] T035 [P] Add `alert-dispatcher` to Helm chart in `helm/estategap/`: Deployment (image, envFrom ConfigMap + Sealed Secrets, livenessProbe `GET /healthz`, readinessProbe `GET /readyz`, resources `256Mi/200m`), Service (port 8081), ConfigMap (non-secret env vars), reference Sealed Secrets for all credentials
- [ ] T036 [P] Run `go vet ./...` and `golangci-lint run` in `services/alert-dispatcher/`; fix all linting errors; run `go test ./...` to confirm all unit tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T003 and T004 are parallel
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all channel sender phases**
  - T006, T007 parallel after T001/T002
  - T008, T009 parallel after T006
  - T010, T011 parallel after T007
  - T012 after T006
  - T013 after T008, T009, T010, T011, T012
  - T014 after T013
  - T015 after T014
  - T016 parallel after T001
- **Phase 3 (US1 Email)**: Depends on Phase 2 completion
  - T017 first (reference template); T018–T021 parallel after T017
  - T022 after T017–T021 (needs all templates embedded)
  - T023 parallel with T022
- **Phases 4–7 (US2–US5)**: All depend on Phase 2; independent of each other
- **Phase 8 (Polish)**: Depends on all desired sender phases complete

### User Story Dependencies

- **US1 (P1)**: Foundational complete → no other story dependencies
- **US2 (P2)**: Foundational complete → no story dependencies (independent of US1)
- **US3 (P3)**: Foundational complete → no story dependencies
- **US4 (P4)**: Foundational complete → no story dependencies
- **US5 (P5)**: Foundational complete → no story dependencies (needs Redis from foundational)

### Parallel Opportunities

- T003, T004, T016 are fully parallel within/after Phase 1
- T006, T007 are parallel within Phase 2
- T008, T009, T010, T011 are parallel after T006/T007
- T018, T019, T020, T021 are parallel after T017
- T023 parallel with T022
- US2–US5 sender phases can all be developed in parallel by different engineers once Phase 2 is done
- T035, T036 parallel in Phase 8

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch in parallel (different files, no dependencies on each other):
Task: "T006 Implement internal/model/types.go"
Task: "T007 Implement internal/config/config.go"
Task: "T010 Implement internal/metrics/metrics.go"
Task: "T011 Implement internal/router/router.go"

# After T006 completes, launch in parallel:
Task: "T008 Implement internal/repository/user.go"
Task: "T009 Implement internal/repository/history.go"
Task: "T012 Implement internal/sender/sender.go"
```

## Parallel Example: Phase 3 Email Templates

```bash
# After T017 (email_en.html) completes, launch in parallel:
Task: "T018 Create internal/templates/email_es.html"
Task: "T019 Create internal/templates/email_de.html"
Task: "T020 Create internal/templates/email_fr.html"
Task: "T021 Create internal/templates/email_pt.html"

# T022 and T023 can overlap (email.go and email_test.go written concurrently):
Task: "T022 Implement internal/sender/email.go"
Task: "T023 Write internal/sender/email_test.go"
```

## Parallel Example: Channel Senders (Phase 4–7)

```bash
# Once Phase 2 is complete, all channel senders are fully independent:
Task: "T024 Implement internal/sender/telegram.go"    # Developer A
Task: "T026 Implement internal/sender/whatsapp.go"    # Developer B
Task: "T028 Implement internal/sender/push.go"        # Developer C
Task: "T030 Implement internal/sender/webhook.go"     # Developer D
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL** — blocks everything)
3. Complete Phase 3: US1 Email (T017–T023)
4. **STOP and VALIDATE**: Publish test NATS event → verify email received + DB record written
5. Deploy to staging; collect feedback

### Incremental Delivery

1. Setup + Foundational → service boots and consumes messages
2. + US1 Email → first delivery channel live (MVP)
3. + US2 Telegram → second channel, Telegram linking UX
4. + US3 WhatsApp → third channel
5. + US4 Push → fourth channel
6. + US5 Webhook → developer integration channel
7. Polish → full test coverage, Helm deployment

### Parallel Team Strategy (4 developers)

Once Phase 2 is complete:
- Developer A: US1 Email (T017–T023) — includes templates
- Developer B: US2 Telegram (T024–T025) — includes bot linking
- Developer C: US3 WhatsApp + US4 Push (T026–T029)
- Developer D: US5 Webhook (T030–T031) + Phase 8 Polish (T032–T036)

---

## Notes

- `[P]` tasks operate on different files and have no dependencies on incomplete tasks
- Every channel sender must be registered in `cmd/main.go` to be active
- Migration T005 must be applied (`uv run alembic upgrade head`) before running integration tests
- Telegram bot long-poll goroutine starts in `TelegramSender` constructor — ensure it is shut down gracefully via context cancellation
- Email templates use `html/template` (not `text/template`) for automatic HTML escaping
- `withRetry` must check `ctx.Err()` between attempts to respect cancellation
- Webhook Redis key TTL (300s) covers the full 1+4+16=21s retry window with margin
