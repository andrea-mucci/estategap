# Data Model: NATS-to-Kafka Migration (033)

**Phase**: 1 — Design
**Date**: 2026-04-17

This document describes the broker abstraction types, Kafka topic configurations, consumer group assignments, and message envelope format for the migration.

---

## Broker Abstraction — Go (`libs/pkg/broker/`)

### Core Types

```go
// libs/pkg/broker/broker.go

package broker

import "context"

// Message is the canonical event envelope for all Kafka messages.
type Message struct {
    Key     string            // partitioning key (country code, user_id, etc.)
    Value   []byte            // raw message payload (JSON or Protobuf)
    Headers map[string]string // metadata headers (x-original-topic, x-error, etc.)
    Topic   string            // fully-qualified topic name (with prefix)
}

// MessageHandler is the callback invoked per consumed message.
// Returning a non-nil error triggers retry logic in the subscriber.
type MessageHandler func(ctx context.Context, msg Message) error

// Publisher publishes events to a named topic.
type Publisher interface {
    Publish(ctx context.Context, topic string, key string, value []byte) error
    PublishWithHeaders(ctx context.Context, topic string, key string, value []byte, headers map[string]string) error
    Close() error
}

// Subscriber consumes events from one or more topics as a named group.
type Subscriber interface {
    Subscribe(ctx context.Context, topics []string, group string, handler MessageHandler) error
    Close() error
}

// Broker combines Publisher and Subscriber.
type Broker interface {
    Publisher
    Subscriber
}
```

### KafkaBroker (Go)

```go
// libs/pkg/broker/kafka.go

package broker

type KafkaConfig struct {
    Brokers     []string
    TopicPrefix string
    MaxRetries  int    // default: 3
    TLSEnabled  bool
    SASLUser    string
    SASLPass    string
}

type KafkaBroker struct {
    cfg     KafkaConfig
    writers map[string]*kafka.Writer  // topic → writer
    mu      sync.RWMutex
    dlt     *kafka.Writer             // dead-letter writer
}
```

---

## Broker Abstraction — Python (`libs/common/broker/`)

### Core Types

```python
# libs/common/broker/types.py

from dataclasses import dataclass, field
from typing import Awaitable, Callable

@dataclass
class Message:
    key: str
    value: bytes
    topic: str
    headers: dict[str, str] = field(default_factory=dict)

MessageHandler = Callable[[Message], Awaitable[None]]
```

### KafkaBroker (Python)

```python
# libs/common/broker/kafka_broker.py

from pydantic_settings import BaseSettings

class KafkaConfig(BaseSettings):
    brokers: str = "localhost:9092"       # comma-separated
    topic_prefix: str = "estategap."
    max_retries: int = 3
    tls_enabled: bool = False
    sasl_username: str = ""
    sasl_password: str = ""

    model_config = {"env_prefix": "KAFKA_"}

class KafkaBroker:
    def __init__(self, config: KafkaConfig): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def publish(self, topic: str, key: str, value: bytes) -> None: ...
    async def publish_with_headers(self, topic: str, key: str, value: bytes, headers: dict[str, str]) -> None: ...
    async def subscribe(self, topics: list[str], group: str, handler: MessageHandler) -> None: ...
    async def _handle_failure(self, msg, error: Exception, retry_count: int) -> None: ...
```

---

## Kafka Topic Configuration

### Topic Definitions

| Topic | Partitions | Replication | Retention | `cleanup.policy` |
|---|---|---|---|---|
| `estategap.raw-listings` | 10 | 3 | 604800000ms (7d) | delete |
| `estategap.normalized-listings` | 10 | 3 | 604800000ms (7d) | delete |
| `estategap.enriched-listings` | 10 | 3 | 604800000ms (7d) | delete |
| `estategap.scored-listings` | 10 | 3 | 604800000ms (7d) | delete |
| `estategap.price-changes` | 10 | 3 | 604800000ms (7d) | delete |
| `estategap.alerts-triggers` | 5 | 3 | 259200000ms (3d) | delete |
| `estategap.alerts-notifications` | 5 | 3 | 259200000ms (3d) | delete |
| `estategap.scraper-commands` | 5 | 3 | 86400000ms (1d) | delete |
| `estategap.scraper-cycle` | 5 | 3 | 86400000ms (1d) | delete |
| `estategap.dead-letter` | 3 | 3 | 604800000ms (7d) | delete |

### Topic-Init Job Script

