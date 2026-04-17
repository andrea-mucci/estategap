# Feature: NATS JetStream → Apache Kafka Migration

## /specify prompt

```
Migrate all asynchronous event-driven communication from NATS JetStream to Apache Kafka. The target Kubernetes cluster already has a Kafka cluster running at kafka-bootstrap.kafka.svc.cluster.local:9092. No functional behavior changes — same event semantics, same message schemas, different transport.

## What

1. **Broker abstraction interface** — Create a `broker.EventBroker` interface in both Go and Python that abstracts publish/subscribe operations. The NATS implementation already exists implicitly in the code; extract it into a formal interface, then implement a Kafka version.

2. **Go Kafka implementation** — Using `github.com/segmentio/kafka-go` (pure Go, no CGO):
   - KafkaPublisher: produces messages with key-based partitioning (country code as key for listings, user_id for alerts)
   - KafkaSubscriber: consumes with consumer groups, auto-commit, configurable batch size
   - Connection management: dial with retry, TLS optional, SASL/PLAIN auth optional (configurable)
   - Replace NATS usage in: scrape-orchestrator, alert-engine, alert-dispatcher, ws-server

3. **Python Kafka implementation** — Using `aiokafka` (async-native):
   - AIOKafkaPublisher: async produce with key partitioning
   - AIOKafkaSubscriber: async consume with consumer group, manual commit for at-least-once
   - Replace NATS usage in: spider-workers, pipeline (normalizer, deduplicator, enricher, change-detector), ml-scorer, ai-chat

4. **Kafka topic provisioning** — Kubernetes Job (`kafka-topics-init`) that runs on Helm install/upgrade:
   - Creates all 8 topics with `estategap.` prefix
   - Configures partitions (10 for listing topics, 5 for alert/scraper topics)
   - Sets retention (7 days for listings, 3 days for alerts, 1 day for commands)
   - Idempotent: re-running doesn't fail if topics exist

5. **Shared configuration** — Kafka broker address, auth, TLS, topic prefix all configurable via:
   - Go: environment variables read by config module (KAFKA_BROKERS, KAFKA_SASL_USERNAME, KAFKA_SASL_PASSWORD, KAFKA_TLS_ENABLED, KAFKA_TOPIC_PREFIX)
   - Python: same env vars read by config module
   - Helm: values.yaml kafka section → ConfigMap → env vars

6. **Dead letter topic** — Messages that fail processing after max retries (3) are published to `estategap.dead-letter` with original topic, error message, and timestamp as headers.

7. **Consumer lag monitoring** — Expose Kafka consumer lag as Prometheus metric `estategap_kafka_consumer_lag{group,topic}` in each consuming service. Alerting rule when lag > 10,000 messages.

8. **Remove NATS** — Delete all NATS-related code, configs, Helm templates, and dependencies. Remove nats-io/nats.go and nats-py from go.mod/pyproject.toml.

## Acceptance Criteria

- All 8 Kafka topics created successfully by init Job
- Full pipeline works: raw listing published → scored listing in DB (same as before, just via Kafka)
- Consumer groups correctly balanced across pod replicas
- Dead letter topic receives messages after 3 failed processing attempts
- Consumer lag metric visible in Prometheus
- Zero NATS references remaining in codebase (grep returns nothing)
- All existing unit, integration, and E2E tests pass with Kafka
- Pipeline throughput unchanged (≥ 100 listings/s)
- No message loss: inject 10,000 messages → all 10,000 processed
```
