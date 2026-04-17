# Quickstart: 017 — Notification Dispatcher

**Service**: `services/alert-dispatcher/`  
**Language**: Go 1.23  
**Port**: 8081 (health/metrics)

---

## Prerequisites

- Go 1.23+
- NATS server with JetStream (stream `ALERTS` must exist — created by alert-engine)
- PostgreSQL 16 with migration `019_notification_dispatcher.py` applied
- Redis 7
- AWS SES credentials (for email)
- Telegram Bot token
- Twilio account SID + auth token + WhatsApp number
- Firebase service account JSON (for FCM)

---

## Environment Variables

```env
# Core
LOG_LEVEL=info
HEALTH_PORT=8081

# Database
DATABASE_URL=postgres://estategap:secret@localhost:5432/estategap
DATABASE_REPLICA_URL=postgres://estategap:secret@localhost:5432/estategap

# NATS
NATS_URL=nats://localhost:4222
NATS_CONSUMER_NAME=alert-dispatcher
WORKER_POOL_SIZE=16
BATCH_SIZE=50

# Redis
REDIS_URL=redis://localhost:6379

# Email (AWS SES)
AWS_REGION=eu-west-1
AWS_SES_FROM_ADDRESS=alerts@estategap.com
AWS_SES_FROM_NAME=EstateGap Alerts

# Telegram
TELEGRAM_BOT_TOKEN=<bot_token>

# WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=<sid>
TWILIO_AUTH_TOKEN=<token>
TWILIO_WHATSAPP_FROM=+14155238886
TWILIO_WHATSAPP_TEMPLATE_SID=<template_sid>

# Push (Firebase FCM)
FIREBASE_CREDENTIALS_JSON=<service_account_json_string>

# Tracking base URL (for email open/click tracking)
BASE_URL=https://api.estategap.com
```

---

## Run Locally

```bash
cd services/alert-dispatcher

# Apply DB migration (from pipeline service)
cd ../../services/pipeline
uv run alembic upgrade head
cd ../../services/alert-dispatcher

# Run
cp .env.example .env   # fill in credentials
go run ./cmd/main.go
```

---

## Key Source Paths

```
services/alert-dispatcher/
├── cmd/main.go                     # Wires config, NATS, DB, Redis; starts consumer
├── internal/
│   ├── config/config.go            # Viper env config
│   ├── consumer/consumer.go        # JetStream pull consumer loop
│   ├── dispatcher/dispatcher.go    # Routes event → senders via errgroup
│   ├── sender/
│   │   ├── sender.go               # Sender interface + DeliveryResult
│   │   ├── email.go                # AWS SES + html/template rendering
│   │   ├── telegram.go             # Telegram Bot API (sendPhoto + /start handler)
│   │   ├── whatsapp.go             # Twilio WhatsApp messages
│   │   ├── push.go                 # Firebase FCM
│   │   └── webhook.go              # HTTP POST + HMAC-SHA256 + Redis retry
│   ├── repository/
│   │   ├── history.go              # INSERT/UPDATE alert_history
│   │   └── user.go                 # SELECT UserChannelProfile from users
│   ├── model/types.go              # NotificationEvent, UserChannelProfile structs
│   ├── templates/
│   │   ├── email_en.html
│   │   ├── email_es.html
│   │   ├── email_de.html
│   │   ├── email_fr.html
│   │   └── email_pt.html
│   ├── metrics/metrics.go          # Prometheus counters/histograms
│   └── router/router.go            # /healthz, /readyz, /metrics HTTP endpoints
├── go.mod
├── Dockerfile
└── .env.example
```

---

## Health Endpoints

```
GET :8081/healthz   → 200 OK (liveness)
GET :8081/readyz    → 200 OK (NATS + DB + Redis connected)
GET :8081/metrics   → Prometheus text format
```

---

## Run Tests

```bash
cd services/alert-dispatcher
go test ./...

# Integration tests (requires testcontainers / local infra)
go test ./... -tags integration
```

---

## Apply DB Migration

```bash
cd services/pipeline
uv run alembic upgrade head
# Verify:
uv run alembic current
```

---

## Telegram Account Linking Flow

1. Admin generates a `telegram_link_token` UUID for a user and stores it in `users.telegram_link_token`.
2. User sends `/start {token}` to the EstateGap Telegram bot.
3. Bot handler validates the token, stores `chat_id` in `users.telegram_chat_id`, and clears `telegram_link_token`.
4. Bot replies "Account linked successfully!".

Token generation endpoint is exposed via the API Gateway (out of scope for this service).
