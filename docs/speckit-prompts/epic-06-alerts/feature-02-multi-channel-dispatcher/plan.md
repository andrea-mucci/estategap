# Feature: Multi-Channel Notification Dispatcher

## /plan prompt

```
Implement with these technical decisions:

## Service (services/alert-dispatcher/)
- Go, NATS consumer on alerts.notifications
- Channel router: switch on notification.channel → dispatch to appropriate sender
- Each sender in internal/sender/: email.go, telegram.go, whatsapp.go, push.go, webhook.go
- Common interface: Sender.Send(ctx, notification) → DeliveryResult
- Concurrent dispatch: use errgroup for parallel sends (when user has multiple channels)
- Retry: channel-level retry with exponential backoff (1s, 4s, 16s). Max 3 attempts.

## Email (AWS SES)
- aws-sdk-go-v2/service/ses
- HTML templates in internal/templates/ (Go html/template). One template per language.
- Template data: photo_url, address, price_formatted, deal_score, deal_tier_badge_color, features_list, analysis_url, portal_url
- Open tracking: 1x1 pixel image with tracking URL
- Click tracking: redirect URLs via /api/v1/alerts/track?id=X&action=click&url=Y

## Telegram
- go-telegram-bot-api/telegram-bot-api/v5
- SendPhoto with caption (Markdown formatted) + InlineKeyboardMarkup
- User linking: /start {linking_token} → store chat_id in users.telegram_chat_id

## WhatsApp (Twilio)
- twilio/twilio-go
- Pre-approved message template with variables: {{property_address}}, {{price}}, {{deal_score}}, {{link}}

## Push (FCM)
- firebase.google.com/go/v4/messaging
- Web push subscription stored in users.push_subscription_json
- Notification payload: title, body, image, click_action URL

## Webhook
- Standard net/http POST with JSON body
- HMAC-SHA256 signature in X-Webhook-Signature header using user's webhook_secret
- Retry with tracking in Redis: "webhook:retry:{notification_id}" with attempt count
```
