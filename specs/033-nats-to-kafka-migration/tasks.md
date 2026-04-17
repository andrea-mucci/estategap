# Tasks: NATS-to-Kafka Migration

**Input**: Design documents from `specs/033-nats-to-kafka-migration/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-progress tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new directory structures and add new dependencies before any implementation begins.

- [ ] T001 Create `libs/pkg/broker/` directory and empty `broker.go` placeholder
- [ ] T002 [P] Create `libs/common/estategap_common/broker/` directory with `__init__.py`
- [ ] T003 [P] Add `github.com/segmentio/kafka-go v0.4.47` to `libs/pkg/go.mod` and run `go mod tidy`
- [ ] T004 [P] Add `aiokafka>=0.10` to `libs/common/pyproject.toml` dependencies and run `uv lock`
- [ ] T005 [P] Add `github.com/segmentio/kafka-go v0.4.47` to `libs/testhelpers/go.mod` and run `go mod tidy`

---

## Phase 2: Foundational (Broker Abstraction Libraries)

**Purpose**: Go and Python broker interfaces with Kafka implementations. **All user story phases depend on this completing first.**

**⚠️ CRITICAL**: No service migration can begin until this phase is complete.

### Go Broker — `libs/pkg/broker/`

- [ ] T006 Write `libs/pkg/broker/broker.go`: define `Message` struct (`Key string`, `Value []byte`, `Headers map[string]string`, `Topic string`), `MessageHandler` type alias (`func(context.Context, Message) error`), and `Publisher`, `Subscriber`, `Broker` interfaces exactly as specified in `data-model.md`
- [ ] T007 Write `libs/pkg/broker/kafka.go`: implement `KafkaConfig` struct (fields: `Brokers []string`, `TopicPrefix string`, `MaxRetries int`, `TLSEnabled bool`, `SASLUser string`, `SASLPass string`) and `KafkaBroker` struct with lazy `kafka.NewWriter` per topic using `Balancer: &kafka.Hash{}`, `BatchSize: 100`, `BatchTimeout: 10ms`, `Async: false`; implement `Publish` and `PublishWithHeaders` methods
- [ ] T008 Add `Subscribe` method to `KafkaBroker` in `libs/pkg/broker/kafka.go`: create `kafka.NewReader` with `GroupID`, `MinBytes: 1e3`, `MaxBytes: 10e6`, `CommitInterval: time.Second`; implement retry loop up to `MaxRetries` (default 3); on exhaustion call `publishDeadLetter` with headers `x-original-topic`, `x-error`, `x-retry-count`, `x-timestamp`, `x-service`
- [ ] T009 Add `publishDeadLetter` helper and `Close` methods to `KafkaBroker` in `libs/pkg/broker/kafka.go`; add `NewKafkaBroker(cfg KafkaConfig) (*KafkaBroker, error)` constructor with TLS/SASL dialer setup
- [ ] T010 Write `libs/pkg/broker/kafka_lag.go`: define `estategap_kafka_consumer_lag` `prometheus.GaugeVec` with labels `[group, topic, partition]`; implement `StartLagPoller(ctx context.Context, reader *kafka.Reader, group string) ` background goroutine that polls `OffsetFetch` every 30 seconds and updates the gauge
- [ ] T011 Write `libs/pkg/broker/kafka_test.go`: integration test using `testcontainers-go` Kafka module — start container, publish 10 messages, consume all via `Subscribe`, verify dead-letter receives message after simulated handler failure on 3rd retry
- [ ] T012 Write `libs/testhelpers/kafka.go`: export `StartKafkaContainer(t testing.TB) (bootstrapAddr string, cleanup func())` using `testcontainers-go`; mirrors existing `StartNATSContainer` API
- [ ] T013 [P] Delete `libs/pkg/natsutil/natsutil.go` (entire `natsutil` package)
- [ ] T014 [P] Delete `libs/testhelpers/nats.go`

### Python Broker — `libs/common/estategap_common/broker/`

- [ ] T015 Write `libs/common/estategap_common/broker/types.py`: `Message` dataclass with fields `key: str`, `value: bytes`, `topic: str`, `headers: dict[str, str] = field(default_factory=dict)`; `MessageHandler = Callable[[Message], Awaitable[None]]`
- [ ] T016 Write `libs/common/estategap_common/broker/kafka_broker.py`: `KafkaConfig(BaseSettings)` with `brokers: str`, `topic_prefix: str = "estategap."`, `max_retries: int = 3`, `tls_enabled: bool = False`, `sasl_username: str = ""`, `sasl_password: str = ""` and `model_config = {"env_prefix": "KAFKA_"}`; `KafkaBroker.__init__`, `start()`, `stop()`, `publish()`, `publish_with_headers()` methods
- [ ] T017 Add `subscribe()` method and `_handle_failure()` to `KafkaBroker` in `libs/common/estategap_common/broker/kafka_broker.py`: `AIOKafkaConsumer` with `enable_auto_commit=False`, retry loop up to `config.max_retries`, manual `await consumer.commit()` after success, publish to dead-letter topic after exhaustion with all 5 required headers
- [ ] T018 Write `libs/common/estategap_common/broker/kafka_lag.py`: define `estategap_kafka_consumer_lag` Prometheus `Gauge` with labels `[group, topic, partition]`; `async def start_lag_poller(consumer, group: str)` asyncio task polling `end_offsets()` vs `position()` every 30 seconds
- [ ] T019 Write `libs/common/estategap_common/testing/kafka.py`: `KafkaTestContainer` context manager wrapping `testcontainers.kafka.KafkaContainer`; expose `get_bootstrap_server() -> str` method
- [ ] T020 Write integration test `libs/common/tests/test_kafka_broker.py`: start `KafkaTestContainer`, test `publish` + `subscribe` round-trip, verify DLT receives message after 3 handler failures
- [ ] T021 [P] Delete `libs/common/estategap_common/nats_client.py`
- [ ] T022 [P] Delete `libs/common/estategap_common/testing/nats.py`
- [ ] T023 [P] Update `libs/common/estategap_common/broker/__init__.py`: export `KafkaBroker`, `KafkaConfig`, `Message`, `MessageHandler`

**Checkpoint**: Broker abstraction complete — all service migrations can now proceed in parallel.

---

## Phase 3: User Story 1 — End-to-End Listing Pipeline (Priority: P1) 🎯 MVP

**Goal**: Full raw-listing → normalized → enriched → scored pipeline works via Kafka. All pipeline Python services migrated.

**Independent Test**: Publish 1 raw listing event to `estategap.raw-listings`; verify a scored listing record appears in the database within 60 seconds. No NATS infrastructure present.

### spider-workers

- [ ] T024 [P] [US1] Replace `NatsClient` import and usage in `services/spider-workers/estategap_spiders/consumer.py` with `KafkaBroker.subscribe("scraper-commands", "estategap.spider-workers", handler)` from `estategap_common.broker`
- [ ] T025 [P] [US1] Replace NATS publish in `services/spider-workers/estategap_spiders/consumer.py` (raw listing publish) with `await broker.publish("raw-listings", country_code, payload)`
- [ ] T026 [P] [US1] Update `services/spider-workers/estategap_spiders/settings.py`: remove `NATS_URL`, add `KAFKA_BROKERS: str`, `KAFKA_TOPIC_PREFIX: str = "estategap."`, `KAFKA_MAX_RETRIES: int = 3`
- [ ] T027 [US1] Update `services/spider-workers/pyproject.toml`: remove `nats-py`, add `aiokafka>=0.10`; run `uv lock`

### pipeline/normalizer

- [ ] T028 [P] [US1] Replace `NatsClient` consumer in `services/pipeline/src/pipeline/normalizer/consumer.py` with `KafkaBroker.subscribe("raw-listings", "estategap.pipeline-normalizer", handler)`; publish normalized listing via `broker.publish("normalized-listings", country_code, payload)`
- [ ] T029 [P] [US1] Update `services/pipeline/src/pipeline/normalizer/config.py` (or settings): replace `NATS_URL` with `KAFKA_BROKERS`, `KAFKA_TOPIC_PREFIX`, `KAFKA_MAX_RETRIES`

### pipeline/deduplicator

- [ ] T030 [P] [US1] Replace `NatsClient` consumer in `services/pipeline/src/pipeline/deduplicator/consumer.py` with `KafkaBroker.subscribe("normalized-listings", "estategap.pipeline-deduplicator", handler)`
- [ ] T031 [P] [US1] Update `services/pipeline/src/pipeline/deduplicator/config.py`: replace NATS vars with KAFKA vars

### pipeline/enricher

- [ ] T032 [P] [US1] Replace `NatsClient` consumer + NATS publish in `services/pipeline/src/pipeline/enricher/service.py` with `KafkaBroker.subscribe("normalized-listings", "estategap.pipeline-enricher", handler)` and `broker.publish("enriched-listings", country_code, payload)`
- [ ] T033 [P] [US1] Update `services/pipeline/src/pipeline/enricher/config.py`: replace NATS vars with KAFKA vars

### pipeline/change-detector

- [ ] T034 [P] [US1] Replace `NatsClient` consumer + NATS publish in `services/pipeline/src/pipeline/change_detector/consumer.py` with `KafkaBroker.subscribe("enriched-listings", "estategap.pipeline-change-detector", handler)` and `broker.publish("price-changes", country_code, payload)`
- [ ] T035 [P] [US1] Update `services/pipeline/src/pipeline/change_detector/config.py`: replace NATS vars with KAFKA vars

### ml/scorer

- [ ] T036 [P] [US1] Delete `services/ml/estategap_ml/nats_publisher.py`; create `services/ml/estategap_ml/kafka_publisher.py` using `KafkaBroker.publish("scored-listings", country_code, payload)`
- [ ] T037 [P] [US1] Replace `NatsClient` consumer in `services/ml/estategap_ml/scorer/nats_consumer.py` (rename to `kafka_consumer.py`): subscribe to `"enriched-listings"` with group `"estategap.ml-scorer"` via `KafkaBroker.subscribe()`; update all imports in `services/ml/estategap_ml/scorer/__main__.py`
- [ ] T038 [P] [US1] Update `services/ml/estategap_ml/settings.py`: remove `NATS_URL`, add `KAFKA_BROKERS`, `KAFKA_TOPIC_PREFIX`, `KAFKA_MAX_RETRIES`

### Pipeline & ML pyproject.toml + tests

- [ ] T039 [US1] Update `services/pipeline/pyproject.toml`: remove `nats-py`, add `aiokafka>=0.10`; run `uv lock`
- [ ] T040 [US1] Update `services/ml/pyproject.toml`: remove `nats-py`, add `aiokafka>=0.10`; run `uv lock`
- [ ] T041 [P] [US1] Update spider-workers integration tests to use `KafkaTestContainer` from `estategap_common.testing.kafka` instead of NATS test helpers
- [ ] T042 [P] [US1] Update pipeline integration tests (normalizer, deduplicator, enricher, change-detector) to use `KafkaTestContainer`; remove all NATS test fixtures
- [ ] T043 [P] [US1] Update ml/scorer integration tests to use `KafkaTestContainer`; remove NATS test fixtures and `testcontainers[nats]` dep from any test pyproject

**Checkpoint**: Inject a raw listing into `estategap.raw-listings`; verify it flows through normalizer → deduplicator → enricher → change-detector → scorer and lands in the database.

---

## Phase 4: User Story 2 — Real-Time Alerts Reach Users (Priority: P1)

**Goal**: alert-engine, alert-dispatcher, and ws-server migrated to Kafka. Alert notifications flow from scored listings to WebSocket clients.

**Independent Test**: Publish a `ScoredListingEvent` to `estategap.scored-listings` that matches a saved alert rule; verify WebSocket client receives the notification within 10 seconds. No NATS infrastructure present.

### alert-engine

- [ ] T044 [US2] Replace `internal/publisher/publisher.go` in `services/alert-engine/`: remove NATS JetStream publish; implement `KafkaPublisher` wrapping `libs/pkg/broker.KafkaBroker.Publish(ctx, "alerts-notifications", userID, payload)` using key `userID`
- [ ] T045 [US2] Replace NATS consumer in `services/alert-engine/internal/worker/consumer.go`: use `broker.Subscribe(ctx, []string{"scored-listings", "price-changes"}, "estategap.alert-engine", handler)`; remove JetStream pull-subscribe logic
- [ ] T046 [US2] Update `services/alert-engine/internal/config/config.go`: remove `NATS_URL`; add `KAFKA_BROKERS`, `KAFKA_TOPIC_PREFIX`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `KAFKA_TLS_ENABLED`
- [ ] T047 [US2] Update `services/alert-engine/cmd/main.go`: wire `broker.NewKafkaBroker(cfg)` replacing NATS connection setup; start lag poller via `broker.StartLagPoller`
- [ ] T048 [US2] Update `services/alert-engine/go.mod`: remove `github.com/nats-io/nats.go`; add `github.com/segmentio/kafka-go v0.4.47`; run `go mod tidy`

### alert-dispatcher

- [ ] T049 [US2] Replace NATS durable pull-subscribe in `services/alert-dispatcher/internal/consumer/consumer.go` with `broker.Subscribe(ctx, []string{"alerts-notifications"}, "estategap.alert-dispatcher", handler)`; preserve existing worker-pool concurrency model (configurable worker count)
- [ ] T050 [US2] Update `services/alert-dispatcher/internal/config/config.go`: remove NATS fields; add `KAFKA_BROKERS`, `KAFKA_TOPIC_PREFIX`
- [ ] T051 [US2] Update `services/alert-dispatcher/cmd/main.go`: wire `broker.NewKafkaBroker(cfg)`; remove NATS connection setup
- [ ] T052 [US2] Update `services/alert-dispatcher/go.mod`: remove `nats.go`; add `kafka-go`; run `go mod tidy`
- [ ] T053 [US2] Update `services/alert-dispatcher/internal/consumer/consumer_integration_test.go`: replace NATS testcontainer with `testhelpers.StartKafkaContainer(t)`; keep identical assertions on message delivery behavior

### ws-server

- [ ] T054 [US2] Delete `services/ws-server/internal/nats/consumer.go`; create `services/ws-server/internal/kafka/consumer.go` that wraps `broker.Subscribe(ctx, []string{"alerts-notifications"}, "estategap.ws-server", handler)` with the same WebSocket fan-out logic
- [ ] T055 [US2] Update `services/ws-server/internal/metrics/metrics.go`: add `"partition"` label to existing consumer lag gauge; update metric registration
- [ ] T056 [US2] Update `services/ws-server/internal/config/config.go`: remove NATS fields; add `KAFKA_BROKERS`, `KAFKA_TOPIC_PREFIX`
- [ ] T057 [US2] Update `services/ws-server/cmd/main.go`: wire `broker.NewKafkaBroker(cfg)`; start `kafka.StartLagPoller`; remove NATS connection and JetStream setup
- [ ] T058 [US2] Update `services/ws-server/go.mod`: remove `nats.go`; add `kafka-go`; run `go mod tidy`
- [ ] T059 [US2] Update `services/ws-server/tests/integration/ws_test.go`: replace NATS testcontainer with `testhelpers.StartKafkaContainer(t)`; keep identical WebSocket delivery assertions

**Checkpoint**: alert-engine, alert-dispatcher, and ws-server running with Kafka; trigger a scored listing match and verify WebSocket notification arrives.

---

## Phase 5: User Story 3 — Scrape Orchestration Continues Scheduling (Priority: P2)

**Goal**: scrape-orchestrator publishes to Kafka; api-gateway NATS code removed entirely.

**Independent Test**: Start scrape-orchestrator connected to Kafka; verify `estategap.scraper-commands` receives a scrape command on the configured schedule without any NATS infrastructure.

### scrape-orchestrator

- [ ] T060 [US3] Delete `services/scrape-orchestrator/internal/natsutil/client.go`; update `services/scrape-orchestrator/cmd/main.go` to wire `broker.NewKafkaBroker(cfg)` from `libs/pkg/broker`
- [ ] T061 [US3] Replace NATS publish calls throughout scrape-orchestrator (wherever `natsutil.Client.Publish` is called) with `broker.Publish(ctx, "scraper-commands", countryPortalKey, payload)` where `countryPortalKey = country + "." + portal`
- [ ] T062 [US3] Update `services/scrape-orchestrator/internal/handler/health.go`: remove NATS ping; add Kafka admin connectivity check (dial broker with 5s timeout)
- [ ] T063 [US3] Update scrape-orchestrator config (wherever `NATS_URL` is read): replace with `KAFKA_BROKERS`, `KAFKA_TOPIC_PREFIX`
- [ ] T064 [US3] Update `services/scrape-orchestrator/go.mod`: remove `nats.go`; add `kafka-go`; run `go mod tidy`

### api-gateway (NATS removal only — no Kafka added)

- [ ] T065 [P] [US3] Delete `services/api-gateway/internal/natsutil/client.go`
- [ ] T066 [P] [US3] Remove NATS health check from `services/api-gateway/internal/handler/health.go` and any NATS ping logic in `services/api-gateway/internal/repository/admin.go` and `services/api-gateway/internal/handler/admin.go`
- [ ] T067 [P] [US3] Update `services/api-gateway/go.mod`: remove `github.com/nats-io/nats.go` and transitive NATS deps (`nkeys`, `nuid`); run `go mod tidy`

**Checkpoint**: scrape-orchestrator starts, publishes commands to `estategap.scraper-commands`; spider-workers (already on Kafka from Phase 3) receive them.

---

## Phase 6: User Story 4 — Consumer Lag Observable by Operators (Priority: P2)

**Goal**: Prometheus lag metric visible for all consumer services; Prometheus alerting rule fires when lag > 10,000.

**Independent Test**: Pause a consumer process; verify `estategap_kafka_consumer_lag` rises in Prometheus; confirm the `KafkaConsumerLagHigh` alert fires within 2 minutes of lag crossing 10,000.

### Helm Prometheus Rule

- [ ] T068 [US4] Update `helm/estategap/templates/prometheus-rules.yaml`: add `KafkaConsumerLagHigh` alert rule with `expr: estategap_kafka_consumer_lag > 10000`, `for: 2m`, `severity: warning`, annotations referencing `$labels.group`, `$labels.topic`, `$labels.partition`

### Lag Poller Wiring Verification

- [ ] T069 [P] [US4] Verify `StartLagPoller` is wired in `services/alert-engine/cmd/main.go` (called after `broker.NewKafkaBroker` and before serving)
- [ ] T070 [P] [US4] Verify `StartLagPoller` is wired in `services/alert-dispatcher/cmd/main.go`
- [ ] T071 [P] [US4] Verify `StartLagPoller` is wired in `services/ws-server/cmd/main.go`
- [ ] T072 [P] [US4] Verify `start_lag_poller` asyncio task is started in spider-workers `__main__` or equivalent startup code in `services/spider-workers/`
- [ ] T073 [P] [US4] Verify `start_lag_poller` is started in all four pipeline service entrypoints (`services/pipeline/src/pipeline/normalizer/`, `deduplicator/`, `enricher/`, `change_detector/`)
- [ ] T074 [P] [US4] Verify `start_lag_poller` is started in ml-scorer entrypoint `services/ml/estategap_ml/scorer/__main__.py`

**Checkpoint**: Scrape the `/metrics` endpoint of any consumer service; confirm `estategap_kafka_consumer_lag` is present with `group`, `topic`, `partition` labels.

---

## Phase 7: User Story 5 — Zero NATS References (Priority: P3)

**Goal**: Helm chart fully migrated to Kafka; all NATS dependencies removed; zero NATS references in codebase.

**Independent Test**: `grep -r "nats" --include="*.go" --include="*.py" --include="*.yaml" --include="*.toml" . | grep -v "specs/"` returns zero results.

### Helm Migration

- [ ] T075 [US5] Delete `helm/estategap/templates/nats-streams-job.yaml`
- [ ] T076 [US5] Remove NATS chart dependency from `helm/estategap/Chart.yaml` (remove the `nats-io/nats` dependency entry)
- [ ] T077 [US5] Create `helm/estategap/templates/kafka-configmap.yaml`: ConfigMap named `estategap-kafka-config` with keys `KAFKA_BROKERS`, `KAFKA_TOPIC_PREFIX`, `KAFKA_TLS_ENABLED`, `KAFKA_MAX_RETRIES` sourced from `values.yaml` kafka block; add `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD` referencing Kubernetes Secret (only rendered when `kafka.sasl.enabled=true`)
- [ ] T078 [US5] Create `helm/estategap/templates/kafka-topics-init-job.yaml`: Kubernetes Job with annotations `"helm.sh/hook": pre-install,pre-upgrade` and `"helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded`; `backoffLimit: 5`; `restartPolicy: OnFailure`; runs `kafka-topics-init.sh` script (embedded in ConfigMap or as Job command) using bitnami/kafka image; creates all 10 topics with `--if-not-exists` flag
- [ ] T079 [US5] Update `helm/estategap/values.yaml`: remove entire `nats:` block; add `kafka:` block matching structure defined in `data-model.md` (brokers, topicPrefix, sasl.enabled, sasl.username, sasl.secretName, tls.enabled, consumer.maxRetries); update all service env var references from `NATS_URL` to `envFrom: configMapRef: estategap-kafka-config`
- [ ] T080 [US5] Update `helm/estategap/values-staging.yaml`: set `kafka.brokers` to staging cluster broker address; remove any NATS staging overrides

