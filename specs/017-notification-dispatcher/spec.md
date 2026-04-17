# Feature Specification: Notification Dispatcher

**Feature Branch**: `017-notification-dispatcher`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Build the Go notification dispatcher that delivers alerts via email, Telegram, WhatsApp, push, and webhook."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive Email Alert for a Matching Deal (Priority: P1)

A user has configured email as their preferred notification channel. When the alert engine publishes a notification event for a matching deal, the user receives a well-formatted HTML email within 30 seconds containing the property photo, address, price, deal score badge, key features, and call-to-action buttons linking to the analysis and the original portal listing.

**Why this priority**: Email is the most universally used notification channel and the primary delivery path for most users. It represents the baseline delivery capability the system must achieve first.

**Independent Test**: Publish a notification event with channel "email" to the NATS stream. Verify the user receives an HTML email containing all required template fields within 30 seconds, and that a delivery record is written to the database with status "sent".

**Acceptance Scenarios**:

1. **Given** a notification event with channel "email" is published, **When** the dispatcher processes it, **Then** the user receives an HTML email rendered in their preferred language within 30 seconds.
2. **Given** the email template includes a tracking pixel and click-tracking links, **When** the email is rendered, **Then** the pixel and CTA button URLs reference the tracking API endpoint.
3. **Given** the email delivery succeeds, **When** the SES API responds with a message ID, **Then** the delivery record in the database is updated to status "sent".
4. **Given** the email delivery fails with a transient error, **When** the dispatcher retries up to 3 times, **Then** if all attempts fail, the delivery record is updated to status "failed" with the error detail captured.

---

### User Story 2 - Receive Telegram Alert with Photo and Buttons (Priority: P2)

A user who has linked their Telegram account receives a bot message with the property photo, a formatted caption with price and deal score, and three inline keyboard buttons: View Analysis, View on Portal, and Dismiss.

**Why this priority**: Telegram delivers immediate, mobile-native alerts that are preferred by a significant portion of users in European markets. Account linking is a prerequisite, making this more complex than email but still high-value.

**Independent Test**: With a user who has `telegram_chat_id` populated in the database, publish a notification event with channel "telegram". Verify the bot sends a photo message with inline keyboard to the correct chat within 30 seconds.

**Acceptance Scenarios**:

1. **Given** a user has a linked Telegram account (chat_id stored in database), **When** a notification event with channel "telegram" is published, **Then** the bot sends a `sendPhoto` message with formatted Markdown caption and InlineKeyboardMarkup to the user's chat.
2. **Given** a user sends `/start {linking_token}` to the bot, **When** the bot handler processes the command, **Then** the user's `telegram_chat_id` is stored and the account is confirmed as linked.
3. **Given** a user has no linked Telegram account (no chat_id), **When** a "telegram" notification event is processed, **Then** delivery is skipped and the delivery record is marked "failed" with reason "account not linked".

---

### User Story 3 - Receive WhatsApp Notification (Priority: P3)

A user who has opted in to WhatsApp notifications receives a pre-approved template message on WhatsApp containing the property address, price, deal score, and a direct link.

**Why this priority**: WhatsApp provides high open rates in markets such as Spain and Portugal. Delivery is constrained by Twilio's pre-approved template requirement.

**Independent Test**: Publish a notification event with channel "whatsapp". Verify a Twilio API call is made with the correct template SID and variable values, and that the delivery record is written.

**Acceptance Scenarios**:

1. **Given** a user has a verified WhatsApp-capable phone number on file, **When** a "whatsapp" notification event is processed, **Then** a Twilio Messages API call is made using the approved template with property address, price, deal score, and link substituted as template variables.
2. **Given** the Twilio API returns an error, **When** the dispatcher retries up to 3 times with backoff, **Then** if all attempts fail, the delivery record is updated to status "failed".

---

### User Story 4 - Receive Web Push Notification (Priority: P4)

A user who has granted push permission in their browser receives a web push notification with the property title, a summary body, the property photo thumbnail, and a click URL that opens the analysis page.

**Why this priority**: Web push complements email for users who are actively browsing and provides instant delivery without requiring a messaging account.

**Independent Test**: With a user who has a valid FCM registration token stored, publish a "push" notification event. Verify the Firebase Messaging API is called with the correct payload (title, body, image, click_action) within 30 seconds.

**Acceptance Scenarios**:

1. **Given** a user has a stored FCM registration token, **When** a "push" notification event is processed, **Then** Firebase Cloud Messaging is called with title, body, image URL, and click_action URL.
2. **Given** the FCM token is expired or invalid, **When** delivery fails, **Then** the push subscription is invalidated in the database and the delivery record is marked "failed".

---

### User Story 5 - Webhook Delivery with Retry (Priority: P5)

A developer using EstateGap has configured a webhook URL. When a matching alert fires, the dispatcher sends a signed HTTP POST to their endpoint with the full notification payload. If the endpoint returns a 5xx response, the dispatcher retries up to 3 times with exponential backoff before marking the delivery as failed.

**Why this priority**: Webhooks enable third-party integrations and automation workflows. Retry reliability is critical for developer trust.

**Independent Test**: Configure a webhook endpoint that returns 503 on the first two requests and 200 on the third. Publish a "webhook" notification event. Verify three attempts are made, the final delivery succeeds, and the delivery record is marked "sent".

**Acceptance Scenarios**:

1. **Given** a user has a webhook URL and secret configured, **When** a "webhook" notification event is processed, **Then** an HTTP POST is made to the URL with the full JSON payload and an `X-Webhook-Signature` header containing an HMAC-SHA256 signature.
2. **Given** the webhook endpoint returns a 5xx response, **When** retried up to 3 times with exponential backoff (1s, 4s, 16s), **Then** the delivery eventually succeeds or is marked "failed" after all attempts are exhausted.
3. **Given** the webhook endpoint returns a 4xx response (client error), **When** the dispatcher processes the response, **Then** no retry is attempted and the delivery is immediately marked "failed".

