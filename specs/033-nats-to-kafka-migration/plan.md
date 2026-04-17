# Implementation Plan: NATS-to-Kafka Migration

**Branch**: `033-nats-to-kafka-migration` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/033-nats-to-kafka-migration/spec.md`

## Summary

Replace all NATS JetStream publish/subscribe transport with Apache Kafka across 9 Go codebases and 6 Python codebases. The migration introduces a formal `broker.EventBroker` abstraction in both languages, implements Kafka-backed producers/consumers using `segmentio/kafka-go` (Go) and `aiokafka` (Python), provisions 10 Kafka topics via a Helm hook Job, and removes all NATS code, dependencies, and Helm configuration. Message schemas and event semantics are unchanged.

## Technical Context

**Language/Version**: Go 1.23, Python 3.12
**Primary Dependencies**:
- Go new: `github.com/segmentio/kafka-go` (pure Go, no CGO)
- Python new: `aiokafka>=0.10`
- Removed: `github.com/nats-io/nats.go v1.37.0` (all 7 Go modules), `nats-py` (all 5 Python packages)

**Storage**: PostgreSQL 16 + PostGIS 3.4, Redis 7 (unchanged)
**Testing**: Go: `testcontainers-go` Kafka module; Python: `testcontainers` Kafka module; E2E: Bitnami Kafka on kind
**Target Platform**: Kubernetes shared cluster; Kafka at `kafka-bootstrap.kafka.svc.cluster.local:9092`
**Project Type**: Polyglot microservices monorepo
**Performance Goals**: ≥ 100 listings/s end-to-end pipeline throughput (unchanged from pre-migration)
**Constraints**: Zero message loss; at-least-once delivery; zero NATS references post-migration
**Scale/Scope**: 10 Kafka topics, 10 consumer groups, 9 Go modules + 6 Python packages affected

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Polyglot Service Architecture | ✅ PASS | Go services use `segmentio/kafka-go`; Python services use `aiokafka`. Shared code in `libs/`. No cross-service imports. |
| II. Event-Driven Communication | ✅ PASS | Kafka replaces NATS exactly as mandated. Topic names mirror legacy NATS stream names. gRPC unchanged. |
| III. Country-First Data Sovereignty | ✅ PASS | Country code used as partitioning key for all listing events. No schema or DB changes. |
| IV. ML-Powered Intelligence | ✅ PASS | ML scorer consumer migrated; ONNX scoring pipeline unchanged. |
| V. Code Quality Discipline | ✅ PASS | `golangci-lint` and `ruff`/`mypy` enforced. Table-driven and testcontainers-based tests updated for Kafka. |
| VI. Security & Ethical Scraping | ✅ PASS | SASL/TLS configurable via env vars + Kubernetes Secrets. No secrets in code. |
| VII. Brownfield K8s Deployment | ✅ PASS | Helm chart MUST NOT deploy Kafka. No NATS chart dependency. Topic-init Job is idempotent hook. |
| Migration Strategy | ✅ PASS | Feature-branch, incremental, topic naming mirrors NATS stream names. |

**Result**: ALL PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/033-nats-to-kafka-migration/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: decisions, topic/consumer group mapping
├── data-model.md        # Phase 1: broker interfaces, topic configs, metrics schema
├── contracts/
│   └── kafka-topics.md  # Phase 1: per-topic event contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (repository root)

```text
libs/
├── pkg/
│   ├── broker/                    # NEW: Go broker abstraction + Kafka implementation
│   │   ├── broker.go              # Publisher, Subscriber, Broker interfaces + Message type
│   │   ├── kafka.go               # KafkaBroker, KafkaPublisher, KafkaSubscriber
│   │   ├── kafka_lag.go           # Consumer lag Prometheus gauge (background goroutine)
│   │   └── kafka_test.go          # Unit + integration tests (testcontainers)
│   ├── natsutil/                  # DELETE entire package
│   └── config/                    # UPDATE: remove NATS_URL, add KAFKA_* vars
├── common/
│   ├── broker/                    # NEW: Python broker abstraction + Kafka implementation
│   │   ├── __init__.py
│   │   ├── types.py               # Message, MessageHandler
│   │   ├── kafka_broker.py        # KafkaBroker, KafkaConfig (pydantic-settings)
│   │   └── kafka_lag.py           # Consumer lag Prometheus gauge (async task)
│   ├── nats_client.py             # DELETE
│   └── testing/
│       ├── kafka.py               # NEW: KafkaTestContainer helper
│       └── nats.py                # DELETE
└── testhelpers/
    ├── kafka.go                   # NEW: Kafka testcontainer helper for Go
    └── nats.go                    # DELETE