### Dependency & Test Harness Cleanup

- [X] T081 [P] [US5] Update `tests/e2e/pyproject.toml`: remove `testcontainers[nats]`; add bitnami/kafka Helm chart reference in kind test setup scripts (e.g., `tests/e2e/kind/setup.sh` if it exists)
- [ ] T082 [P] [US5] Run `go mod tidy` in every Go module that was updated: `libs/pkg`, `libs/testhelpers`, `services/api-gateway`, `services/alert-engine`, `services/alert-dispatcher`, `services/ws-server`, `services/scrape-orchestrator`; verify NATS packages absent from all `go.sum` files

### Final Verification

- [X] T083 [US5] Run zero-NATS grep: `grep -rn "nats" --include="*.go" --include="*.py" --include="*.yaml" --include="*.toml" . | grep -v "^./specs/"` — output must be empty; fix any remaining references found
- [ ] T084 [P] [US5] Run `golangci-lint run ./...` in each Go module (`libs/pkg`, `libs/testhelpers`, and all five service modules); fix all lint errors
- [ ] T085 [P] [US5] Run `ruff check . && mypy --strict` across `libs/common`, `services/spider-workers`, `services/pipeline`, `services/ml`; fix all errors
- [ ] T086 [P] [US5] Run full Go test suite: `go test ./...` in each Go module; all tests must pass
- [ ] T087 [P] [US5] Run `pytest` in `libs/common`, `services/spider-workers`, `services/pipeline`, `services/ml`; all tests must pass

