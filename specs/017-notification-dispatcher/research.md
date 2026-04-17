# Research: 017 — Notification Dispatcher

**Phase**: 0 — Pre-design research  
**Date**: 2026-04-17

---

## 1. NATS JetStream Consumer Pattern

**Decision**: Durable pull consumer on subject `alerts.notifications.>`, consumer group name `alert-dispatcher`, max-deliver 1 (dispatcher owns retry logic).

**Rationale**: The alert-engine publishes to per-country subjects (`alerts.notifications.ES`, `alerts.notifications.DE`, …). Using a wildcard `>` subject lets a single consumer handle all countries. Pull consumers are preferred over push for back-pressure control — the dispatcher fetches in batches matching its concurrency level. Setting `MaxDeliver=1` in JetStream prevents NATS-level redelivery; retry is owned entirely by the dispatcher's in-process backoff loop, which gives finer control and avoids double-delivery on slow but successful attempts.

**Alternatives considered**:
- Push consumer with `AckWait` redelivery — rejected because it can race with in-progress retries and produce duplicates.
- Per-country consumer — rejected because it multiplies consumer complexity without benefit; wildcards handle fan-in cleanly.

---

## 2. Retry & Backoff Strategy

**Decision**: Channel-level in-process retry with exponential backoff: attempt 1 → 0s delay (immediate), attempt 2 → 1s, attempt 3 → 4s, attempt 4 → 16s. Maximum 3 retries (4 total attempts). After exhaustion, mark `delivery_status = 'failed'` and `nack` the NATS message. Webhook retry state (`webhook:retry:{notification_id}`) tracked in Redis to survive pod restarts for long-running retry windows.

**Rationale**: The user-specified intervals (1s, 4s, 16s) fit the 30-second SLA for the success path. Keeping retries in-process avoids a separate retry queue for email/Telegram/push since their retry windows are short. Webhook retries are persisted in Redis because webhook delivery can fail for reasons that persist (endpoint down), and the retry state must survive a pod restart.

**Alternatives considered**:
- NATS redelivery with `AckWait` — rejected; complicates multi-channel dispatch where some channels succeed and others fail.
- Redis-based retry queue for all channels — over-engineered for channels with sub-minute retry windows.

---

## 3. Concurrency Model

**Decision**: Each consumed NATS message is dispatched to a goroutine. Within one message, if the user has multiple channels, `errgroup` fans out to one goroutine per sender. The consumer worker pool is bounded by `WORKER_POOL_SIZE` (default: `runtime.NumCPU() * 4`).

**Rationale**: NATS message processing is I/O-bound (external API calls). Goroutines are cheap; bounded pool prevents memory blow-up under burst load. `errgroup` collects all channel errors so the overall dispatch result is logged even if individual channels fail independently.

**Alternatives considered**:
- Sequential channel dispatch per message — too slow; violates 30s SLA when user has 3+ channels.
- Unlimited goroutines — risks OOM under burst.

---

## 4. Email Templating & Localization

**Decision**: Go `html/template` with one template file per language embedded via `embed.FS`. Template files: `internal/templates/email_{lang}.html` (e.g., `email_en.html`, `email_es.html`, `email_de.html`, `email_fr.html`, `email_pt.html`). Language resolution: use `users.preferred_language`, fall back to `"en"` if template for that language does not exist. Templates are parsed once at startup and cached in a `map[string]*template.Template`.

**Rationale**: `html/template` automatically escapes HTML preventing XSS from listing data. Embedding templates in the binary avoids file-system dependencies at runtime and simplifies the Docker image. One template per language is simpler than a single template with i18n message keys given the moderate number of supported languages (≤10).

**Open/click tracking**: Open tracking via a 1×1 transparent PNG at `/api/v1/alerts/track?id={history_id}&action=open`. Click tracking via redirect at `/api/v1/alerts/track?id={history_id}&action=click&url={encoded_destination}`. These URLs are substituted into the template at render time using the delivery record ID.

**Alternatives considered**:
- `text/template` — rejected; unsafe for HTML context.
- Single template with `next-intl` message keys — over-engineered for a backend-rendered email template.

---

## 5. Telegram Bot Delivery

**Decision**: Use `go-telegram-bot-api/telegram-bot-api/v5`. Delivery: `SendPhotoConfig` with `FileURL` pointing to the listing's `image_url` and caption in MarkdownV2 format. Inline keyboard: three buttons — `[View Analysis](analysis_url)`, `[View on Portal](portal_url)`, `[Dismiss]` (callback `dismiss:{history_id}`). Linking flow: long-polling bot with `/start {token}` handler stores `telegram_chat_id` in `users` table. The bot runs as a goroutine within the same service process.

**Rationale**: `go-telegram-bot-api` is the most widely used Go Telegram library with active maintenance. MarkdownV2 supports bold/italic for structured captions. FileURL avoids proxying images through the service. Long-polling is simpler than webhook mode (no public HTTPS endpoint needed for the bot).

**Alternatives considered**:
- Webhook mode for the Telegram bot — requires a publicly routable HTTPS endpoint; adds deployment complexity.
- Separate bot service — over-engineered; the bot's only job is to store `chat_id` on `/start`.

---

## 6. WhatsApp via Twilio

