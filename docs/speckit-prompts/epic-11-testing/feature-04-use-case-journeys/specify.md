# Feature: Use Case / User Journey Tests

## /specify prompt

```
Build the suite of realistic end-to-end user journey tests that validate business-critical flows by exercising multiple services together. Each journey represents a real scenario an EstateGap user would experience.

## What

Implement 15 user journey tests (UJ-01 through UJ-15) that run against a fully deployed kind cluster. These are the highest-value tests in the suite — they validate that the entire platform works together correctly for real business scenarios.

### The 15 User Journeys

**UJ-01: New User Onboarding**
Sign up with email → verify email (mocked) → complete onboarding tour → reach dashboard.
Validates: registration flow, email sending, session management, onboarding state tracking.

**UJ-02: Find a Tier 1 Deal via Search**
Login as Pro user → navigate to /search → apply filters (country=ES, city=Madrid, tier=1) → results sorted by deal_score descending → click top result → detail page shows: price, estimated value, confidence range, SHAP explanation (top 5 factors), 5 comparable properties.
Validates: search API, filtering, sorting, tier gating, ML scorer integration, SHAP, comparables.

**UJ-03: Create Alert Rule and Receive Notification**
Login → navigate to /alerts → create rule (country=ES, zone=Chamberí, property_type=flat, max_price=600k, min_tier=2, channels=[email, telegram, websocket]) → inject a new listing matching the rule into the pipeline → verify all three channels receive the alert within 30 seconds.
Validates: alert rule creation, rule matching, zone intersection, multi-channel dispatch, end-to-end alert flow.

**UJ-04: AI Conversational Search → Auto Alert Creation**
Login → open AI chat → send "I'm looking for a 2-bedroom apartment in Madrid, under 500k, renovated" → assistant asks about preferred zones → user selects chip "Chamberí" → assistant asks about move-in timing → user selects chip "This year" → criteria summary card shown → user confirms → results displayed below chat (at least 5 listings) → alert rule auto-created with same criteria → visible in /alerts.
Validates: AI chat WebSocket, LLM integration, criteria state parsing, chips, summary card, search execution, alert auto-creation.

**UJ-05: Subscription Upgrade Unlocks Features**
Free user logs in → tries to create a 4th alert rule (free limit is 0, but let's test Basic → Pro) → login as Basic user → create 3 alerts successfully → try to create 4th → blocked with "Upgrade to Pro for unlimited alerts" → click upgrade → Stripe Checkout (test mode) with preset card 4242-4242-4242-4242 → payment succeeds → webhook simulated → user tier updated to Pro → retry alert creation succeeds.
Validates: tier enforcement, Stripe integration, webhook processing, real-time tier update, feature unlock.

**UJ-06: Portfolio Tracking with Multi-Currency**
Login as Pro user → navigate to /portfolio → add 3 owned properties (Madrid €450k purchased 2020, London £350k purchased 2022, Paris €600k purchased 2023) → all rendered with ML-estimated current values → total gain/loss calculated correctly → switch currency preference to USD → all values re-display in USD.
Validates: portfolio CRUD, ML scorer on-demand valuation, multi-currency conversion, preference persistence.

**UJ-07: Admin Retrains ML Model Manually**
Login as admin → navigate to /admin → ML Models tab → see current Spain model MAPE 11.2% → click "Retrain Now" → K8s Job created and running → wait for completion (test uses minimal training dataset so completes in 2 minutes) → new model version appears as active → verify new scorer pod uses new model on next scoring operation.
Validates: admin access control, K8s Job creation, MLflow integration, model hot-reload.

**UJ-08: Free Tier Delay**
Free user logs in → searches for listings in Madrid → newest listing (published 10 minutes ago) does NOT appear in results → advance time via NOW_OVERRIDE by 48 hours → same search now shows the listing.
Validates: subscription-based data filtering, time-based gating, NOW_OVERRIDE test capability.

**UJ-09: Multi-Country Search**
Pro user with countries=[ES, IT, FR] → searches without country filter → results include listings from all 3 countries → prices correctly converted to user's preferred currency (EUR) → switch preferred currency to GBP → all prices reconverted.
Validates: multi-country data, currency conversion, user preferences.

**UJ-10: GDPR Data Export & Deletion**
Login → Settings → click "Export my data" → receive JSON file within 30s containing: profile, conversations, alert rules, portfolio, alert history → click "Delete my account" → confirmation dialog → confirm → account immediately anonymized (email set to deleted-<hash>@estategap.test, PII cleared) → user logged out → attempt to login with original credentials fails.
Validates: GDPR data export, account deletion cascade, PII anonymization.

**UJ-11: Price Drop Notification → Engagement**
Existing listing with price €550k → inject price update to €520k (-5.5%) → system detects drop → recalculates tier (Tier 2 → Tier 1) → alert fires to users with matching rules → user receives email with tracking link → click link → redirected to listing detail page → email click tracked in alert_log → CRM status can be set to "contacted".
Validates: price change detection, re-scoring on price change, alert engine, email tracking, CRM workflow.

**UJ-12: Scraping Failure Recovery**
All proxies configured to return 403 for Idealista → orchestrator schedules scraping job → spider-worker fails → after 3 retries, job marked failed → admin receives alert notification → admin navigates to /admin → rotates proxy credentials → triggers manual re-scrape → next cycle succeeds → zero listings lost (verify by counting before and after).
Validates: error handling, proxy rotation, admin alerting, data integrity.

**UJ-13: Language Switching Preserves State**
User with active search at /search?country=ES&city=Madrid&min_price=200000&max_price=500000 → language switcher from ES to EN → URL filters preserved → UI text in English → results still match filters.
Validates: i18n, state preservation across locale change.

**UJ-14: WebSocket Reconnection**
User in middle of AI chat, has sent 3 messages and received responses → simulated network disconnect (close WS from server side) → client detects, shows "Reconnecting..." UI → auto-reconnect after 2s → reconnects with same session_id → previous conversation visible → user sends next message → continues correctly.
Validates: WebSocket auto-reconnect, session persistence, client-side reconnection UX.

**UJ-15: Scrape-to-Alert Latency**
New listing published on Idealista (in test fixture: use test spider that triggers on demand) → scraped within 15 minutes (or immediately in test mode) → normalized, enriched, scored within 30 seconds → matching alerts dispatched within 10 seconds → end-to-end latency from publication to user notification: **< 20 minutes** (realistic target); in test mode with accelerated schedules: **< 2 minutes**.
Validates: end-to-end pipeline latency, real-time alert system.

### Test Structure

Each user journey follows the **Given/When/Then** structure:

```
# UJ-02: Find a Tier 1 Deal via Search