**Checkpoint**: Zero NATS references. All linters and unit/integration tests pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: E2E validation, conformance test, and CI hygiene.

- [X] T088 Update E2E test fixtures in `tests/e2e/` (or `specs/032-e2e-user-journeys/` test suite): replace NATS container startup with Bitnami Kafka Helm install on kind; update topic names in any hardcoded E2E expectations from NATS stream names to Kafka topic names (`estategap.*`)
- [ ] T089 [P] Write or update conformance test in `tests/e2e/`: inject 10,000 raw listing messages to `estategap.raw-listings`; poll DB until count stabilizes; assert all 10,000 rows present — zero message loss
- [X] T090 [P] Remove `helm repo add nats https://nats-io.github.io/k8s/helm/charts` from all CI scripts, `Makefile` targets, and developer documentation (check `Makefile`, `scripts/`, `.github/`)
- [ ] T091 Run `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml` and fix any template errors introduced by the kafka block additions
- [X] T092 [P] Update `CLAUDE.md` Active Technologies section: replace NATS entries with `github.com/segmentio/kafka-go` (Go) and `aiokafka` (Python); remove `kube-prometheus-stack KEDA (for NATS-based HPA)` note

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all service migration phases**
- **User Stories (Phases 3–7)**: All depend on Phase 2 completion
  - Phase 3 (US1) and Phase 4 (US2) can proceed in parallel after Phase 2
  - Phase 5 (US3) can proceed in parallel with Phases 3 and 4
  - Phase 6 (US4) depends on at least one consumer service being migrated (Phase 3 or 4)
  - Phase 7 (US5) must come last (cleanup + verification requires all migrations done)
