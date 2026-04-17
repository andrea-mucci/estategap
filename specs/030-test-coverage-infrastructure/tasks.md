# Tasks: Test Coverage Infrastructure

**Input**: Design documents from `specs/030-test-coverage-infrastructure/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: User story label — US1 through US8 (maps to spec.md)

---

## Phase 1: Setup (Shared Directory Structure)

**Purpose**: Create all new directories and stub files so all phases can proceed without blocking on each other.

- [X] T001 Create `libs/testhelpers/` directory with empty `go.mod` stub (`module github.com/estategap/testhelpers`, `go 1.23`)
- [X] T002 [P] Create `libs/common/testing/` directory with empty `__init__.py`
- [X] T003 [P] Create `tests/contracts/frontend/` and `tests/contracts/api/proto_fixtures/` directories with `.gitkeep`
- [X] T004 [P] Create `tests/integration/cross_service/` directory with empty `__init__.py` and `conftest.py` stub
- [X] T005 [P] Add `libs/testhelpers` entry to `go.work` so the workspace resolves the new module

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared test helpers, dependency additions, and configuration standardization that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Go Foundation

- [X] T006 Implement `libs/testhelpers/postgres.go`: `StartPostgres(t *testing.T) *pgxpool.Pool` using `testcontainers-go` with image `postgis/postgis:16-3.4`, registers `t.Cleanup` for container termination
- [X] T007 [P] Implement `libs/testhelpers/redis.go`: `StartRedis(t *testing.T) *redis.Client` using `testcontainers-go` with image `redis:7-alpine`, registers `t.Cleanup`
- [X] T008 [P] Implement `libs/testhelpers/nats.go`: `StartNATS(t *testing.T) *nats.Conn` using `testcontainers-go` with image `nats:2.10-alpine -js`, registers `t.Cleanup`
- [X] T009 [P] Implement `libs/testhelpers/minio.go`: `StartMinIO(t *testing.T) (endpoint, accessKey, secretKey string)` using `testcontainers-go` with image `minio/minio:latest`, registers `t.Cleanup`
- [X] T010 [P] Implement `libs/testhelpers/wait.go`: `WaitForCondition(t *testing.T, fn func() bool, timeout, interval time.Duration)` polling helper using `t.Fatalf` on timeout
- [X] T011 Populate `libs/testhelpers/go.mod` with full dependencies: `testcontainers-go` v0.32+, `pgx/v5`, `go-redis/v9`, `nats.go`, `testify/require`
- [X] T012 [P] Add `github.com/stretchr/testify v1.9.0` to `go.mod` in all 6 Go services + `libs/pkg`: `api-gateway`, `ws-server`, `scrape-orchestrator`, `proxy-manager`, `alert-engine`, `alert-dispatcher`, `libs/pkg`
- [X] T013 [P] Add `github.com/estategap/testhelpers v0.0.0` workspace dependency to `go.mod` in services that have integration tests: `alert-dispatcher`, `alert-engine`, `ws-server`

### Python Foundation

- [X] T014 Implement `libs/common/testing/fixtures.py`: session-scoped pytest fixtures `postgres_container`, `db_pool` (runs Alembic migrations, truncates after each test), `redis_container`, `redis_client` (flushes after each test), `nats_container`, `nats_client`, `minio_container`, `minio_client`
- [X] T015 [P] Implement `libs/common/testing/factories.py`: `ListingFactory`, `ZoneFactory`, `UserFactory`, `AlertRuleFactory` — thin wrappers around Pydantic v2 model constructors with sensible test defaults
- [X] T016 [P] Implement `libs/common/testing/assertions.py`: `assert_listing_processed(pool, listing_id)`, `assert_nats_message_received(client, subject, timeout)`, `assert_deal_score_set(pool, listing_id)`
- [X] T017 Add `testcontainers[postgres,redis]`, `pytest-cov>=5.0`, `pytest-mock>=3.14`, `respx>=0.21` to `[dependency-groups] dev` in `libs/common/pyproject.toml`
- [X] T018 [P] Add `[tool.pytest.ini_options]` block to `libs/common/pyproject.toml`: `testpaths=["tests"]`, `asyncio_mode="auto"`, `addopts="--strict-markers --cov=estategap_common --cov-branch --cov-report=xml --cov-report=term-missing --cov-fail-under=80"`, markers for `unit`, `integration`, `slow`
- [X] T019 [P] Add `[tool.pytest.ini_options]` to `services/pipeline/pyproject.toml` with `--cov=src --cov-fail-under=80` and all three markers; add `pytest-cov>=5.0`, `pytest-mock>=3.14`, `respx>=0.21` to dev deps; expand testcontainers extra to `[postgres,nats]`
- [X] T020 [P] Add `[tool.pytest.ini_options]` to `services/ml/pyproject.toml` with `--cov=src --cov-fail-under=80`; add `pytest-cov>=5.0`, `pytest-mock>=3.14` to dev deps; add `testcontainers[postgres,minio]` to dev deps
- [X] T021 [P] Add `[tool.pytest.ini_options]` to `services/ai-chat/pyproject.toml` with `--cov=src --cov-fail-under=80`; add `pytest-cov>=5.0`, `pytest-mock>=3.14`, `respx>=0.21` to dev deps (testcontainers already present)
- [X] T022 [P] Add `[tool.pytest.ini_options]` to `services/spider-workers/pyproject.toml` with `--cov=src --cov-fail-under=80`; add `pytest-cov>=5.0`, `pytest-mock>=3.14`, `respx>=0.21`, `testcontainers[redis,nats]>=4.4` to dev deps

### golangci-lint

- [X] T023 Update `.golangci.yml`: add `gosec`, `revive`, `ineffassign`, `typecheck` to `linters.enable` section while preserving all existing linters (`errcheck`, `gosimple`, `govet`, `staticcheck`, `unused`, `gofmt`, `goimports`, `misspell`)

**Checkpoint**: Foundation complete. All user story work can now begin.

---

## Phase 3: User Story 1 — Run All Unit Tests with a Single Command (Priority: P1) 🎯 MVP

**Goal**: `make test-unit` runs all Go, Python, and frontend unit tests in < 3 minutes with coverage reports.

**Independent Test**: Run `make test-unit` from repo root. All tests pass. Coverage percentages appear per service. Command exits 0.

### US1 Implementation

- [X] T024 [US1] Create `scripts/check-go-coverage.sh`: reads `coverage.out`, extracts total statement coverage via `go tool cover -func`, compares against `$COVERAGE_THRESHOLD` env var (default `80`), exits 1 with descriptive message if below threshold, exits 0 otherwise
- [X] T025 [US1] Update `Makefile` `test` target and add `test-unit` target: iterates all Go modules running `go test -race -coverprofile=coverage.out -covermode=atomic -tags '!integration' ./...` then calls `scripts/check-go-coverage.sh`; iterates Python services running `uv run pytest -m "not integration and not slow"`; runs `cd frontend && npm run test`
- [X] T026 [US1] Update `Makefile`: add `test-integration` target (runs `go test -race -tags integration` per module, `uv run pytest -m integration` per service, `uv run pytest tests/integration/cross_service/`, `uv run pytest tests/integration/test_pipeline_e2e.py`) and `coverage` target (HTML report generation)
- [X] T027 [P] [US1] Add `msw@^2.6.0` and `@vitest/coverage-v8@^2.1.8` to `frontend/package.json` devDependencies
- [X] T028 [US1] Update `frontend/vitest.config.ts`: add `coverage` block with `provider: 'v8'`, `reporter: ['text','json','lcov']`, `exclude: ['src/test/**','**/*.d.ts','src/types/**','src/i18n/**']`, `thresholds: { lines: 70, functions: 70, branches: 70, statements: 70 }`; add `"test:coverage": "vitest run --coverage"` to `package.json` scripts
- [X] T029 [P] [US1] Create `frontend/src/test/msw.ts`: sets up MSW server with `setupServer()` from `msw/node`, exports `server` instance; update `frontend/src/test/setup.ts` to start/reset/close the MSW server in `beforeAll`/`afterEach`/`afterAll` hooks
- [X] T030 [P] [US1] Create `frontend/src/test/handlers.ts`: MSW request handlers for `GET /api/v1/listings`, `GET /api/v1/zones`, `POST /api/v1/alert-rules` returning static fixture objects matching the API response shape from `services/api-gateway/openapi.yaml`
- [X] T031 [P] [US1] Create `frontend/src/components/listing/ListingCard.test.tsx`: table-driven component tests verifying price display, address rendering, and deal badge for `ListingCard` component; uses `render`, `screen` from `@testing-library/react`
- [X] T032 [P] [US1] Create `frontend/src/components/chat/ChatInput.test.tsx`: tests that `ChatInput` submit handler is called with message text on form submission; uses `userEvent` for interaction
- [X] T033 [P] [US1] Create `frontend/src/hooks/useListings.test.ts`: MSW intercepts `GET /api/v1/listings`, verifies `useListings` hook returns correctly typed data; uses `renderHook` + `QueryClientProvider` wrapper
- [ ] T034 [P] [US1] Verify existing `frontend/src/stores/chatStore.test.ts` and `notificationStore.test.ts` pass with updated vitest config; fix any type errors from strict mode

**Checkpoint**: `make test-unit` runs and exits 0 with coverage output for all 10 services + frontend.

---

## Phase 4: User Story 2 — Integration Tests with Real Dependencies (Priority: P1)

**Goal**: Each service has ≥1 integration test exercising the happy path with real PostgreSQL, Redis, NATS, or MinIO containers.

**Independent Test**: `make test-integration` runs. Containers start and stop cleanly. All happy-path tests pass. No orphaned Docker containers remain after run.

### US2 Implementation — Go Services

- [ ] T035 [US2] Create `services/api-gateway/internal/handler/listings_integration_test.go` with `//go:build integration`: inserts a test listing into a real PostgreSQL container, calls the listing search handler, asserts results returned; uses `testhelpers.StartPostgres(t)`, table-driven subtests with `testify/assert`
- [ ] T036 [P] [US2] Create `services/scrape-orchestrator/internal/scheduler/scheduler_integration_test.go` with `//go:build integration`: publishes a scrape job trigger via real NATS JetStream, asserts job state written to real Redis; uses `testhelpers.StartNATS(t)` and `testhelpers.StartRedis(t)`
- [ ] T037 [P] [US2] Create `services/proxy-manager/internal/grpc/server_integration_test.go` with `//go:build integration`: starts the proxy-manager gRPC server on `127.0.0.1:0`, dials with insecure credentials, calls `GetProxy` RPC, asserts non-empty proxy address returned
- [ ] T038 [P] [US2] Expand `services/alert-engine/internal/matcher/engine_integration_test.go`: add subtest verifying that a listing matching an alert rule publishes exactly one event to NATS `alerts.triggered` subject within 5 seconds; uses `testhelpers.WaitForCondition`
- [ ] T039 [P] [US2] Expand `services/alert-dispatcher/internal/consumer/consumer_integration_test.go`: add subtest verifying that when the sender returns an error, the NATS message is nacked and redelivered; verify `alert_history` record shows `status=failed` with error message
- [X] T040 [P] [US2] Add `github.com/estategap/testhelpers` workspace dependency to `services/api-gateway/go.mod`, `services/scrape-orchestrator/go.mod`, `services/proxy-manager/go.mod`