## Given
- Fixture data loaded (1,000 listings with 50 Tier 1 deals in Madrid)
- User "test-pro@estategap.test" logged in
- Default country preference: ES

## When
1. Navigate to /search
2. Select filters: country=ES, city=Madrid, tier=1
3. Click top result in list

## Then
- Results page shows ≥ 20 Tier 1 deals
- Results sorted by deal_score descending
- Detail page loads within 2s
- Detail page contains: photo gallery (≥ 1 image), key stats, deal score ≥ 70, confidence range, SHAP chart with 5 features, 5 comparables, mini map
- SHAP values sum approximately to (estimated_price - mean_price)
- Comparables are in Madrid and similar size (±20%)
```

### Test Artifacts

Each journey test produces:
- Pass/fail status
- Duration
- Step-by-step log
- On failure: screenshots (if UI), API request/response logs, pod logs, DB state dump

### Performance Assertions

Each journey has latency assertions:
- UJ-02 (search → detail): total flow < 5s
- UJ-03 (alert creation → notification received): < 30s
- UJ-04 (AI chat → alert created): < 60s
- UJ-07 (manual retrain → model active): < 5 minutes
- UJ-15 (scrape → alert): < 2 minutes (test mode)

Latency regressions (> 20% increase vs baseline) trigger warnings.

## Why

User journey tests validate real business value. A passing unit test suite means nothing if users can't actually use the product. These 15 journeys cover the most important flows that, if broken, would cause customer-impacting incidents. They also serve as living documentation of what the product does.

## Acceptance Criteria

- All 15 user journey tests implemented and passing on kind cluster
- Each test runs in < 5 minutes (total suite < 30 minutes)
- Tests are independent (any test can run alone without dependencies on other tests)
- Failure artifacts (logs, screenshots) auto-collected for debugging
- Tests cover all subscription tiers (free, basic, pro, global, api, admin)
- Tests cover at least 3 countries (ES, IT, FR)
- Tests exercise all major services: api-gateway, ws-server, ai-chat, ml-scorer, alert-engine, pipeline, spider-workers
- Test suite runs nightly against staging and alerts on failures
- Test suite runs in CI for PRs touching critical paths
- All journeys documented in `docs/test-scenarios.md` with the Given/When/Then structure
```