- **Polish (Phase 8)**: Depends on all Phases 3–7 completion

### User Story Dependencies

- **US1 (P1)**: Start after Phase 2 — no dependency on US2/US3/US4
- **US2 (P1)**: Start after Phase 2 — no dependency on US1/US3/US4
- **US3 (P2)**: Start after Phase 2 — no dependency on US1/US2/US4
- **US4 (P2)**: The lag metric implementation is inside Phase 2 (broker lib); Phase 6 only wires and validates it — can start after US1 or US2 are done (at least one consumer running)
- **US5 (P3)**: Depends on US1 + US2 + US3 complete (all services migrated before Helm cleanup)

### Within Each Phase

- Tasks marked [P] have no file conflicts with other [P] tasks in the same phase — launch simultaneously
- Non-[P] tasks within a phase must complete in listed order

### Parallel Opportunities

**Phase 2** (Foundational):
- T006–T011 (Go broker) and T015–T023 (Python broker) run in parallel tracks
- T013/T014 (Go cleanup) and T021/T022 (Python cleanup) run concurrently

**Phase 3** (US1):
- T024–T027 (spider-workers), T028–T029 (normalizer), T030–T031 (deduplicator), T032–T033 (enricher), T034–T035 (change-detector), T036–T038 (ml-scorer) are all parallelizable (different files)
- T041, T042, T043 (test updates) all parallelizable