services/
├── api-gateway/
│   ├── internal/natsutil/         # DELETE
│   ├── internal/handler/health.go # UPDATE: remove NATS health check
│   └── go.mod                     # UPDATE: remove nats.go
├── scrape-orchestrator/
│   ├── internal/natsutil/         # DELETE; use libs/pkg/broker directly
│   ├── internal/handler/health.go # UPDATE: remove NATS health check
│   ├── cmd/main.go                # UPDATE: wire KafkaBroker
│   └── go.mod                     # UPDATE: add kafka-go, remove nats.go
├── alert-engine/
│   ├── internal/publisher/        # REPLACE: NatsPublisher → KafkaPublisher
│   ├── internal/worker/consumer.go # REPLACE: NATS consumer → Kafka consumer
│   ├── internal/config/           # UPDATE: NATS_URL → KAFKA_BROKERS
│   └── go.mod                     # UPDATE
├── alert-dispatcher/
│   ├── internal/consumer/         # REPLACE: NATS pull-subscribe → Kafka consumer group
│   ├── internal/config/           # UPDATE
│   └── go.mod                     # UPDATE
├── ws-server/
│   ├── internal/nats/             # DELETE; create internal/kafka/consumer.go
│   ├── internal/metrics/metrics.go # UPDATE: add partition label to lag gauge
│   ├── internal/config/           # UPDATE
│   └── go.mod                     # UPDATE
├── spider-workers/
│   ├── estategap_spiders/consumer.py # REPLACE: NatsClient → KafkaBroker
│   ├── estategap_spiders/settings.py # UPDATE: NATS_URL → KAFKA_BROKERS
│   └── pyproject.toml             # UPDATE: remove nats-py, add aiokafka
├── pipeline/
│   ├── src/pipeline/normalizer/   # REPLACE consumer
│   ├── src/pipeline/deduplicator/ # REPLACE consumer
│   ├── src/pipeline/enricher/     # REPLACE consumer + publisher
│   ├── src/pipeline/change_detector/ # REPLACE consumer + publisher
│   └── pyproject.toml             # UPDATE
└── ml/
    ├── estategap_ml/scorer/       # REPLACE consumer + publisher
    ├── estategap_ml/nats_publisher.py # DELETE; add kafka_publisher.py
    ├── estategap_ml/settings.py   # UPDATE
    └── pyproject.toml             # UPDATE

helm/estategap/
├── Chart.yaml                     # REMOVE nats dependency
├── values.yaml                    # REMOVE nats: block; ADD kafka: block
├── values-staging.yaml            # UPDATE
└── templates/
    ├── nats-streams-job.yaml      # DELETE
    ├── kafka-topics-init-job.yaml # NEW: pre-install,pre-upgrade hook Job
    ├── kafka-configmap.yaml       # NEW: ConfigMap for KAFKA_* env vars
    └── prometheus-rules.yaml      # UPDATE: add KafkaConsumerLagHigh alert rule

tests/
└── e2e/
    └── pyproject.toml             # UPDATE: remove testcontainers[nats], add Kafka support
