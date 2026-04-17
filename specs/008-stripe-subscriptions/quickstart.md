# Quickstart: Stripe Subscription Management

**Branch**: `008-stripe-subscriptions` | **Date**: 2026-04-17

---

## Prerequisites

- Go 1.23 installed
- Running PostgreSQL 16 (apply migration 012 first)
- Running Redis 7
- Stripe test-mode account with Products and Prices configured
- Stripe CLI installed for local webhook forwarding

---

## 1. Configure Environment

Add to `services/api-gateway/.env` (copy from `.env.example`):

```bash
# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...   # from `stripe listen` output
STRIPE_SUCCESS_URL=http://localhost:3000/dashboard?checkout=success
STRIPE_CANCEL_URL=http://localhost:3000/pricing?checkout=cancelled
STRIPE_PORTAL_RETURN_URL=http://localhost:3000/dashboard

# Price IDs (from Stripe Dashboard → Products)
STRIPE_PRICE_BASIC_MONTHLY=price_...
STRIPE_PRICE_BASIC_ANNUAL=price_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_ANNUAL=price_...
STRIPE_PRICE_GLOBAL_MONTHLY=price_...
STRIPE_PRICE_GLOBAL_ANNUAL=price_...
STRIPE_PRICE_API_MONTHLY=price_...
STRIPE_PRICE_API_ANNUAL=price_...
```

---

## 2. Apply Database Migration

```bash
cd services/pipeline
uv run alembic upgrade head
```

Verify:
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'subscriptions';
```

---

## 3. Add stripe-go Dependency

```bash
cd services/api-gateway
go get github.com/stripe/stripe-go/v81
go mod tidy
```

Update `go.work` if needed:
```bash
cd /root/projects/estategap
go work sync
```

---

## 4. Run the Service

```bash
cd services/api-gateway
go run ./cmd/...
```

---

## 5. Forward Stripe Webhooks Locally

```bash
stripe listen --forward-to localhost:8080/v1/webhooks/stripe
```

The CLI prints `STRIPE_WEBHOOK_SECRET=whsec_...` — copy this to your `.env`.

---

## 6. Test the Checkout Flow

```bash
# 1. Register and log in to get a JWT
TOKEN=$(curl -s -X POST http://localhost:8080/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"password123"}' \
  | jq -r '.access_token')

# 2. Create a checkout session
curl -X POST http://localhost:8080/v1/subscriptions/checkout \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"tier":"pro","billing_period":"monthly"}'

# 3. Open the returned checkout_url in a browser
# 4. Use Stripe test card: 4242 4242 4242 4242, any future expiry, any CVC

# 5. Verify subscription was created
curl http://localhost:8080/v1/subscriptions/me \
  -H "Authorization: Bearer $TOKEN"
```

---

## 7. Test Webhook Idempotency

```bash
# Trigger the same event twice via Stripe CLI
stripe events resend evt_1XXXXX
stripe events resend evt_1XXXXX  # second call should be no-op
```

Check Redis:
```bash
redis-cli GET "stripe:event:evt_1XXXXX"
# Should return "1"
```

---

## 8. Test Grace-Period Downgrade

```bash
# Trigger a payment failure event
stripe trigger invoice.payment_failed

# Check pending downgrades sorted set
redis-cli ZRANGE stripe:pending_downgrades 0 -1 WITHSCORES
```

The score is the Unix timestamp at which the downgrade fires (now + 259200 seconds = 3 days).

---

## 9. Test Customer Portal

```bash
curl -X POST http://localhost:8080/v1/subscriptions/portal \
  -H "Authorization: Bearer $TOKEN"

# Open the returned portal_url in a browser
```

---

## Key Stripe Test Cards

| Card Number | Behavior |
|-------------|----------|
| `4242 4242 4242 4242` | Successful payment |
| `4000 0000 0000 0341` | Payment fails after attach |
| `4000 0025 0000 3155` | Requires 3D Secure authentication |

Use expiry `12/34`, CVC `123`, any ZIP.