**Phase 4** (US2):
- T044–T048 (alert-engine), T049–T053 (alert-dispatcher), T054–T059 (ws-server) are all parallelizable

**Phase 5** (US3):
- T060–T064 (scrape-orchestrator) and T065–T067 (api-gateway) parallelizable

**Phase 6** (US4):
- T069–T074 (lag poller verification) all parallelizable

**Phase 7** (US5):
- T081–T082 and T084–T087 all parallelizable once T083 (zero-grep) passes

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Track 1 — Go broker (run sequentially within track):
Task T006: "Write libs/pkg/broker/broker.go — interfaces and Message type"
Task T007: "Write libs/pkg/broker/kafka.go — KafkaBroker, Publish, PublishWithHeaders"
Task T008: "Add Subscribe + retry loop + DLT to libs/pkg/broker/kafka.go"
Task T009: "Add NewKafkaBroker constructor + TLS/SASL dialer to libs/pkg/broker/kafka.go"
Task T010: "Write libs/pkg/broker/kafka_lag.go — lag poller goroutine"

# Track 2 — Python broker (run in parallel with Track 1):
Task T015: "Write libs/common/estategap_common/broker/types.py"
Task T016: "Write libs/common/estategap_common/broker/kafka_broker.py — KafkaConfig + publish"
Task T017: "Add subscribe + retry + DLT to kafka_broker.py"
Task T018: "Write libs/common/estategap_common/broker/kafka_lag.py"

