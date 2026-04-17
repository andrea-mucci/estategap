# NATS Event Contracts: Notification Dispatcher

**Direction**: Consumer  
**Stream**: `ALERTS` (existing, created by alert-engine)  
**Subject filter**: `alerts.notifications.>` (wildcard over all country codes)  
**Consumer**: durable pull consumer, name `alert-dispatcher`

---

## Consumed Event: `NotificationEvent`

**Subject pattern**: `alerts.notifications.{COUNTRY_CODE}`  
**Format**: JSON  
**Publisher**: `services/alert-engine`

### Schema

```json
{
  "event_id":     "string (UUID v4)",
  "user_id":      "string (UUID)",
  "rule_id":      "string (UUID)",
  "rule_name":    "string",
  "listing_id":   "string (UUID) | null",
  "country_code": "string (ISO 3166-1 alpha-2, uppercase)",
  "channel":      "email | telegram | whatsapp | push | webhook",
  "webhook_url":  "string (URL) | null",
  "frequency":    "instant | hourly | daily",
  "is_digest":    "boolean",
  "deal_score":   "number (0.0–1.0) | null",
  "deal_tier":    "integer (1–4) | null",
  "listing_summary": {
    "title":    "string",
    "price_eur": "number",
    "area_m2":  "number",
    "bedrooms": "integer | null",
    "city":     "string",
    "image_url": "string (URL) | null"
  } | null,
  "total_matches": "integer | null",
  "listings": [
    {
      "listing_id": "string (UUID)",
      "deal_score": "number",
      "deal_tier":  "integer",
      "title":      "string",
      "price_eur":  "number",
      "area_m2":    "number",
      "bedrooms":   "integer | null",
      "city":       "string",
      "image_url":  "string | null"
    }
  ],
  "triggered_at": "string (RFC3339)"
}
```

### Field Rules

| Field | Presence | Notes |
|-------|----------|-------|
| `event_id` | Always | UUID v4; used for idempotent delivery record insert |
| `listing_id` | Non-digest only | NULL for digest events |
| `listing_summary` | Non-digest only | NULL for digest events |
| `listings` | Digest only | Empty array for instant events |
| `total_matches` | Digest only | Number of matches before top-20 cap |
| `webhook_url` | Channel=webhook only | NULL for all other channels |
| `deal_score` / `deal_tier` | Non-digest only | NULL for digest events (per-listing in `listings`) |

### Consumer Configuration

```
Stream:        ALERTS
Name:          alert-dispatcher
FilterSubject: alerts.notifications.>
DeliverPolicy: DeliverNewPolicy
AckPolicy:     AckExplicit
MaxDeliver:    1
AckWait:       60s
MaxAckPending: 500
```

`MaxDeliver: 1` — the dispatcher owns all retry logic in-process. NATS will not redeliver a message if it times out; the dispatcher acks or nacks immediately after all retry attempts complete.

---

## HTTP Tracking Contract (consumed by API Gateway, not dispatcher)

The dispatcher embeds these URLs in email templates. The API Gateway owns the handler.

```
GET /api/v1/alerts/track?id={history_id}&action=open
GET /api/v1/alerts/track?id={history_id}&action=click&url={base64url_destination}
```

On receipt, the API Gateway executes:
```sql
UPDATE alert_history
SET delivery_status = $action  -- 'opened' or 'clicked'
WHERE id = $history_id
  AND delivery_status IN ('sent', 'delivered', 'opened');
```

---

## Webhook Outbound Contract

**Direction**: Outbound HTTP POST to user-configured URL  
**Body**: `NotificationEvent` JSON (identical schema above)  
**Headers**:

```
Content-Type:       application/json
X-Webhook-Signature: sha256={hex(HMAC-SHA256(webhook_secret, raw_body))}
X-Estategap-Event:  alert.notification
X-Delivery-ID:      {history_id}
```

**Retry policy**:
- Attempt 1: immediate
- Attempt 2: +1s
- Attempt 3: +4s
- Attempt 4: +16s
- No further retries; mark `delivery_status = 'failed'`

**Success**: HTTP 2xx response within 10s  
**No retry**: HTTP 4xx (client error) — mark failed immediately  
**Retry**: HTTP 5xx or network timeout