**Decision**: Use `github.com/twilio/twilio-go`. Send using `MessagesCreate` with `From: "whatsapp:+{twilio_number}"`, `To: "whatsapp:+{user_phone}"`, and `ContentSid: {WHATSAPP_TEMPLATE_SID}`. Template variables provided as `ContentVariables` JSON. Template variables: `1=address`, `2=price`, `3=deal_score`, `4=link`.

**Rationale**: Twilio's Go SDK wraps the REST API with automatic retries and structured errors. WhatsApp Business API requires a pre-approved template for proactive messages; the template SID is environment-configured. `ContentVariables` is the current Twilio-preferred approach for template parameters (as opposed to the legacy `Body` field).

**Alternatives considered**:
- Raw `net/http` calls to Twilio REST — more control but more boilerplate; SDK handles auth and serialization.
- Meta WhatsApp Cloud API directly — requires additional setup; Twilio is the project's already-assumed provider.

---

## 7. Firebase FCM Push

**Decision**: Use `firebase.google.com/go/v4/messaging`. Initialize the Firebase app from a service account JSON credential (env var `FIREBASE_CREDENTIALS_JSON`). Send `messaging.Message` with `Token: user.push_subscription_json` (stored as a plain FCM registration token string), `Notification: &messaging.Notification{Title, Body, ImageURL}`, and `Webpush: &messaging.WebpushConfig{FCMOptions: {Link: click_action_url}}`.

**Rationale**: The official Firebase Admin SDK handles token refresh and HTTP/2 multiplexing. Storing the FCM registration token as a plain string in `push_subscription_json` is sufficient — it is not a Web Push subscription object. `WebpushConfig.FCMOptions.Link` sets the click-through URL for web push.

**On token expiry**: If FCM returns `messaging/registration-token-not-registered`, set `push_subscription_json = NULL` in the database (token is invalid, no retry).

**Alternatives considered**:
- Web Push Protocol directly (VAPID + RFC 8030) — avoids vendor lock-in but requires managing encryption; FCM handles this transparently.

---

## 8. Webhook Delivery & HMAC Signing

**Decision**: Standard `net/http` client with 10s timeout. POST body: `json.Marshal(notification_event)`. Signature header: `X-Webhook-Signature: sha256=<hex(HMAC-SHA256(secret, body))>`. Retry state in Redis key `webhook:retry:{notification_id}` (INCR + EXPIRE 300s). Do not retry on 4xx (except 429); retry on 5xx and network errors.

**Rationale**: HMAC-SHA256 over the raw request body is the standard signing approach (used by GitHub, Stripe). Storing retry count in Redis allows the service to survive a pod restart mid-retry window. 4xx errors are not retried because they indicate a permanent client error (bad URL, auth rejected, etc.). 429 is not retried either — without a `Retry-After` header we cannot safely re-queue; log and fail.

**Alternatives considered**:
- Storing retry state in PostgreSQL — higher write latency for a transient counter; Redis TTL is a natural expiry mechanism.

---

## 9. Database Schema Additions

**Decision**: New Alembic migration `019_notification_dispatcher.py`:

**`users` table — new columns**:
| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `telegram_chat_id` | `BIGINT` | `NULL` | Telegram chat ID set on `/start` |
| `telegram_link_token` | `VARCHAR(64)` | `NULL` | One-time linking token; cleared after use |
| `push_subscription_json` | `TEXT` | `NULL` | FCM registration token |
| `preferred_language` | `VARCHAR(10)` | `'en'` | Language code for email templates |
| `webhook_secret` | `VARCHAR(64)` | `NULL` | HMAC secret for webhook signing |
| `phone_e164` | `VARCHAR(20)` | `NULL` | E.164 phone for WhatsApp (if not already present) |

**`alert_history` table — new columns**:
| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `event_id` | `UUID` | required | `NotificationEvent.EventID` for idempotency |
| `attempt_count` | `SMALLINT` | `1` | Number of delivery attempts made |

**Rationale**: `event_id` enables idempotent inserts — if the NATS message is redelivered (e.g., after a crash before ack), a `INSERT … ON CONFLICT (event_id, channel) DO NOTHING` prevents duplicate records.

---

## 10. Metrics

**Prometheus metrics exposed at `:8081/metrics`**:

| Metric | Type | Labels |
|--------|------|--------|
| `dispatcher_notifications_total` | Counter | `channel`, `status` (sent/failed) |
| `dispatcher_delivery_latency_seconds` | Histogram | `channel` |
| `dispatcher_retry_attempts_total` | Counter | `channel` |
| `dispatcher_consumer_lag` | Gauge | — |

---

## 11. Constitution Compliance

| Principle | Compliance |
|-----------|-----------|
| Polyglot Architecture (Go for high-throughput) | ✅ Go service |
| Event-Driven (NATS JetStream) | ✅ Consumes `alerts.notifications.>` |
| No direct HTTP between services | ✅ Consumes from NATS, not calling alert-engine HTTP |
| Country-First partitioning | ✅ Subject includes country; delivery records include country via rule |
| Code Quality (golangci-lint, slog, pgx, no ORM) | ✅ All enforced |
| Security (no secrets in code; Sealed Secrets) | ✅ All credentials via env/K8s Sealed Secrets |
| Kubernetes-native (Dockerfile + Helm) | ✅ Required |
| Protobuf for inter-service contracts | ⚠️ NATS events use JSON (inherited from alert-engine pattern); gRPC not used for this service (no synchronous callers). No new proto needed. |
