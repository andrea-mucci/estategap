# Feature Specification: Stripe Subscription Management

**Feature Branch**: `008-stripe-subscriptions`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Implement Stripe subscription management for the EstateGap platform."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subscribe to a Paid Tier (Priority: P1)

A free-tier user wants to upgrade to a paid plan (Basic, Pro, Global, or API) to unlock higher rate limits and additional features. They initiate checkout, are redirected to Stripe's hosted payment page, and upon successful payment gain immediate access to tier benefits — starting with a 14-day free trial for Basic, Pro, and Global tiers.

**Why this priority**: Revenue-generating flow. Without this, no paid subscriptions exist.

**Independent Test**: Can be fully tested by registering a free user, calling the checkout endpoint, completing a test-mode Stripe payment, and verifying the user's tier is upgraded in the database.

**Acceptance Scenarios**:

1. **Given** a free user is authenticated, **When** they request a checkout session for the "pro" tier with "monthly" billing, **Then** they receive a Stripe Checkout URL and are redirected to complete payment.
2. **Given** a user selects Basic, Pro, or Global tier, **When** checkout is created, **Then** a 14-day free trial is applied and the user's tier is immediately set to the chosen tier upon trial start.
3. **Given** a user completes Stripe Checkout, **When** the `checkout.session.completed` webhook fires, **Then** the user's `subscription_tier` is updated in the database within 5 seconds and their Stripe customer ID is stored.
4. **Given** an annual billing cycle is selected, **When** checkout session is created, **Then** the annual price ID is used and the user's billing period reflects a 12-month cycle.

---

### User Story 2 - Manage Subscription via Customer Portal (Priority: P2)

An active subscriber wants to self-serve changes to their subscription — upgrading, downgrading, cancelling, or updating their payment method — without contacting support. They are directed to the Stripe Customer Portal where they complete the action, and the platform reflects the change automatically.

**Why this priority**: Reduces support burden and gives users control over their billing lifecycle.

**Independent Test**: Can be fully tested by creating an active subscriber, calling the portal endpoint, completing a plan change in Stripe's portal, and verifying the webhook updates the platform state correctly.

**Acceptance Scenarios**:

1. **Given** an active subscriber is authenticated, **When** they request a portal session, **Then** they receive a Stripe Customer Portal URL for self-service management.
2. **Given** a subscriber upgrades their tier via the portal, **When** `customer.subscription.updated` fires, **Then** the user's tier is immediately updated in the database.
3. **Given** a subscriber cancels their subscription via the portal, **When** `customer.subscription.deleted` fires, **Then** the user's tier is set to "free" and the subscription status is marked "cancelled".

---

### User Story 3 - View Current Subscription Status (Priority: P2)

A logged-in user wants to see their current subscription details — tier, billing period, trial status, and next invoice date — to understand what they're paying for and when.

**Why this priority**: Essential for user trust and transparency. Users need to understand their billing state.

**Independent Test**: Can be tested by creating users in various subscription states and verifying the GET endpoint returns accurate status for each.

**Acceptance Scenarios**:

1. **Given** a user on a free tier, **When** they call `GET /api/v1/subscriptions/me`, **Then** they receive `{"tier": "free", "status": "free"}` with no billing dates.
2. **Given** a user in trial, **When** they call the endpoint, **Then** the response includes `status: "trialing"`, tier, trial end date, and next invoice date.
3. **Given** an active subscriber, **When** they call the endpoint, **Then** the response includes tier, billing period (monthly/annual), current period end, and next invoice date.

---

### User Story 4 - Handle Failed Payment (Priority: P3)

When a subscriber's payment fails (trial end or renewal), they are notified and given a 3-day grace period to update their payment method before being downgraded to the free tier.

**Why this priority**: Protects against accidental churn while ensuring non-paying users do not retain paid access indefinitely.

**Independent Test**: Can be tested by triggering an `invoice.payment_failed` event and verifying the grace period timer is set, and that after 3 days (simulated) the user's tier is downgraded to free.

**Acceptance Scenarios**:

1. **Given** a subscriber's payment fails, **When** `invoice.payment_failed` fires, **Then** a payment failure flag is set on the user's account.
2. **Given** a payment failure flag is set, **When** 3 days elapse without payment resolution, **Then** the user's tier is automatically downgraded to "free".
3. **Given** a user resolves their payment within the 3-day grace period, **When** a subsequent `invoice.payment_succeeded` fires, **Then** the downgrade is cancelled and the user retains their tier.