# Track 3 — Tests + cleanup (run in parallel with Tracks 1 and 2 once interfaces are stable):
Task T011: "Write libs/pkg/broker/kafka_test.go"
Task T012: "Write libs/testhelpers/kafka.go"
Task T019: "Write libs/common/estategap_common/testing/kafka.py"
Task T020: "Write libs/common/tests/test_kafka_broker.py"
Task T013: "Delete libs/pkg/natsutil/"
Task T014: "Delete libs/testhelpers/nats.go"
Task T021: "Delete libs/common/estategap_common/nats_client.py"
Task T022: "Delete libs/common/estategap_common/testing/nats.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 — Pipeline)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (broker libs) — **critical blocker**
3. Complete Phase 3: US1 (pipeline + ml-scorer + spider-workers)
4. **STOP and VALIDATE**: Inject raw listing → verify scored listing in DB
5. Confirm throughput ≥ 100 listings/s

### Incremental Delivery

1. Setup + Foundational → broker abstraction ready
2. US1 (pipeline) → core product data flow on Kafka ← **deploy here**
3. US2 (alerts) → real-time notifications on Kafka ← **deploy here**
4. US3 (scrape orchestration) → full autonomous scrape loop on Kafka ← **deploy here**
5. US4 (lag monitoring) → observability complete
6. US5 (cleanup) → zero NATS, Helm migrated ← **final deploy**

### Parallel Team Strategy

With two developers:
- **Developer A**: Phase 2 Go broker (T006–T014) → Phase 4 Go alert services (T044–T059) → Phase 5 Go scrape (T060–T067)
- **Developer B**: Phase 2 Python broker (T015–T023) → Phase 3 Python pipeline (T024–T043) → Phase 6 lag validation (T068–T074)
- Both converge on Phase 7 (cleanup) and Phase 8 (E2E/conformance)

---

## Notes

- [P] tasks = different files, no dependency conflicts — launch simultaneously
- [Story] label maps each task to its user story for traceability
- All `go mod tidy` runs should happen immediately after `go.mod` edits
- All `uv lock` runs should happen immediately after `pyproject.toml` edits
- Commit after each completed phase checkpoint
- Do not delete any NATS code until the replacement Kafka code passes its tests in the same service
- The zero-NATS grep (T083) is the gate before Helm cleanup — run it before T075–T080