### US2 Implementation — Python Services

- [ ] T041 [P] [US2] Expand `services/pipeline/tests/integration/test_normalizer_ingest.py` (or create `test_normalizer_happy_path.py`): marks `@pytest.mark.integration`, publishes a raw listing JSON to NATS `raw.listings.es`, asserts normalized listing appears in PostgreSQL `listings` table within 10s; uses shared fixtures from `libs/common/testing/fixtures.py`
- [ ] T042 [P] [US2] Create `services/ml/tests/integration/test_onnx_roundtrip_integration.py` with `@pytest.mark.integration`: loads a test ONNX model from MinIO fixture, runs `onnxruntime.InferenceSession.run()` with sample feature vector, asserts output shape and non-NaN score; uses `minio_client` fixture
- [ ] T043 [P] [US2] Create `services/ai-chat/tests/integration/test_session_integration.py` (expand existing): marks `@pytest.mark.integration`, creates a conversation session backed by real Redis, sends a message, asserts session state persisted; uses `redis_client` fixture
- [ ] T044 [P] [US2] Expand `services/spider-workers/tests/integration/test_consumer.py`: marks `@pytest.mark.integration`, publishes a scrape-result message to NATS, verifies consumer acknowledges it and listing ID added to Redis seen-set; uses `nats_client` and `redis_client` fixtures from `libs/common/testing/fixtures.py`

