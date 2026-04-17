# Contract: Kafka Topics & Message Schemas (033)

**Type**: Event-bus contracts between EstateGap microservices
**Date**: 2026-04-17
**Stability**: Stable — message schemas are unchanged from NATS migration; only transport changes.

---

## Contract Principles

1. **Schema unchanged**: All message payloads (JSON-serialized Pydantic v2 models) are identical to those published over NATS. No schema migration is needed.
2. **Key-based routing**: Each topic uses a mandatory message key for partitioning; consumers MUST NOT rely on partition assignment for ordering across keys.
3. **At-least-once delivery**: All consumers implement retry + dead-letter; producers use synchronous writes (`send_and_wait` / `Async: false`).
4. **Topic naming convention**: `estategap.{stream-name}` — mirrors NATS stream names per constitution §II.

---

## Topic Contracts

### `estategap.raw-listings`

**Producer**: `spider-workers`
**Consumers**: `pipeline/normalizer`
**Key**: `country_code` (e.g., `"FR"`, `"US"`)
**Partitions**: 10 | **Retention**: 7 days

**Payload** (existing `RawListing` Pydantic model, JSON-encoded):
```json
{
  "listing_id": "string (portal-assigned ID)",
  "portal": "string (e.g. rightmove, seloger)",
  "country_code": "string (ISO 3166-1 alpha-2)",
  "url": "string",
  "scraped_at": "datetime (ISO 8601)",
  "raw_data": "object (portal-specific fields)"
}
```

---

### `estategap.normalized-listings`

**Producer**: `pipeline/normalizer`
**Consumers**: `pipeline/deduplicator`, `pipeline/enricher`
**Key**: `country_code`
**Partitions**: 10 | **Retention**: 7 days

**Payload**: existing `NormalizedListing` Pydantic model (unified schema across portals).

---

### `estategap.enriched-listings`

**Producer**: `pipeline/enricher`
**Consumers**: `pipeline/change-detector`, `ml/scorer`
**Key**: `country_code`
**Partitions**: 10 | **Retention**: 7 days

**Payload**: existing `EnrichmentState` Pydantic model (includes POI distances, zone metadata).

---

### `estategap.scored-listings`

**Producer**: `ml/scorer`
**Consumers**: `alert-engine`
**Key**: `country_code`
**Partitions**: 10 | **Retention**: 7 days

**Payload**: existing `ScoredListingEvent` Pydantic model (deal score + SHAP values).

---

### `estategap.price-changes`

**Producer**: `pipeline/change-detector`
**Consumers**: `alert-engine`
**Key**: `country_code`
**Partitions**: 10 | **Retention**: 7 days

**Payload**: existing `PriceChangeEvent` Pydantic model.

---

### `estategap.alerts-triggers`

**Producer**: `alert-engine`
**Consumers**: (future — currently triggers are processed inline by alert-engine)
**Key**: `user_id`
**Partitions**: 5 | **Retention**: 3 days

---

### `estategap.alerts-notifications`

**Producer**: `alert-engine`
**Consumers**: `alert-dispatcher`, `ws-server`
**Key**: `user_id`
**Partitions**: 5 | **Retention**: 3 days

**Payload**: existing alert notification model (user_id, listing_id, rule_id, channel, payload).

---

### `estategap.scraper-commands`

**Producer**: `scrape-orchestrator`
**Consumers**: `spider-workers`
**Key**: `"{country_code}.{portal}"` (e.g., `"FR.seloger"`)
**Partitions**: 5 | **Retention**: 1 day

**Payload**: scrape command with country, portal, target URL pattern, proxy config.

---

### `estategap.scraper-cycle`

**Producer**: `scrape-orchestrator`
**Consumers**: `spider-workers` (cycle acknowledgement)
**Key**: `country_code`
**Partitions**: 5 | **Retention**: 1 day

---

### `estategap.dead-letter`

**Producer**: All consuming services (on 3rd retry failure)
**Consumers**: Ops tooling / manual replay
**Key**: original message key (preserved)
**Partitions**: 3 | **Retention**: 7 days

**Required Headers**:
- `x-original-topic`: source topic full name
- `x-error`: exception message (truncated to 512 chars)
- `x-retry-count`: always `"3"`
- `x-timestamp`: RFC3339 UTC timestamp of final failure
- `x-service`: name of the consuming service that failed

---

## Breaking Change Policy

- Message payload schemas are defined in `libs/common/estategap_common/models/` (Pydantic) and `libs/pkg/models/` (Go structs).
- Any field addition is backward-compatible (consumers ignore unknown fields).
- Field removal or type change requires a versioned schema migration tracked as an ADR in `docs/`.
- Topic partition count increases are backward-compatible; decreases are not allowed.
