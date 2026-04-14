# Feature: Subscriptions & Payments (Stripe)

## /plan prompt

```
Implement Stripe integration with these technical decisions:

## Stack
- github.com/stripe/stripe-go/v81 for all Stripe operations
- Stripe Products and Prices configured in Stripe Dashboard (not via API)
- Price IDs stored in ConfigMap as environment variables

## Webhook Processing
- POST /webhooks/stripe route bypasses JWT auth middleware
- Verify signature using stripe.VerifySignature with STRIPE_WEBHOOK_SECRET
- Store processed event IDs in Redis SET "stripe:processed_events" (TTL 7d) for idempotency
- Event handler pattern: switch on event.Type, extract relevant data, update DB

## Database Updates
- On checkout.session.completed: create subscription row, update user.subscription_tier, set stripe_customer_id
- On customer.subscription.updated: update tier and billing period
- On customer.subscription.deleted: set tier to "free", set subscription status to "cancelled"
- On invoice.payment_failed: set flag, schedule downgrade after 3 days (Redis delayed task)

## Trial Management
- Stripe Checkout session created with trial_period_days=14
- During trial: user has full tier access
- Trial end: Stripe auto-charges. If payment fails → standard payment failure flow.
```