**Checkpoint**: `make test-integration` exits 0. Each service has ≥1 passing integration test with real containers.

---

## Phase 5: User Story 3 — CI Coverage Enforcement (Priority: P1)

**Goal**: CI rejects PRs that drop coverage below thresholds. Codecov posts PR comments showing coverage diffs.

**Independent Test**: Submit a test PR removing a test. CI fails with coverage message. Codecov comment appears on the PR.

### US3 Implementation

- [X] T045 [US3] Create `.codecov.yml` at repository root with `coverage.status.project.default.target: 80%`, `threshold: 2%`, per-flag overrides for `go` (80%), `python` (80%), `frontend` (70%), `comment.layout: "diff, files"` configuration, and `flags` section mapping each language to its source paths
- [X] T046 [US3] Update `.github/workflows/ci-go.yml`: add `-race -coverprofile=coverage.out -covermode=atomic` to the `go test` command in the `test` job; add a coverage-check step running `scripts/check-go-coverage.sh`; add `codecov/codecov-action@v4` step uploading `coverage.out` with `flags: go-${{ matrix.module }}`
- [X] T047 [P] [US3] Update `.github/workflows/ci-python.yml`: rename existing `test` job to `test-unit`, add `-m "not integration and not slow"` flag; coverage flags are already in `pyproject.toml` `addopts` (configured in Phase 2); add `codecov/codecov-action@v4` step uploading `coverage.xml` with `flags: python-${{ matrix.service }}`
- [X] T048 [P] [US3] Update `.github/workflows/ci-frontend.yml`: add `test` job step `npm run test -- --coverage`; add `codecov/codecov-action@v4` step uploading `frontend/coverage/lcov.info` with `flags: frontend`
- [X] T049 [P] [US3] Update `.github/workflows/ci-proto.yml`: add step `buf breaking --against '.git#branch=main'` after the existing `buf lint` step (buf.yaml already has `breaking.use: [FILE]`)
- [X] T050 [US3] Create `.github/workflows/ci-integration.yml`: triggers on PR to main and push to main; two jobs: `go-integration` (ubuntu-latest, Docker available, runs `go test -race -tags integration ./...` per service matrix) and `python-integration` (ubuntu-latest with Docker, `uv run pytest -m integration` per service matrix); overall `timeout-minutes: 10`