```

**Structure Decision**: Polyglot monorepo layout (Option 2 variant). The broker abstraction lives in `libs/` (shared) and all services reference it. No new services or top-level directories are added — this is a transport-layer replacement within the existing layout.

## Implementation Phases

### Phase 1: Broker Abstraction Libraries

**Prerequisite for all other phases.**

**Go** (`libs/pkg/broker/`):
1. Define `Message`, `MessageHandler`, `Publisher`, `Subscriber`, `Broker` interfaces in `broker.go`
2. Implement `KafkaBroker` in `kafka.go` using `kafka.NewWriter` (`Balancer: &kafka.Hash{}`) and `kafka.NewReader` (`GroupID`, `MinBytes: 1e3`, `MaxBytes: 10e6`, `CommitInterval: 1s`)
3. Implement dead-letter on 3rd retry failure: write to `estategap.dead-letter` with 4 required headers
4. Implement consumer lag polling in `kafka_lag.go`: background goroutine, 30s interval, `estategap_kafka_consumer_lag{group,topic,partition}` gauge
5. Write integration test using `testcontainers-go` Kafka module
6. Add `github.com/segmentio/kafka-go` to `libs/pkg/go.mod`; delete `libs/pkg/natsutil/`
7. Replace `libs/testhelpers/nats.go` with `libs/testhelpers/kafka.go`

**Python** (`libs/common/broker/`):
1. Create `types.py`: `Message` dataclass, `MessageHandler` type alias
2. Create `kafka_broker.py`: `KafkaConfig` (pydantic-settings, `env_prefix="KAFKA_"`) + `KafkaBroker` class with `start()`, `stop()`, `publish()`, `publish_with_headers()`, `subscribe()`, `_handle_failure()`
3. Create `kafka_lag.py`: async background task, 30s polling, same metric name/labels as Go
4. Write integration test using testcontainers Kafka module
5. Add `aiokafka>=0.10` to `libs/common/pyproject.toml`; delete `nats_client.py`, `testing/nats.py`
6. Add `libs/common/testing/kafka.py` with `KafkaTestContainer` helper class

### Phase 2: Go Service Migration

Migrate Go services in this order (each depends on Phase 1 completion):

1. **scrape-orchestrator**: Delete `internal/natsutil/`; wire `broker.KafkaBroker`; publish to `scraper-commands` with key `"{country}.{portal}"`; update health check; update config + go.mod
2. **alert-engine**: Replace `internal/publisher/` with `KafkaBroker.Publish`; replace `internal/worker/consumer.go` with `broker.Subscribe()` for `scored-listings` + `price-changes`; consumer group `estategap.alert-engine`; update config + go.mod
3. **alert-dispatcher**: Replace `internal/consumer/consumer.go` NATS pull-subscribe with `broker.Subscribe()` for `alerts-notifications`; consumer group `estategap.alert-dispatcher`; preserve worker-pool concurrency; update integration test; update config + go.mod
4. **ws-server**: Delete `internal/nats/`; create `internal/kafka/consumer.go` using `broker.Subscribe()` for `alerts-notifications`; consumer group `estategap.ws-server`; update metrics partition label; update integration test; update config + go.mod
5. **api-gateway**: Remove `internal/natsutil/`; remove NATS health check from `health.go` and `admin.go`; remove NATS from go.mod (api-gateway does not publish/consume events)

### Phase 3: Python Service Migration

Migrate Python services in pipeline order (each depends on Phase 1 completion):

1. **spider-workers**: Replace `consumer.py` NatsClient → KafkaBroker for `scraper-commands` (group `estategap.spider-workers`); replace NATS raw listing publish → `broker.publish("raw-listings", country_code, payload)`; update settings + pyproject.toml + tests
2. **pipeline/normalizer**: Subscribe `raw-listings`, group `estategap.pipeline-normalizer`; publish `normalized-listings`; update config + tests
3. **pipeline/deduplicator**: Subscribe `normalized-listings`, group `estategap.pipeline-deduplicator`; update config + tests
4. **pipeline/enricher**: Subscribe `normalized-listings`, group `estategap.pipeline-enricher`; publish `enriched-listings`; update config + tests
5. **pipeline/change-detector**: Subscribe `enriched-listings`, group `estategap.pipeline-change-detector`; publish `price-changes`; update config + tests
6. **ml/scorer**: Delete `nats_publisher.py`; create `kafka_publisher.py`; subscribe `enriched-listings` (group `estategap.ml-scorer`); publish `scored-listings`; update settings + pyproject.toml + tests

### Phase 4: Helm Migration

1. Delete `templates/nats-streams-job.yaml`
2. Create `templates/kafka-topics-init-job.yaml` (Helm hook `pre-install,pre-upgrade`, `backoffLimit: 5`, idempotent `kafka-topics.sh --if-not-exists`)
3. Create `templates/kafka-configmap.yaml` (ConfigMap `estategap-kafka-config`)
4. Update `templates/prometheus-rules.yaml`: add `KafkaConsumerLagHigh` rule (threshold: 10,000, for: 2m)
5. Update `Chart.yaml`: remove NATS dependency
6. Update `values.yaml`: remove `nats:` block; add `kafka:` block with brokers, topicPrefix, sasl, tls, consumer settings
7. Update `values-staging.yaml`

### Phase 5: Test Adaptation & Cleanup

1. Update `tests/e2e/pyproject.toml`: remove `testcontainers[nats]`; add Kafka test support
2. Run zero-NATS verification: `grep -r "nats" --include="*.go" --include="*.py" --include="*.yaml" --include="*.toml" .` → must return zero source-code results
3. Run linters: `golangci-lint run ./...` across all Go modules; `ruff check . && mypy --strict` across all Python packages
4. Run full test suite in all modules
5. Run conformance test: inject 10,000 messages end-to-end; verify all 10,000 in DB

## Complexity Tracking

No constitution violations. No complexity table required.
