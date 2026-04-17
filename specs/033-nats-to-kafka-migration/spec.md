# Feature Specification: NATS-to-Kafka Migration

**Feature Branch**: `033-nats-to-kafka-migration`
**Created**: 2026-04-17
**Status**: Draft
**Input**: Migrate all asynchronous event-driven communication from NATS JetStream to Apache Kafka

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End-to-End Listing Pipeline Continues Working (Priority: P1)

A property listing scraped from a portal must travel through the full pipeline — raw ingestion, normalization, deduplication, enrichment, ML scoring, and final storage — with no change to user-visible behavior. Operators should observe no disruption or data loss during and after migration.

**Why this priority**: The listing pipeline is the core product function. Any regression here directly breaks the product for all users.

**Independent Test**: Inject 10,000 raw listing events, verify all 10,000 appear as scored listings in the database within SLA. No NATS infrastructure required.

**Acceptance Scenarios**:

1. **Given** the Kafka broker is running and all topics exist, **When** a spider publishes a raw listing event, **Then** the listing appears as a scored record in the database within 60 seconds.
2. **Given** a malformed message is published, **When** the normalizer fails to process it after 3 retries, **Then** the message is routed to the dead-letter topic and never blocks the pipeline.
3. **Given** 10,000 messages are injected concurrently, **When** the full pipeline completes, **Then** all 10,000 are present in the database — no message loss.

---

### User Story 2 - Real-Time Alerts Reach Users (Priority: P1)

When a property matching a saved alert rule is identified, the user must receive a notification in real-time via WebSocket and/or configured channel (email, Telegram, push). Latency and delivery guarantees must be equivalent to the previous system.

**Why this priority**: Real-time alerts are the primary monetized feature. Silent failures here break user trust directly.

**Independent Test**: Trigger a scored listing that matches a saved rule; verify the user receives a WebSocket notification within 10 seconds.

**Acceptance Scenarios**:

1. **Given** a scored listing matches an alert rule, **When** the alert engine processes it, **Then** a notification event is published and the WebSocket server delivers it to the connected user within 10 seconds.
2. **Given** the notification dispatcher fails to deliver after 3 retries, **Then** the failed notification lands in the dead-letter topic with error metadata.

---

### User Story 3 - Scrape Orchestration Continues Scheduling (Priority: P2)

The scrape orchestrator must continue dispatching crawl commands to spider workers on the configured schedule, with no change to scheduling frequency or target portals.

**Why this priority**: Without scrape commands, the listing pipeline starves. However, a short delay in scheduling is less critical than pipeline or alert regressions.

**Independent Test**: Verify scrape commands appear on the relevant Kafka topic on the configured schedule interval without any NATS infrastructure present.

**Acceptance Scenarios**:

1. **Given** the scheduler fires for a country/portal pair, **When** the orchestrator publishes a scrape command, **Then** the spider-worker service receives and begins processing it within 30 seconds.

---

### User Story 4 - Consumer Lag Observable by Operators (Priority: P2)

Operations teams must be able to monitor consumer group lag per topic in Prometheus and Grafana. An alert fires automatically when lag exceeds 10,000 messages on any topic.

**Why this priority**: Observability is a prerequisite for safe production operation. Without it, lag spikes are invisible until users report missing data.

**Independent Test**: With a consumer deliberately paused, verify `estategap_kafka_consumer_lag` rises in Prometheus and the alerting rule fires above the threshold.

**Acceptance Scenarios**:

1. **Given** a consumer group has fallen behind by > 10,000 messages, **When** Prometheus scrapes the service, **Then** the gauge `estategap_kafka_consumer_lag{group,topic,partition}` reflects the actual lag and the alerting rule fires.

---

### User Story 5 - Zero NATS References Remain (Priority: P3)

After migration is complete, no NATS code, configuration, Helm templates, or dependencies should remain in the repository. The codebase must be fully on Kafka.

**Why this priority**: Clean removal eliminates dead code, reduces attack surface, and avoids confusion for future contributors. It is lower priority than functional correctness.

**Independent Test**: `grep -r "nats" --include="*.go" --include="*.py" --include="*.yaml" --include="*.toml" .` returns zero results (excluding this spec and git history).

**Acceptance Scenarios**:

1. **Given** migration is complete, **When** a full-repository search for "nats" is run, **Then** zero results are returned in source files, Helm templates, and dependency manifests.

---

### Edge Cases