**Checkpoint**: Open a PR, observe CI fails if coverage drops, and Codecov comment appears on the PR.

---

## Phase 6: User Story 4 — Database Migration Verification (Priority: P2)

**Goal**: All Alembic migrations apply, rollback, and are idempotent. Migration failures are caught before merge.

**Independent Test**: Run `uv run pytest services/pipeline/tests/integration/test_migrations.py -v`. All 4 migration test cases pass against a real PostgreSQL container.

### US4 Implementation

- [ ] T051 [US4] Rewrite/expand `services/pipeline/tests/integration/test_migrations.py`: marks entire module `@pytest.mark.integration`; implement `test_upgrade_from_scratch` (empty DB → `alembic upgrade head` via programmatic API → assert all expected tables in `information_schema.tables`); uses `postgres_container` fixture from `libs/common/testing/fixtures.py`
- [ ] T052 [US4] Add `test_downgrade_each_migration` to `services/pipeline/tests/integration/test_migrations.py`: uses `alembic.script.ScriptDirectory` to get all revision IDs; for each revision: `alembic downgrade -1`, assert no error, `alembic upgrade +1`, assert no error; verifies round-trip for every migration
- [ ] T053 [P] [US4] Add `test_idempotency` to `services/pipeline/tests/integration/test_migrations.py`: runs `alembic upgrade head` on already-upgraded DB, asserts no exception and `alembic current` output shows `head` with no pending migrations
- [ ] T054 [P] [US4] Add `test_no_data_loss` to `services/pipeline/tests/integration/test_migrations.py`: seeds a listing row via raw `asyncpg` INSERT at current schema version, applies one additional test migration (if none available, uses a no-op migration), asserts original listing still present with correct fields after upgrade
- [X] T055 [P] [US4] Add `alembic>=1.13` and `psycopg2-binary` to `libs/common/testing` dependencies in `libs/common/pyproject.toml` dev group (needed so migration tests can use the shared postgres fixture with Alembic programmatic API)

**Checkpoint**: `uv run pytest services/pipeline/tests/integration/test_migrations.py -v` — 4 tests pass.

