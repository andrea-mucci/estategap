# Feature: Alert Engine & Rule Matching

## /specify prompt

```
Build the Go alert engine that evaluates user rules against scored listings and routes to notification channels.

## What
A Go service that consumes scored listings and price change events from NATS, evaluates them against all active user alert rules, and dispatches matching alerts to notification channels.

1. Rule matching: for each scored listing or price drop event — (a) filter rules by country match, (b) PostGIS zone intersection (listing location within rule's zone polygons), (c) JSONB filter evaluation (property_type, price range, area range, bedrooms, features), (d) deal tier threshold check.
2. Deduplication: don't re-alert the same user for the same listing unless material change (price drop). Track sent pairs in Redis SET.
3. Routing: instant rules → publish to alerts.notifications immediately. Hourly/daily digest rules → buffer in Redis sorted set (score = deal_score, for ranking in digest).
4. Digest compilation: Go CronJob (hourly, daily). Read buffered alerts from Redis per user+frequency. Compile ranked digest grouped by country. Publish as single notification.

## Acceptance Criteria
- Scored listing matching 3 user rules → 3 notification events published
- Non-matching rules correctly skipped (no false positives)
- Dedup prevents re-sending same listing to same user
- Digest compiles correct number of deals, sorted by score, grouped by country
- Processing latency: < 500ms per scored listing (including all rule evaluations)
- Handles 10k active rules without degradation
```
