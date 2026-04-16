# Feature: Subscriptions & Payments (Stripe)

## /specify prompt

```
Implement Stripe subscription management for the EstateGap platform.

## What
1. POST /api/v1/subscriptions/checkout — Create Stripe Checkout session for a given tier (basic, pro, global, api). Redirect user to Stripe-hosted payment page. Support monthly and annual billing.
2. POST /webhooks/stripe — Handle Stripe webhook events: checkout.session.completed (activate subscription), customer.subscription.updated (tier change), customer.subscription.deleted (cancel), invoice.payment_failed (flag account). Webhook signature verification with stripe-go.
3. GET /api/v1/subscriptions/me — Current subscription status, tier, billing period, next invoice date.
4. POST /api/v1/subscriptions/portal — Create Stripe Customer Portal session for self-service management (upgrade, downgrade, cancel, update payment method).
5. Subscription tier changes immediately update user's tier in the database, affecting rate limits and feature gating across the platform.
6. 14-day free trial for Basic, Pro, and Global tiers.

## Acceptance Criteria
- Full lifecycle: checkout → trial → active → upgrade → downgrade → cancel. All state transitions correct.
- Webhook signature verification rejects tampered payloads
- Idempotent event processing (same event_id processed only once)
- User tier updated within 5 seconds of Stripe event
- Failed payment → user notified, tier downgraded to free after 3 days grace period
```