---

### Edge Cases

- What happens when a notification event references a user with no notification preferences for the specified channel? Skip delivery and record as "failed" with reason "no channel configuration".
- How does the system handle a malformed notification event payload? Log the error, discard the message, and do not crash the consumer.
- What if the database is unreachable when writing the delivery record? Log the error; still attempt delivery, retry DB write with backoff.
- What happens if multiple channels are specified for a single notification event? Dispatch to all channels concurrently and record a delivery entry per channel.
- What if the AWS SES sending limit is exceeded? Treat as transient error and retry with backoff.
- What happens when the Telegram bot rate limit is hit? Respect `retry_after` from the Telegram API error and delay accordingly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST consume notification events from the NATS `alerts.notifications.>` subject using a durable JetStream consumer.
- **FR-002**: System MUST route each notification event to the appropriate delivery channel sender based on the `channel` field in the event.
- **FR-003**: System MUST support five delivery channels: email (AWS SES), Telegram, WhatsApp (Twilio), push (Firebase FCM), and webhook.
- **FR-004**: System MUST deliver notifications within 30 seconds of receiving the dispatch event.
- **FR-005**: System MUST retry failed deliveries up to 3 times using exponential backoff intervals of 1s, 4s, and 16s.
- **FR-006**: System MUST NOT retry on 4xx client errors from external APIs (excluding 429 rate limit); retry MUST only occur on 5xx or transient network errors.
- **FR-007**: Email MUST be rendered from an HTML template including: property photo, address, price, deal score badge, key features, CTA buttons (View Analysis, View on Portal), open-tracking pixel, and click-tracking redirect links.
- **FR-008**: Email MUST be rendered in the user's preferred language; supported locales determined by available template files.
- **FR-009**: Telegram delivery MUST use `sendPhoto` with a Markdown-formatted caption and an InlineKeyboardMarkup with three buttons: View Analysis, View on Portal, Dismiss.
- **FR-010**: System MUST support Telegram account linking: when a user sends `/start {token}` to the bot, the bot MUST store the user's `telegram_chat_id` in the database.
- **FR-011**: WhatsApp delivery MUST use a Twilio pre-approved message template with variables: property address, price, deal score, and link.
- **FR-012**: Push delivery MUST send a Firebase Cloud Messaging notification with title, body, image URL, and click_action URL.
- **FR-013**: Webhook delivery MUST POST the full notification payload as JSON with an `X-Webhook-Signature` header containing an HMAC-SHA256 signature using the user's webhook secret.
- **FR-014**: System MUST record each delivery attempt in the `alert_history` table with: event ID, rule ID, listing ID, channel, delivery status (sent/failed), error detail, and timestamp.
- **FR-015**: System MUST update delivery status to "opened" or "clicked" when the tracking API receives the corresponding signal (via the API Gateway).
- **FR-016**: System MUST expose a health endpoint for liveness and readiness checks.
- **FR-017**: System MUST expose Prometheus metrics: notifications dispatched per channel, delivery success/failure rate per channel, retry count, delivery latency p50/p95.

### Key Entities

- **NotificationEvent**: The incoming NATS message from the alert engine containing user ID, rule ID, listing details, channel, and deal metadata.
- **DeliveryRecord**: A persisted entry in `alert_history` tracking the dispatch attempt, status, and any error detail.
- **ChannelSender**: An abstraction representing a delivery channel implementation (email, Telegram, WhatsApp, push, webhook).
- **UserChannelProfile**: A user's channel-specific configuration loaded from the database: email address, Telegram chat ID, phone number, FCM token, webhook URL and secret.
- **EmailTemplate**: A localized HTML template parameterized with listing data for email rendering.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of notification events dispatched within 30 seconds of receipt under normal operating conditions.
- **SC-002**: Email renders correctly (images visible, links clickable, layout intact) in Gmail and Outlook without broken formatting.
- **SC-003**: Webhook delivery succeeds on the first retry following a transient 5xx response; give up and mark failed after 3 total attempts.
- **SC-004**: Every dispatched notification produces exactly one delivery record per channel in the database.
- **SC-005**: Delivery success rate exceeds 95% under normal conditions across all channels.
- **SC-006**: System sustains a dispatch throughput of at least 100 notifications per second without backlog growth.
- **SC-007**: Telegram account linking completes within one bot interaction (single `/start` command).

## Assumptions

- The alert engine publishes `NotificationEvent` JSON payloads to `alerts.notifications.{COUNTRY_CODE}` NATS subjects; the dispatcher consumes from `alerts.notifications.>`.
- User channel preferences (email, telegram_chat_id, phone number, FCM token, webhook URL and secret) are stored in the `users` table; additional columns will be added via a new Alembic migration.
- The `alert_history` table exists (migration 013 confirms this); a new migration will add an `event_id` column for deduplication.
- Open and click tracking status updates are applied by the API Gateway when it handles tracking pixel requests and click redirects; the dispatcher only writes the initial delivery record.
- WhatsApp template messages require a Twilio-approved template SID; the template SID is provided via service configuration.
- Firebase FCM stores a registration token per user (not a web push subscription object); the token is stored as a text column.
- Telegram Bot webhook mode or polling is an implementation choice; long-polling is assumed for simplicity.
- Preferred language defaults to "en" if not set; only languages with corresponding template files are supported.
- The API Gateway exposes `/api/v1/alerts/track` for open/click tracking signals; the dispatcher does not implement this endpoint.
