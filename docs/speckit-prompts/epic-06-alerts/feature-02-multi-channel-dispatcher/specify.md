# Feature: Multi-Channel Notification Dispatcher

## /specify prompt

```
Build the Go notification dispatcher that delivers alerts via email, Telegram, WhatsApp, push, and webhook.

## What
A Go service consuming from alerts.notifications NATS stream that routes each alert to the appropriate delivery channel:

1. Email (AWS SES): HTML template with property photo, address, price, deal score badge, key features, CTA buttons. Localized in user's preferred language. Open/click tracking.
2. Telegram Bot: formatted message with photo + inline keyboard buttons (View Analysis, View on Portal, Dismiss). User links account via /start with token.
3. WhatsApp (Twilio): template message with property summary and link.
4. Push (Firebase FCM): web push notification with title, body, image, click URL.
5. Webhook: HTTP POST to user-configured URL with JSON payload + HMAC signature. Retry 3x with exponential backoff.
6. Record delivery status (sent, delivered, failed, opened, clicked) in alert_log table.

## Acceptance Criteria
- Each channel delivers within 30s of dispatch event
- Email renders correctly in Gmail and Outlook
- Telegram message with photo and buttons works
- WhatsApp template message delivers
- Push notification shows on Chrome and Safari
- Webhook retry on 5xx, give up after 3 attempts
- All delivery statuses recorded in DB
```