- What happens when the Kafka broker is temporarily unreachable at startup? → Service must retry connection with exponential backoff and surface readiness probe failure until connected.
- How does the system handle a consumer that crashes mid-message? → Manual commit (Python) or `CommitInterval` (Go) ensure the message is re-consumed from the last committed offset — at-least-once delivery.
- What happens if the topic-init Job fails on first Helm install? → The Job must be idempotent; re-running after fixing the broker connection must not duplicate or corrupt topics.
- What if a message exceeds `MaxBytes: 10e6`? → The producer rejects it at publish time with a clear error logged; message goes to dead-letter if published by internal code.
- What if consumer group rebalancing occurs during a batch? → Kafka consumer groups handle rebalancing transparently; in-flight messages not yet committed are retried by the new partition owner.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST replace all NATS JetStream publish/subscribe calls with equivalent Kafka producer/consumer calls, preserving identical message schemas and event semantics.
- **FR-002**: System MUST create a `broker.EventBroker` abstraction in Go (`libs/pkg/broker/`) and Python (`libs/common/broker/`) that decouples services from the transport layer.
- **FR-003**: Go Kafka implementation MUST use `github.com/segmentio/kafka-go` with `Hash` balancer for key-based partitioning (country code for listing events, user ID for alert events).
- **FR-004**: Python Kafka implementation MUST use `aiokafka` with manual commit (`enable_auto_commit=False`) for at-least-once delivery semantics.
- **FR-005**: A Kubernetes Job (`kafka-topics-init`) MUST provision all required topics on Helm install/upgrade; re-running MUST be idempotent.
- **FR-006**: All 9 production topics MUST be created with `estategap.` prefix; topic short names MUST mirror the legacy NATS stream names exactly.
- **FR-007**: Listing topics (`raw-listings`, `normalized-listings`, `enriched-listings`, `scored-listings`, `price-changes`) MUST have 10 partitions; alert and scraper topics MUST have 5 partitions.
- **FR-008**: Retention MUST be: 7 days for listing topics, 3 days for alert topics, 1 day for scraper command topics.
- **FR-009**: Messages that fail processing after 3 retries MUST be published to `estategap.dead-letter` with headers: `x-original-topic`, `x-error`, `x-retry-count`, `x-timestamp`.
- **FR-010**: Each consuming service MUST expose `estategap_kafka_consumer_lag{group,topic,partition}` as a Prometheus gauge, polled every 30 seconds.
- **FR-011**: A Prometheus alerting rule MUST fire when consumer lag exceeds 10,000 messages on any topic for any consumer group.
- **FR-012**: Kafka broker address, SASL credentials, TLS, and topic prefix MUST be configurable via environment variables (`KAFKA_BROKERS`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `KAFKA_TLS_ENABLED`, `KAFKA_TOPIC_PREFIX`).
- **FR-013**: Helm chart MUST NOT deploy a Kafka instance; it MUST reference the platform-managed Kafka via `values.yaml` and propagate config to services via ConfigMap.
- **FR-014**: All NATS-related code, dependencies (`nats.go`, `nats-py`), and Helm templates MUST be removed after migration.
- **FR-015**: All existing Go integration tests that used a NATS testcontainer MUST be rewritten to use a Kafka testcontainer with identical assertions.
- **FR-016**: All existing Python integration tests that used `testcontainers[nats]` MUST be rewritten to use the Kafka testcontainer module with identical assertions.

### Key Entities

- **Kafka Topic**: Named event stream with a partition count, replication factor, and retention policy. Maps 1:1 to a legacy NATS stream.
- **Consumer Group**: Named group of consumers sharing work across partitions. Maps to a legacy NATS durable consumer name.
- **Dead-Letter Topic**: Single catch-all topic (`estategap.dead-letter`) where unprocessable messages land after max retries, with error metadata in headers.
- **Broker Abstraction**: Go interface (`Publisher`, `Subscriber`, `Broker`) and Python base class (`KafkaBroker`) that isolate services from transport details.
- **Topic-Init Job**: Kubernetes Job (Helm hook) responsible for idempotent topic provisioning on every install/upgrade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Full listing pipeline processes ≥ 100 listings per second end-to-end (raw publish → scored in DB), matching pre-migration throughput.
- **SC-002**: Zero message loss: 10,000 injected messages all reach the database; verified by count comparison before and after.
- **SC-003**: Consumer groups correctly rebalance across pod replicas — no partition assignment gaps or duplicate processing detected during a rolling restart.
- **SC-004**: Dead-letter topic receives a test message within 5 seconds of the 3rd processing failure — verifiable via direct topic inspection.
- **SC-005**: Consumer lag metric appears in Prometheus within 60 seconds of a consumer starting; alert fires within 2 minutes of lag crossing 10,000.
- **SC-006**: Zero occurrences of the string "nats" in all `.go`, `.py`, `.yaml`, `.toml`, and `.mod` source files after cleanup.
- **SC-007**: All existing unit, integration, and E2E tests pass with no test-suite changes other than swapping NATS containers for Kafka containers.
- **SC-008**: All 9 production topics + dead-letter topic created successfully by the topic-init Job in a clean cluster (verified by topic listing).

## Assumptions

- The platform-managed Kafka cluster at `kafka-bootstrap.kafka.svc.cluster.local:9092` is reachable from the `estategap-system` namespace during development, staging, and production.
- No SASL/TLS is required for the initial migration; credentials support is implemented but disabled by default (`KAFKA_TLS_ENABLED=false`, no SASL env vars set).
- The migration is a clean cutover — no dual-write period required (per constitution Migration Strategy: feature-branch per migration, no big-bang cutover but no dual-write mandated).
- Replication factor for all topics is 3 (matching platform cluster standard); the topic-init Job configures this automatically.
- The `api-gateway` NATS health check is removed; Kafka connectivity is health-checked via a lightweight admin client ping in each consuming service.
- E2E tests on `kind` use the Bitnami Kafka Helm chart for the test cluster (single-broker, replication factor 1).
- The `ml-trainer` service publishes training completion events but does not consume from Kafka; it retains this behavior unchanged.