---

## Phase 7: User Story 5 — gRPC Contract Verification (Priority: P2)

**Goal**: Every gRPC service has in-process server tests. `buf breaking` blocks breaking proto changes in CI.

**Independent Test**: `go test -race -tags integration ./...` in ml, proxy-manager; `uv run pytest -m integration services/ml/tests/integration/test_scorer_grpc.py` — all pass. Modify a proto field and verify `buf breaking` fails.

### US7 Implementation

- [ ] T056 [US5] Expand `services/ml/tests/integration/test_scorer_grpc.py` (already exists): add `test_score_listing_happy_path` (in-process `grpc.aio` server on random port, send valid `ScoreListingRequest`, assert `estimated_price > 0`); add `test_score_listing_invalid_args` (missing required fields → assert `INVALID_ARGUMENT` status); add `test_cancellation` (cancel mid-streaming RPC, assert server stops)
- [ ] T057 [P] [US5] Create `services/ai-chat/tests/integration/test_grpc_server.py` with `@pytest.mark.integration`: `test_chat_unary` starts in-process `grpc.aio` server with `ai_chat_pb2_grpc`, sends `ChatRequest` with session ID, asserts non-empty `ChatResponse`; `test_streaming_responses` sends message, collects streamed tokens, asserts > 0 tokens received
- [ ] T058 [P] [US5] Create `services/proxy-manager/internal/grpc/server_integration_test.go` (already listed as T037 — ensure it includes): `TestGetProxy_HappyPath` (insecure dial, `GetProxy` RPC, assert `Address` non-empty), `TestGetProxy_InvalidCountry` (unknown country code → assert gRPC `INVALID_ARGUMENT`), `TestGetProxy_StickySession` (two requests same session ID → same proxy returned)
- [ ] T059 [P] [US5] Create `tests/contracts/api/proto_fixtures/` generation test `libs/testhelpers/proto_contracts_test.go` (build tag `generate_fixtures`): constructs a `ScoreListingRequest`, `ScoreListingResponse`, `ChatMessage` with representative fields, marshals to protobuf binary, writes to `tests/contracts/api/proto_fixtures/*.bin`; subsequent runs compare binary output to committed fixtures and fail if different
- [ ] T060 [P] [US5] Commit initial proto fixture binary files to `tests/contracts/api/proto_fixtures/` (run T059 once to generate them, then commit); add `Makefile` target `update-proto-fixtures` that runs T059 with `-update` flag

**Checkpoint**: gRPC tests pass. Modify `proto/estategap/v1/ml_scoring.proto` to remove a field, run `buf breaking --against '.git#branch=main'` — confirm it fails.

---

## Phase 8: User Story 6 — Cross-Service Integration Verification (Priority: P2)

**Goal**: Key service interaction paths have dedicated end-to-end tests verifying correct communication.

**Independent Test**: `uv run pytest tests/integration/cross_service/ -v` — all 3 implemented paths pass.

### US6 Implementation

- [ ] T061 [US6] Implement `tests/integration/cross_service/conftest.py`: session-scoped fixtures that start PostgreSQL, Redis, NATS, and MinIO containers; function-scoped fixtures that start individual Go/Python services as subprocesses via `subprocess.Popen`; `pytest_configure` hook to register `cross_service` marker; `service_ready(url, timeout)` helper polling HTTP health endpoint
- [ ] T062 [US6] Create `tests/integration/cross_service/test_alert_engine_dispatcher.py` with `@pytest.mark.integration @pytest.mark.cross_service`: starts `alert-engine` and `alert-dispatcher` binaries; inserts matching alert rule and listing in DB; publishes listing to `scored.listings` NATS stream; polls `alert_history` for 10s; asserts one record with `status=dispatched`
- [ ] T063 [P] [US6] Create `tests/integration/cross_service/test_scrape_orchestrator_spiders.py` with `@pytest.mark.integration @pytest.mark.cross_service`: starts `scrape-orchestrator` binary; subscribes to `scrape.jobs` NATS subject; triggers a job via HTTP API; asserts job message published to NATS within 5s with correct portal and region fields
- [ ] T064 [P] [US6] Create `tests/integration/cross_service/test_api_gateway_ml_scorer.py` with `@pytest.mark.integration @pytest.mark.cross_service`: starts `api-gateway` and `ml` scorer service; sends `GET /api/v1/listings/{id}/score` HTTP request to gateway; gateway calls ml-scorer via gRPC; asserts response contains `estimated_price` field > 0

