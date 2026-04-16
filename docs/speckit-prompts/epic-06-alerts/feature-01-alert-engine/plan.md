# Feature: Alert Engine & Rule Matching

## /plan prompt

```
Implement with these technical decisions:

## Service (services/alert-engine/)
- Go, NATS consumer on: scored.listings, price.changes
- Rule cache: load all active rules from DB into memory on startup. Refresh every 60s. Index by country for fast lookup.
- Zone matching: for each rule with zone filters, pre-load zone geometries. Use a Go PostGIS client or precomputed bounding boxes for fast rejection + precise ST_Contains for candidates.
- JSONB filter evaluation: deserialize rule.filters into Go struct. Evaluate each filter field against listing data. Short-circuit on first non-match.
- Dedup: Redis SISMEMBER "alerts:sent:{user_id}" → listing_id. On match → skip. On miss → SADD with TTL 7d.
- Instant dispatch: publish to alerts.notifications NATS stream with: {user_id, listing_id, channel, rule_id, listing_summary}
- Digest buffer: ZADD "alerts:digest:{user_id}:{frequency}" score=deal_score member=listing_id. TTL = frequency interval.
- Digest CronJob: separate goroutine with time.Ticker. ZRANGEBYSCORE (highest first), limit 20 per digest. Delete after sending.

## Performance
- Pre-index rules by country → O(1) country lookup instead of scanning all rules
- Batch NATS consumption: process 100 messages at a time
- Parallel rule evaluation per listing using goroutine pool (size = GOMAXPROCS)
```