---

### Edge Cases

- What happens when the same Stripe webhook event is delivered more than once? The system must process it only once (idempotency by event ID).
- What happens when a webhook arrives with an invalid or missing signature? The request must be rejected with a 400 error and no state changes occur.
- What happens if a user attempts to create a checkout session while already on a paid tier? Redirect to the Customer Portal instead, or return an error with guidance.
- What happens if the Stripe webhook arrives before the checkout session is confirmed in the database? Events must be handled gracefully, potentially with a short retry or idempotency buffer.
- What happens during a tier downgrade when the user is mid-request with elevated rate limits? Rate limit enforcement reads current tier from DB; stale cache entries expire within the cache TTL window.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow authenticated users to initiate a Stripe Checkout session for any paid tier (basic, pro, global, api) with monthly or annual billing.
- **FR-002**: System MUST apply a 14-day free trial for Basic, Pro, and Global tier checkouts; API tier has no trial.
- **FR-003**: System MUST verify Stripe webhook signatures on every inbound webhook request and reject requests with invalid signatures.
- **FR-004**: System MUST process each unique Stripe event ID only once (idempotent event handling).
- **FR-005**: System MUST update the user's subscription tier in the database upon receiving `checkout.session.completed`, `customer.subscription.updated`, and `customer.subscription.deleted` events.
- **FR-006**: System MUST store the Stripe customer ID and subscription ID on the user record upon first successful checkout.
- **FR-007**: System MUST schedule a tier downgrade to "free" 3 days after an `invoice.payment_failed` event if no successful payment follows.
- **FR-008**: System MUST allow authenticated users with an active Stripe subscription to create a Customer Portal session for self-service management.
- **FR-009**: System MUST expose a `GET /api/v1/subscriptions/me` endpoint returning the current subscription tier, status, billing period, and next invoice date.
- **FR-010**: Subscription tier changes MUST be reflected in rate limiting and feature gating within one cache TTL cycle (≤ 60 seconds).
- **FR-011**: The webhook endpoint MUST NOT require JWT authentication.
- **FR-012**: System MUST cancel a pending grace-period downgrade if payment is subsequently recovered before the 3-day window expires.

### Key Entities

- **Subscription**: Represents a user's Stripe subscription. Attributes: user ID, Stripe subscription ID, Stripe customer ID, tier, status (trialing / active / past_due / cancelled / free), billing period (monthly / annual), current period start, current period end, trial end date, payment failure flag, payment failure timestamp.
- **User**: Existing entity — gains `stripe_customer_id`, `stripe_sub_id`, `subscription_tier`, `subscription_ends_at` attributes (already present in schema).
- **Stripe Event Log**: Processed event IDs stored for idempotency (keyed by Stripe event ID, TTL 7 days). Not a database table — managed in Redis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete the checkout flow from tier selection to active subscription in under 3 minutes under normal conditions.
- **SC-002**: Subscription tier changes are reflected in the platform within 5 seconds of the corresponding Stripe webhook event being received.
- **SC-003**: 100% of webhook requests with invalid or tampered signatures are rejected without any database state change.
- **SC-004**: Duplicate Stripe events (same event ID) result in no additional state changes regardless of how many times they are delivered.
- **SC-005**: Users on a failed-payment grace period are downgraded to "free" within 1 minute of the 3-day grace window expiring.
- **SC-006**: The subscription status endpoint returns accurate data for all subscription states (free, trialing, active, past_due, cancelled).

## Assumptions

- Stripe Products and Prices are pre-configured in the Stripe Dashboard; the platform stores only Price IDs as environment variables, not product catalog data.
- The API tier does not receive a free trial; only Basic, Pro, and Global tiers receive 14-day trials.
- Stripe is the sole payment processor; no other payment methods are in scope.
- Email notification of failed payments is delegated to Stripe's built-in dunning emails; the platform only handles tier gating logic.
- A user may only have one active subscription at a time.
- Webhook endpoint is publicly accessible and excluded from JWT authentication middleware.
- Existing `subscription_tier`, `stripe_customer_id`, `stripe_sub_id`, and `subscription_ends_at` columns on the `users` table are already present (confirmed in migration 005).
- A `subscriptions` table separate from `users` may be needed to store full subscription metadata; this will be resolved in the data model phase.
- Rate limits are enforced using the user's current `subscription_tier` read from the database (with Redis cache); cache TTL is ≤ 60 seconds.