**Checkpoint**: `uv run pytest tests/integration/cross_service/ -v -m "cross_service"` — 3 test files run, services start and communicate.

---

## Phase 9: User Story 7 — OpenAPI Contract Enforcement (Priority: P3)

**Goal**: Frontend TypeScript types are always in sync with OpenAPI spec. API response shapes are codified as fixtures.

**Independent Test**: `npm run generate-api-types` then `git diff --exit-code frontend/src/types/api.ts` exits 0. Add a response field to `openapi.yaml` without regenerating — CI fails.

### US7 Implementation

- [X] T065 [US7] Create `tests/contracts/frontend/GET_listings.json`: representative API response for `GET /api/v1/listings` — array of listing objects with all required fields (`id`, `price`, `currency`, `address`, `deal_score`, `tier`, `country_code`)
- [X] T066 [P] [US7] Create `tests/contracts/frontend/GET_zones.json` and `tests/contracts/frontend/POST_alert_rules.json` with representative response shapes matching `services/api-gateway/openapi.yaml` schema definitions
- [X] T067 [P] [US7] Create `tests/contracts/frontend/README.md`: documents contract update process — when to update fixtures (on OpenAPI schema change), how to regenerate (`make update-contracts`), and policy (fixtures are source-of-truth for MSW handlers)
- [X] T068 [US7] Update `frontend/src/test/handlers.ts` (created in T030) to import and serve contract fixtures from `tests/contracts/frontend/*.json` instead of inline data, ensuring MSW handlers are always contract-fixture-backed
- [ ] T069 [P] [US7] Add step to `.github/workflows/ci-frontend.yml` `lint-typecheck-build` job: run `npm run generate-api-types && git diff --exit-code frontend/src/types/api.ts` — fails CI if generated types differ from committed types, enforcing spec-type sync

**Checkpoint**: Change `openapi.yaml` (add a field). Run `ci-frontend.yml` locally — type-check step fails. Run `npm run generate-api-types` — type-check passes.

---

## Phase 10: User Story 8 — Data Pipeline End-to-End Verification (Priority: P3)

**Goal**: A listing injected at the pipeline entry point reaches the scored DB state within 30s. Batch and recovery scenarios are verified.

**Independent Test**: `uv run pytest tests/integration/test_pipeline_e2e.py::test_single_listing_e2e -v` passes within 45s (30s processing + 15s container startup).

### US8 Implementation

- [ ] T070 [US8] Create `tests/integration/test_pipeline_e2e.py`: session-scoped fixture starting all pipeline service subprocesses (normalizer, deduplicator, enricher, scorer) plus PostgreSQL+PostGIS, NATS, Redis, MinIO containers; seeds MinIO with a test ONNX model for the `es` country
- [ ] T071 [US8] Implement `test_single_listing_e2e` in `tests/integration/test_pipeline_e2e.py`: publishes a raw listing JSON to `raw.listings.es` NATS subject; polls DB every 500ms up to 30s for `deal_score IS NOT NULL AND tier IS NOT NULL AND model_version IS NOT NULL`; asserts all three fields set and `shap_values` non-null for Tier 1 listings
- [ ] T072 [P] [US8] Implement `test_batch_100_listings` in `tests/integration/test_pipeline_e2e.py`: publishes 100 raw listing JSONs (unique IDs, country `es`); polls DB count every 2s up to 60s; asserts all 100 records reach `deal_score IS NOT NULL`; records throughput metric to stdout
- [ ] T073 [P] [US8] Implement `test_recovery_after_enricher_restart` in `tests/integration/test_pipeline_e2e.py`: publishes a listing; kills enricher subprocess after 2s; waits 3s; restarts enricher subprocess; polls DB for 30s; asserts listing eventually reaches fully processed state (NATS JetStream redelivers unacked message)

**Checkpoint**: `uv run pytest tests/integration/test_pipeline_e2e.py -v` — 3 tests pass with output showing processing latency.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Final wiring, documentation, and validation that the entire system works together.

