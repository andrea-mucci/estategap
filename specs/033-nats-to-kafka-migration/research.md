# Research: NATS-to-Kafka Migration (033)

**Phase**: 0 — Research & Decisions
**Date**: 2026-04-17

---

## 1. Existing NATS Footprint

### Streams → Kafka Topics Mapping

| NATS Stream | NATS Subjects | Kafka Topic | Partitions | Retention |
|---|---|---|---|---|
| `raw-listings` | `listings.raw.>` | `estategap.raw-listings` | 10 | 7d |
| `normalized-listings` | `listings.normalized.>` | `estategap.normalized-listings` | 10 | 7d |
| `enriched-listings` | `listings.enriched.>`, `enriched.listings` | `estategap.enriched-listings` | 10 | 7d |
| `scored-listings` | `listings.scored.>`, `scored.listings` | `estategap.scored-listings` | 10 | 7d |
| `price-changes` | `listings.price-change.>` | `estategap.price-changes` | 10 | 7d |
| `alerts-triggers` | `alerts.triggers.>` | `estategap.alerts-triggers` | 5 | 3d |
| `alerts-notifications` | `alerts.notifications.>` | `estategap.alerts-notifications` | 5 | 3d |
| `scraper-commands` | `scraper.commands.>` | `estategap.scraper-commands` | 5 | 1d |
| `scraper-cycle` | `scraper.cycle.>` | `estategap.scraper-cycle` | 5 | 1d |
| (new) dead-letter | — | `estategap.dead-letter` | 3 | 7d |

**Note**: Constitution §II mandates topic names MUST mirror legacy NATS stream names. The `estategap.` prefix fulfills the feature requirement; short names are unchanged.

### NATS Consumers → Kafka Consumer Groups

| NATS Durable Consumer | Service | Stream | Kafka Consumer Group |
|---|---|---|---|
| `alert-engine-scored` | alert-engine | scored-listings | `estategap.alert-engine` |
| `alert-engine-price` | alert-engine | price-changes | `estategap.alert-engine` |
| `alert-dispatcher` | alert-dispatcher | alerts-notifications | `estategap.alert-dispatcher` |
| `ws-server-notifications` | ws-server | alerts-notifications | `estategap.ws-server` |
| (implicit) normalizer | pipeline/normalizer | raw-listings | `estategap.pipeline-normalizer` |
| (implicit) deduplicator | pipeline/deduplicator | normalized-listings | `estategap.pipeline-deduplicator` |
| (implicit) enricher | pipeline/enricher | normalized-listings | `estategap.pipeline-enricher` |
| (implicit) change-detector | pipeline/change-detector | enriched-listings | `estategap.pipeline-change-detector` |
| (implicit) ml-scorer | ml/scorer | enriched-listings | `estategap.ml-scorer` |
| (implicit) spider-consumer | spider-workers | scraper-commands | `estategap.spider-workers` |

### Partitioning Keys

| Topic | Key | Rationale |
|---|---|---|
| `raw-listings`, `normalized-listings`, `enriched-listings`, `scored-listings`, `price-changes` | `country_code` | Ensures all events for a country land on the same partition, enabling ordered processing per country |
| `alerts-notifications`, `alerts-triggers` | `user_id` | Ensures per-user ordering of notification events |
| `scraper-commands`, `scraper-cycle` | `country_code + "." + portal` | Co-locates commands by portal for ordered dispatch |

---

## 2. Go Implementation Decisions

### Decision: `github.com/segmentio/kafka-go`

- **Decision**: Use `segmentio/kafka-go` (pure Go, no CGO).
- **Rationale**: No native library dependency — works in distroless containers, cross-compiles cleanly. Provides a high-level `kafka.Writer`/`kafka.Reader` API that maps naturally to the publish/subscribe interface. Well-maintained, used in production Go services at scale.
- **Alternatives considered**:
  - `confluent-kafka-go`: CGO dependency, more complex build chain, not compatible with distroless images without extra setup.
  - `IBM/sarama`: Lower-level, more boilerplate, no out-of-the-box consumer group semantics.

### Go Publisher Config

```go
kafka.NewWriter(kafka.WriterConfig{
    Brokers:      brokers,
    Topic:        topic,
    Balancer:     &kafka.Hash{},       // key-based consistent partitioning
    BatchSize:    100,
    BatchTimeout: 10 * time.Millisecond,
    Async:        false,               // synchronous for reliability
})
```

### Go Consumer Config

```go
kafka.NewReader(kafka.ReaderConfig{
    Brokers:        brokers,
    GroupID:        groupID,
    Topic:          topic,
    MinBytes:       1e3,     // 1 KB
    MaxBytes:       10e6,    // 10 MB
    CommitInterval: time.Second,
    StartOffset:    kafka.LastOffset,
})
```

### Dead Letter (Go)

On handler error, retry up to `MaxRetries` (3). After exhaustion:

```go
dltWriter.WriteMessages(ctx, kafka.Message{
    Key:   original.Key,
    Value: original.Value,
    Headers: []kafka.Header{
        {Key: "x-original-topic", Value: []byte(originalTopic)},
        {Key: "x-error", Value: []byte(err.Error())},
        {Key: "x-retry-count", Value: []byte("3")},
        {Key: "x-timestamp", Value: []byte(time.Now().UTC().Format(time.RFC3339))},
    },
})
```