```bash
#!/bin/bash
# Idempotent topic provisioning — safe to re-run
BROKER="${KAFKA_BROKERS:-kafka-bootstrap.kafka.svc.cluster.local:9092}"
PREFIX="${KAFKA_TOPIC_PREFIX:-estategap.}"

create_topic() {
  local name=$1 partitions=$2 retention_ms=$3
  kafka-topics.sh --bootstrap-server "$BROKER" \
    --create --if-not-exists \
    --topic "${PREFIX}${name}" \
    --partitions "$partitions" \
    --replication-factor 3 \
    --config "retention.ms=${retention_ms}" \
    --config "cleanup.policy=delete"
}

# Listing topics (10 partitions, 7d)
create_topic raw-listings          10  604800000
create_topic normalized-listings   10  604800000
create_topic enriched-listings     10  604800000
create_topic scored-listings       10  604800000
create_topic price-changes         10  604800000

# Alert topics (5 partitions, 3d)
create_topic alerts-triggers       5   259200000
create_topic alerts-notifications  5   259200000

# Scraper topics (5 partitions, 1d)
create_topic scraper-commands      5   86400000
create_topic scraper-cycle         5   86400000

# Dead-letter (3 partitions, 7d)
create_topic dead-letter           3   604800000
```

---

## Consumer Group Assignments

| Service | Consumer Group | Topics Consumed | Key Pattern |
|---|---|---|---|
| pipeline/normalizer | `estategap.pipeline-normalizer` | `estategap.raw-listings` | country_code |
| pipeline/deduplicator | `estategap.pipeline-deduplicator` | `estategap.normalized-listings` | country_code |
| pipeline/enricher | `estategap.pipeline-enricher` | `estategap.normalized-listings` | country_code |
| pipeline/change-detector | `estategap.pipeline-change-detector` | `estategap.enriched-listings` | country_code |
| ml/scorer | `estategap.ml-scorer` | `estategap.enriched-listings` | country_code |
| alert-engine | `estategap.alert-engine` | `estategap.scored-listings`, `estategap.price-changes` | user_id |
| alert-dispatcher | `estategap.alert-dispatcher` | `estategap.alerts-notifications` | user_id |
| ws-server | `estategap.ws-server` | `estategap.alerts-notifications` | user_id |
| spider-workers | `estategap.spider-workers` | `estategap.scraper-commands` | country.portal |

---

## Dead-Letter Message Format

Dead-letter messages carry the original key and value unchanged. Metadata is conveyed as Kafka headers:

| Header | Type | Example |
|---|---|---|
| `x-original-topic` | string | `estategap.raw-listings` |
| `x-error` | string | `validation error: missing listing_id` |
| `x-retry-count` | string (int) | `3` |
| `x-timestamp` | string (RFC3339) | `2026-04-17T12:34:56Z` |
| `x-service` | string | `pipeline-normalizer` |

---

## Prometheus Metrics Schema

### Gauge: `estategap_kafka_consumer_lag`

| Label | Values | Description |
|---|---|---|
| `group` | consumer group name | e.g. `estategap.alert-engine` |
| `topic` | fully-qualified topic | e.g. `estategap.scored-listings` |
| `partition` | partition index string | e.g. `"0"`, `"1"` |

**Calculation**: `high_watermark_offset − committed_offset` per (group, topic, partition) tuple, polled every 30 seconds.

### Alerting Rule

```yaml
# prometheus-rules.yaml (Helm template)
- alert: KafkaConsumerLagHigh
  expr: estategap_kafka_consumer_lag > 10000
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "Kafka consumer lag too high"
    description: "Group {{ $labels.group }} is {{ $value }} messages behind on {{ $labels.topic }} partition {{ $labels.partition }}"
```

---

## Configuration Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BROKERS` | `kafka-bootstrap.kafka.svc.cluster.local:9092` | Comma-separated broker list |
| `KAFKA_TOPIC_PREFIX` | `estategap.` | Prepended to all topic short names |
| `KAFKA_TLS_ENABLED` | `false` | Enable TLS transport |
| `KAFKA_SASL_USERNAME` | `` | SASL/PLAIN username (empty = no auth) |
| `KAFKA_SASL_PASSWORD` | `` | SASL/PLAIN password (from Secret) |
| `KAFKA_MAX_RETRIES` | `3` | Message processing retries before DLT |
| `KAFKA_CONSUMER_MAX_BYTES` | `10485760` | Max fetch bytes per partition (10 MB) |
| `KAFKA_PRODUCER_BATCH_SIZE` | `100` | Messages batched per write |
| `KAFKA_COMMIT_INTERVAL` | `1s` | Go consumer commit interval |