- [ ] T074 Add `make test` as an alias for `make test-unit && make test-integration` in `Makefile`; verify existing `make lint` still works after `.golangci.yml` update (T023)
- [ ] T075 [P] Update `Makefile` `test` (legacy) target to call `test-unit` — preserves backward compatibility for any CI steps that call bare `make test`
- [X] T076 [P] Add `tests/integration/cross_service/__init__.py`, `tests/integration/__init__.py`, `tests/contracts/__init__.py` where missing to ensure pytest collection works correctly
- [X] T077 [P] Create root-level `pyproject.toml` (or `pytest.ini`) for `tests/` directory: `[tool.pytest.ini_options]` with `testpaths=["tests"]`, `asyncio_mode="auto"`, markers `integration`, `cross_service`, `slow` — allows `uv run pytest tests/` from repo root
- [X] T078 [P] Add `coverage.out`, `coverage.xml`, `htmlcov/`, `.coverage`, `frontend/coverage/` to `.gitignore`
- [ ] T079 [P] Run `make test-unit` end-to-end locally and fix any import errors, missing stubs, or type annotation issues surfaced by the new `golangci-lint` linters (gosec, revive) in existing code; document any intentional suppressions with `//nolint:gosec` + reason comment
- [ ] T080 Validate `quickstart.md` accuracy: follow every command in `specs/030-test-coverage-infrastructure/quickstart.md` end-to-end; update any commands that have changed during implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Requires Phase 1 — **blocks all user story phases**
- **Phase 3 (US1 — Unit Tests)**: Requires Phase 2 — `libs/testhelpers` and pytest config must exist
- **Phase 4 (US2 — Integration Tests)**: Requires Phase 2 — shared fixtures must exist
- **Phase 5 (US3 — CI Coverage)**: Requires Phase 3 — `make test-unit` must work before CI wiring
- **Phase 6 (US4 — Migration Tests)**: Requires Phase 2 — `postgres_container` fixture required
- **Phase 7 (US5 — gRPC Contracts)**: Requires Phase 2 — can start independently of US1/US2
- **Phase 8 (US6 — Cross-Service)**: Requires Phase 4 — individual service integration tests must pass first
- **Phase 9 (US7 — OpenAPI Contracts)**: Requires Phase 3 (T030 MSW handlers) — can otherwise proceed independently
- **Phase 10 (US8 — Pipeline E2E)**: Requires Phase 4 (US2 Python integration tests) — services must run in isolation first
- **Phase 11 (Polish)**: Requires all other phases complete

### User Story Dependencies

| Story | Depends On | Can Parallelise With |
|-------|-----------|---------------------|
| US1 (Unit Tests) | Phase 2 | US2, US4, US5 |
| US2 (Integration Tests) | Phase 2 | US1, US4, US5 |
| US3 (CI Coverage) | US1 | US4, US5, US7 |
| US4 (Migration Tests) | Phase 2 | US1, US2, US5 |
| US5 (gRPC Contracts) | Phase 2 | US1, US2, US4 |
| US6 (Cross-Service) | US2 | US3, US4, US5, US7 |
| US7 (OpenAPI Contracts) | US1 (T030) | US3, US4, US5, US6 |
| US8 (Pipeline E2E) | US2 | US3, US5, US6, US7 |

### Within Each Phase

- Phase 2 (T006–T023): T006 first (postgres.go), then T007–T010 in parallel, then T011 (go.mod), T012 in parallel across services, T014 then T015–T016 in parallel (Python)
- Phase 3 (T024–T034): T024 then T025 (Makefile depends on script), T027–T034 fully parallel
- Phase 4 (T035–T044): All can run in parallel after Phase 2 completes
- Phase 5 (T045–T050): T045 first, then T046–T050 in parallel

---

## Parallel Execution Examples

### Parallel Example: Phase 2 (Foundation)

```bash
# After T001–T005 complete:
# Parallel batch 1 — all can start simultaneously:
Task T006: "Implement libs/testhelpers/postgres.go"
Task T007: "Implement libs/testhelpers/redis.go"
Task T008: "Implement libs/testhelpers/nats.go"
Task T009: "Implement libs/testhelpers/minio.go"
Task T010: "Implement libs/testhelpers/wait.go"
Task T014: "Implement libs/common/testing/fixtures.py"  # Independent
Task T023: "Update .golangci.yml"  # Independent

# After T006–T010 complete: Parallel batch 2
Task T011: "Populate libs/testhelpers/go.mod"
Task T012: "Add testify to all 7 Go go.mod files"
Task T018: "Add pytest.ini_options to libs/common"
Task T019: "Add pytest.ini_options to pipeline"
Task T020: "Add pytest.ini_options to ml"
Task T021: "Add pytest.ini_options to ai-chat"
Task T022: "Add pytest.ini_options to spider-workers"
```