### Consumer Lag Metrics (Go)

```go
kafkaConsumerLag = prometheus.NewGaugeVec(prometheus.GaugeOpts{
    Name: "estategap_kafka_consumer_lag",
    Help: "Kafka consumer group lag per topic partition",
}, []string{"group", "topic", "partition"})
```

Lag = `HighWaterMarkOffset - CommittedOffset`, fetched via `kafka.OffsetFetch` admin call every 30 seconds in a background goroutine.

---

## 3. Python Implementation Decisions

### Decision: `aiokafka`

- **Decision**: Use `aiokafka>=0.10` (asyncio-native Kafka client).
- **Rationale**: Native asyncio integration — no thread pool bridging. Supports both producer and consumer in a single library. Handles consumer group rebalancing, offset management, and SASL/TLS transparently. Manual commit (`enable_auto_commit=False`) gives explicit at-least-once control.
- **Alternatives considered**:
  - `confluent-kafka-python`: C extension, complex build, overkill for service-level use.
  - `kafka-python`: Sync-only, incompatible with asyncio event loop without thread pooling.

### Python Consumer Pattern

```python
consumer = AIOKafkaConsumer(
    *full_topics,
    bootstrap_servers=config.brokers,
    group_id=group,
    enable_auto_commit=False,
    auto_offset_reset="latest",
    max_partition_fetch_bytes=10 * 1024 * 1024,
)
await consumer.start()
try:
    async for msg in consumer:
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                await handler(Message(...))
                await consumer.commit()
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    await self._publish_dead_letter(msg, e, retry_count)
                    await consumer.commit()  # don't replay DLT messages
finally:
    await consumer.stop()
```

### Consumer Lag Metrics (Python)

```python
kafka_consumer_lag = Gauge(
    "estategap_kafka_consumer_lag",
    "Kafka consumer group lag per topic partition",
    ["group", "topic", "partition"],
)
```

Fetched via `AIOKafkaConsumer.end_offsets()` vs `position()` difference, polled every 30s.

---

## 4. Helm & Kubernetes Decisions

### Decision: Topic-Init as Helm Hook Job

- **Decision**: Kubernetes Job with `helm.sh/hook: pre-install,pre-upgrade` annotation, using `bitnami/kafka` image with built-in `kafka-topics.sh`.
- **Rationale**: Runs before any service starts, ensuring topics exist. Idempotent via `--if-not-exists` flag. Hook ensures ordering — topics ready before pod startup.
- **Alternatives considered**:
  - Init containers in each service: duplicates provisioning logic across services.
  - Terraform/separate tooling: out-of-scope for Helm-managed deployment.

### Kafka Config → ConfigMap → Env

```yaml
# values.yaml
kafka:
  brokers: "kafka-bootstrap.kafka.svc.cluster.local:9092"
  topicPrefix: "estategap."
  sasl:
    enabled: false
    username: ""
    password: ""  # reference to Secret
  tls:
    enabled: false
  consumer:
    maxRetries: 3
```

ConfigMap `estategap-kafka-config` propagated to all services as env vars.

### NATS Helm Removal

- Delete `helm/estategap/templates/nats-streams-job.yaml`
- Remove NATS dependency from `Chart.yaml` (`nats-io/nats`)
- Remove `nats:` section from `values.yaml` and `values-staging.yaml`
- Remove KEDA `ScaledObject` resources that referenced NATS metrics

---

## 5. Test Adaptation

### Go Integration Tests

Replace `testhelpers/nats.go` with `testhelpers/kafka.go` using `testcontainers-go` Kafka module:

```go
kafkaContainer, err := kafkatest.Run(ctx, "confluentinc/confluent-local:7.5.0")
// provides bootstrap servers URL for tests
```

### Python Integration Tests

Replace `testcontainers[nats]` with `testcontainers` Kafka module:

```python
from testcontainers.kafka import KafkaContainer
with KafkaContainer() as kafka:
    broker_url = kafka.get_bootstrap_server()
```

### E2E on kind

Use `bitnami/kafka` Helm chart (single-broker, `replicaCount=1`) deployed in the kind cluster under `kafka` namespace. Topic-init Job creates topics before tests run.

---

## 6. Migration Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| NATS at-least-once → Kafka at-least-once semantic drift | Low | Manual commit in Python; `CommitInterval` in Go with retry loop |
| Key partitioning produces hot partitions (e.g., most listings in one country) | Medium | 10 partitions for listing topics; operator can rebalance by increasing partition count |
| Consumer group rebalancing during rolling deploy causes duplicate processing | Low | At-least-once is idempotent in all pipeline stages (upsert, dedup by listing ID) |
| Dead-letter topic fills up silently | Low | Prometheus alert on `estategap.dead-letter` consumer lag |
| Topic-init Job fails on first install due to broker unreachable | Low | `backoffLimit: 5` on Job; Helm hook waits for Job completion before service rollout |