### Parallel Example: Phase 3 (US1)

```bash
# T024 (shell script) can start immediately:
Task T024: "Create scripts/check-go-coverage.sh"

# After T024, parallel:
Task T025: "Update Makefile test-unit target"  # depends on T024
Task T027: "Add msw + @vitest/coverage-v8 to package.json"  # independent
Task T029: "Create frontend/src/test/msw.ts"  # independent
Task T030: "Create frontend/src/test/handlers.ts"  # independent

# Parallel once T028 ready:
Task T031: "ListingCard.test.tsx"
Task T032: "ChatInput.test.tsx"
Task T033: "useListings.test.ts"
Task T034: "Fix existing store tests"
```

### Parallel Example: Phase 4 (US2)

```bash
# All T035–T044 are in different services/files — run together:
Task T035: "api-gateway listings_integration_test.go"
Task T036: "scrape-orchestrator scheduler_integration_test.go"
Task T037: "proxy-manager grpc server_integration_test.go"
Task T038: "Expand alert-engine engine_integration_test.go"
Task T039: "Expand alert-dispatcher consumer_integration_test.go"
Task T041: "pipeline normalizer integration test"
Task T042: "ml onnx roundtrip integration test"
Task T043: "ai-chat session integration test"
Task T044: "spider-workers consumer integration test"
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 — all P1)

1. Complete Phase 1: Setup (T001–T005) — ~30 minutes
2. Complete Phase 2: Foundational (T006–T023) — ~2 hours
3. Complete Phase 3: US1 — Unit test command + frontend infra (T024–T034) — ~2 hours
4. **STOP and VALIDATE**: `make test-unit` passes. Frontend coverage thresholds enforced.
5. Complete Phase 4: US2 — Integration tests (T035–T044) — ~3 hours
6. **STOP and VALIDATE**: `make test-integration` passes. All services have happy-path integration tests.
7. Complete Phase 5: US3 — CI wiring (T045–T050) — ~1 hour
8. **STOP and VALIDATE**: CI fails on coverage drop. Codecov comments appear on PR.

### Incremental Delivery (Full Feature)

1. MVP (above) → **Foundation + all P1 stories done**
2. Phase 6 (US4 — Migration Tests) → Migration regressions caught
3. Phase 7 (US5 — gRPC Contracts) → Service boundary regressions caught
4. Phase 8 (US6 — Cross-Service Tests) → Integration regressions caught
5. Phase 9 (US7 — OpenAPI Contracts) → Frontend/API drift caught
6. Phase 10 (US8 — Pipeline E2E) → End-to-end regressions caught
7. Phase 11 (Polish) → Everything wired, documented, validated

### Parallel Team Strategy

With 2 developers after Phase 2 completes:

- **Developer A**: US1 (T024–T034) + US3 (T045–T050) — unit test command + CI wiring
- **Developer B**: US2 (T035–T044) — integration tests across all services

With 3 developers after Phase 2 + Phase 3 complete:

- **Developer A**: US4 (T051–T055) + US5 (T056–T060) — migrations + gRPC contracts
- **Developer B**: US6 (T061–T064) — cross-service tests
- **Developer C**: US7 (T065–T069) + US8 (T070–T073) — contract fixtures + pipeline E2E

---

## Notes

- [P] tasks touch different files with no blocking inter-dependencies — safe to run concurrently
- `//go:build integration` build tag isolates all Go integration tests from `make test-unit`
- `@pytest.mark.integration` marker isolates Python integration tests in the same way
- All container-backed tests use `t.Cleanup` (Go) / session-scoped fixtures (Python) — no orphaned containers
- `scripts/check-go-coverage.sh` is the single source of truth for Go coverage thresholds — update it to change per-service limits
- `--cov-fail-under=80` in each service's `pyproject.toml` is the Python threshold — change per service independently
- Commit proto fixture binaries (T060) only after all gRPC tests pass cleanly
- The `test_recovery_after_enricher_restart` (T073) test depends on NATS JetStream `max_deliver > 1` — verify consumer config before writing the test
