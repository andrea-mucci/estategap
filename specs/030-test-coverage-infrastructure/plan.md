# Implementation Plan: Test Coverage Infrastructure

**Branch**: `030-test-coverage-infrastructure` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/030-test-coverage-infrastructure/spec.md`

## Summary

Establish a complete, enforced testing infrastructure across all 10 microservices and the frontend. The work centralizes shared test helpers for Go (`libs/testhelpers/`) and Python (`libs/common/testing/`), standardizes coverage configuration with enforced thresholds (80% Go/Python, 70% frontend), and wires everything into CI with Codecov integration. Testcontainers-based integration tests, gRPC in-process server tests, NATS consumer tests, Alembic migration tests, a pipeline E2E test, and Protobuf/OpenAPI contract enforcement complete the picture.

## Technical Context

**Language/Version**: Go 1.23, Python 3.12, TypeScript 5.6 / Node 22  
**Primary Dependencies**:
- Go: `testcontainers-go` v0.32+, `testify` v1.9+, `golangci-lint`
- Python: `pytest-cov`, `pytest-mock`, `respx`, `testcontainers[postgres,redis,nats,minio]`
- Frontend: `msw` v2.x, `@vitest/coverage-v8`
**Storage**: PostgreSQL 16 + PostGIS 3.4, Redis 7, NATS JetStream, MinIO (all via testcontainers)  
**Testing**: go test + testify, pytest + pytest-asyncio, vitest + React Testing Library  
**Target Platform**: Linux (CI: ubuntu-latest), macOS/Linux (local dev)  
**Project Type**: Polyglot monorepo — test infrastructure layer  
**Performance Goals**: `make test-unit` < 3 minutes; `make test-integration` < 10 minutes  
**Constraints**: Docker required for integration tests; unit tests MUST run without Docker  
**Scale/Scope**: 6 Go services + libs/pkg + libs/testhelpers (new), 4 Python services + libs/common, 1 Next.js frontend

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ Pass | Test helpers live in `libs/` (shared), not in any service. Services remain standalone. |
| II. Event-Driven Communication | ✅ Pass | NATS integration tests test the existing patterns; no new inter-service communication introduced. |
| III. Country-First Data Sovereignty | ✅ Pass | Test containers use `postgis/postgis:16-3.4` matching production. Fixtures use country-coded data. |
| IV. ML-Powered Intelligence | ✅ Pass | ML service integration tests cover ONNX inference and gRPC scoring; no new ML patterns introduced. |
| V. Code Quality Discipline | ✅ Pass | This feature IS the code quality discipline layer. golangci-lint expands with gosec/revive/ineffassign. |
| VI. Security & Ethical Scraping | ✅ Pass | gosec linter added to catch security anti-patterns. No scraping changes. |
| VII. Kubernetes-Native Deployment | ✅ Pass | No deployment changes. CI uses Docker-in-Docker for integration tests (standard pattern). |

**Post-Design Re-check**: All gates pass. `libs/testhelpers` is a new Go module but correctly placed in `libs/` per constitution structure.

## Project Structure

### Documentation (this feature)

```text
specs/030-test-coverage-infrastructure/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── makefile-targets.md
│   └── coverage-thresholds.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code Changes (repository root)

```text
# New files and directories
.codecov.yml                              # Codecov configuration (NEW)
scripts/check-go-coverage.sh             # Go coverage threshold enforcer (NEW)

libs/testhelpers/                         # Go shared test helpers (NEW MODULE)
├── go.mod                               # module github.com/estategap/testhelpers
├── go.sum
├── postgres.go
├── redis.go
├── nats.go
├── minio.go
└── wait.go

libs/common/testing/                      # Python shared test helpers (NEW package)
├── __init__.py
├── fixtures.py
├── factories.py
└── assertions.py

tests/contracts/                          # Contract fixtures (NEW)
├── frontend/
│   ├── GET_listings.json
│   ├── GET_zones.json
│   └── POST_alert_rules.json
└── api/
    └── proto_fixtures/
        ├── ScoreListingRequest.bin
        ├── ScoreListingResponse.bin
        └── ChatMessage.bin

tests/integration/                        # New integration tests
├── test_pipeline_e2e.py                 # (NEW)
└── cross_service/                       # (NEW directory)
    ├── conftest.py
    ├── test_api_gateway_ml_scorer.py
    ├── test_api_gateway_ai_chat.py
    ├── test_ws_server_ai_chat.py
    ├── test_alert_engine_dispatcher.py
    └── test_scrape_orchestrator_spiders.py

# Modified files
go.work                                   # Add libs/testhelpers
.golangci.yml                             # Add gosec, revive, ineffassign, typecheck
Makefile                                  # Add test-unit, test-integration, coverage targets

# Per Go service go.mod (all 6 + libs/pkg)
# Add: github.com/stretchr/testify
# Add: github.com/estategap/testhelpers (integration tests only)

# Per Python service pyproject.toml (all 4 + libs/common)
# Add pytest.ini_options block
# Add to dev: pytest-cov, pytest-mock, respx, testcontainers extras

# Frontend
frontend/package.json                     # Add msw, @vitest/coverage-v8
frontend/vitest.config.ts                 # Add coverage config and thresholds
frontend/src/test/msw.ts                  # MSW server setup (NEW)
frontend/src/test/handlers.ts             # MSW request handlers (NEW)

# CI workflows (all modified)
.github/workflows/ci-go.yml              # Add coverage job, integration job
.github/workflows/ci-python.yml          # Add coverage job, integration job, split unit/integration
.github/workflows/ci-frontend.yml        # Add test job with coverage
.github/workflows/ci-proto.yml           # Add buf breaking step

# New CI workflows
.github/workflows/ci-integration.yml     # Combined integration test workflow

# New service integration test files (per service)
services/api-gateway/internal/handler/listings_integration_test.go
services/scrape-orchestrator/internal/job/scheduler_integration_test.go
services/proxy-manager/internal/grpc/server_integration_test.go
services/pipeline/tests/integration/test_migrations.py   # (already exists, add 4 test cases)
services/ml/tests/integration/test_scorer_grpc.py        # (already exists, expand)
services/ai-chat/tests/integration/test_grpc_server.py   # (NEW)
```

## Implementation Phases

### Phase A — Foundation (Prerequisite for all other phases)

These must land first as everything else depends on them.

1. **Create `libs/testhelpers/` Go module**
   - `go.mod` with `module github.com/estategap/testhelpers`
   - `postgres.go`: `StartPostgres(t *testing.T) *pgxpool.Pool` — spins up `postgis/postgis:16-3.4`, returns connected pool, registers `t.Cleanup` for termination
   - `redis.go`: `StartRedis(t *testing.T) *redis.Client`
   - `nats.go`: `StartNATS(t *testing.T) *nats.Conn` — image `nats:2.10-alpine` with `-js` flag
   - `minio.go`: `StartMinIO(t *testing.T) (endpoint, accessKey, secretKey string)`
   - `wait.go`: `WaitForCondition(t *testing.T, fn func() bool, timeout, interval time.Duration)`
   - Add `libs/testhelpers` to `go.work`

2. **Create `libs/common/testing/` Python package**
   - `__init__.py` exporting fixture functions
   - `fixtures.py`: session-scoped container fixtures for PostgreSQL, Redis, NATS, MinIO; function-scoped pool/client fixtures with teardown
   - `factories.py`: `ListingFactory`, `ZoneFactory`, `UserFactory` using Pydantic v2 model constructors
   - `assertions.py`: `assert_listing_processed()`, `assert_nats_message_published()`
   - Update `libs/common/pyproject.toml`: add `testcontainers[postgres,redis]` to dev deps

3. **Update `.golangci.yml`**
   - Add to `linters.enable`: `gosec`, `revive`, `ineffassign`, `typecheck`
   - Keep all existing linters

4. **Add `testify` to all Go service `go.mod` files**
   - `github.com/stretchr/testify v1.9.0` to: `libs/pkg`, `api-gateway`, `ws-server`, `scrape-orchestrator`, `proxy-manager`, `alert-engine`, `alert-dispatcher`
   - `github.com/estategap/testhelpers v0.0.0` (workspace replace) to services with integration tests

5. **Standardize Python pytest configuration**
   - Add `[tool.pytest.ini_options]` block to: `spider-workers`, `pipeline`, `ml`, `ai-chat`, `libs/common`
   - Add to dev deps: `pytest-cov>=5.0`, `pytest-mock>=3.14`, `respx>=0.21`
   - Expand testcontainers extras per service:
     - `pipeline`: `testcontainers[postgres]` → keep, add `nats` extra
     - `ml`: add `testcontainers[postgres,minio]`
     - `ai-chat`: keep `[postgres,redis]`
     - `spider-workers`: add `testcontainers[redis,nats]`

---

### Phase B — Coverage Configuration & CI Wiring

6. **Create `.codecov.yml`**
   ```yaml
   coverage:
     status:
       project:
         default:
           target: 80%
           threshold: 2%
       flags:
         go:
           target: 80%
           threshold: 2%
         python:
           target: 80%
           threshold: 2%
         frontend:
           target: 70%
           threshold: 2%
   comment:
     layout: "diff, files"
     behavior: default
     require_changes: false
   flags:
     go:
       paths:
         - libs/pkg/
         - services/api-gateway/
         - services/ws-server/
         - services/alert-engine/
         - services/alert-dispatcher/
         - services/scrape-orchestrator/
         - services/proxy-manager/
     python:
       paths:
         - services/spider-workers/
         - services/pipeline/
         - services/ml/
         - services/ai-chat/
         - libs/common/
     frontend:
       paths:
         - frontend/
   ```

7. **Create `scripts/check-go-coverage.sh`**
   - Reads `coverage.out`, extracts total statement coverage via `go tool cover -func`
   - Compares against `$COVERAGE_THRESHOLD` (default 80)
   - Exits 1 with message if below threshold

8. **Update `Makefile`**
   - Add `test-unit` target: runs Go unit tests (no integration tag), Python unit tests (marker filter), frontend tests
   - Add `test-integration` target: runs Go integration tests (with tag), Python integration tests, cross-service tests, pipeline E2E
   - Add `coverage` target: generates HTML reports for all services

9. **Update `ci-go.yml`**
   - Existing `test` job: add `-race -coverprofile=coverage.out -covermode=atomic` flags
   - Existing `test` job: add coverage check step using `scripts/check-go-coverage.sh`
   - Add `upload-coverage` step: `codecov/codecov-action@v4` with flag `go-${{ matrix.module }}`
   - Add `test-integration` job: `go test -race -tags integration ./...`, Docker available on ubuntu-latest

10. **Update `ci-python.yml`**
    - Existing `test` job: rename to `test-unit`, add `-m "not integration and not slow"` flag
    - Add coverage args via `pyproject.toml` `addopts` (already configured in Phase A)
    - Add Codecov upload step with flag `python-${{ matrix.service }}`
    - Add `test-integration` job: `-m integration`, Docker-in-Docker setup

11. **Update `ci-frontend.yml`**
    - Add `test` job step: `npm run test -- --coverage`
    - Add Codecov upload step with flag `frontend`

12. **Update `ci-proto.yml`**
    - Add `buf breaking --against '.git#branch=main'` step (buf.yaml already has `breaking.use: [FILE]`)

13. **Create `.github/workflows/ci-integration.yml`**
    - Triggers: PR to main, push to main
    - Docker-in-Docker via `docker/setup-buildx-action`
    - Jobs: `go-integration`, `python-integration`, `cross-service`, `pipeline-e2e`
    - Timeout: 10 minutes

---

### Phase C — Go Integration Tests

14. **`services/api-gateway` integration tests**
    - `internal/handler/listings_integration_test.go`: tests listing search with real PostgreSQL + PostGIS
    - `internal/repository/subscription_integration_test.go`: Stripe webhook handler with real DB
    - Pattern: `//go:build integration`, uses `testhelpers.StartPostgres(t)`

15. **`services/scrape-orchestrator` integration tests**
    - `internal/scheduler/scheduler_integration_test.go`: publish job to NATS, verify state stored in Redis
    - Uses `testhelpers.StartNATS(t)` and `testhelpers.StartRedis(t)`

16. **`services/proxy-manager` gRPC integration tests**
    - `internal/grpc/server_integration_test.go`: start gRPC server on `127.0.0.1:0`, test `GetProxy` RPC
    - Uses real pool of test proxies (no external calls), verifies sticky routing

17. **`services/alert-engine` NATS integration test** (already has one — expand)
    - Verify redelivery behavior: consumer returns nak, message redelivered up to `max_deliver`

18. **`services/alert-dispatcher` NATS + DB integration test** (already has one — expand)
    - Test all sender types fail gracefully (use `failingSender` stub)
    - Verify history record created with correct failure reason

---

### Phase D — Python Integration Tests

19. **`services/pipeline/tests/integration/test_migrations.py`** (expand existing file)
    - `test_upgrade_from_scratch`: empty DB → `alembic upgrade head` → assert all expected tables present
    - `test_downgrade_each_migration`: for each revision, downgrade then re-upgrade, verify schema unchanged
    - `test_idempotency`: upgrade head twice, assert `alembic current` shows head with no pending migrations
    - `test_no_data_loss`: seed listing fixture → upgrade latest migration → assert listing still present
    - All tests use `postgres_container` fixture from `libs/common/testing/fixtures.py`

20. **`services/ml/tests/integration/test_scorer_grpc.py`** (expand existing)
    - `test_score_listing_happy_path`: start gRPC server in-process on random port, send `ScoreListingRequest`, verify `estimated_price > 0`
    - `test_score_listing_streaming`: batch scoring via server-streaming RPC, verify all responses arrive
    - `test_score_listing_invalid_args`: missing required fields → gRPC `INVALID_ARGUMENT` status
    - `test_cancellation`: cancel mid-stream, verify server stops sending

21. **`services/ai-chat/tests/integration/test_grpc_server.py`** (new)
    - `test_chat_unary`: start in-process server, send `ChatRequest`, verify non-empty response
    - `test_chat_streaming`: bidirectional stream, send 3 messages, verify 3+ responses arrive
    - `test_conversation_context`: send 2 messages in same session, verify second response references first

22. **`services/spider-workers/tests/integration/test_consumer.py`** (already exists — verify coverage)
    - Check that NATS `ack`/`nak` behavior is covered
    - Add `test_redelivery_on_nak` if missing

23. **`services/ml/tests/integration/test_nats_consumer.py`** (already exists — verify coverage)
    - Add `test_max_deliver_exhausted`: publish message, consumer always naks, verify dead-letter

---

### Phase E — Frontend Test Infrastructure

24. **Add MSW to frontend**
    - Add to `package.json` devDependencies: `"msw": "^2.6.0"`
    - Create `frontend/src/test/msw.ts`: MSW server setup with `setupServer()` from `msw/node`
    - Create `frontend/src/test/handlers.ts`: request handlers mirroring key API routes from `openapi.yaml`
      - `GET /api/v1/listings` → returns fixture `tests/contracts/frontend/GET_listings.json`
      - `GET /api/v1/zones` → returns fixture
      - `POST /api/v1/alert-rules` → returns fixture
    - Update `frontend/src/test/setup.ts`: import and start MSW server before all tests

25. **Add `@vitest/coverage-v8` to frontend**
    - Add to `package.json` devDependencies: `"@vitest/coverage-v8": "^2.1.8"`
    - Update `frontend/vitest.config.ts`:
      ```ts
      test: {
        coverage: {
          provider: 'v8',
          reporter: ['text', 'json', 'lcov'],
          exclude: ['src/test/**', '**/*.d.ts', 'src/types/**', 'src/i18n/**'],
          thresholds: {
            lines: 70,
            functions: 70,
            branches: 70,
            statements: 70,
          },
        },
      }
      ```
    - Update `package.json` scripts: `"test:coverage": "vitest run --coverage"`

26. **Add component tests** (demonstrate the pattern, cover key components)
    - `frontend/src/components/listing/ListingCard.test.tsx`: renders price, address, badge; no API call needed
    - `frontend/src/components/chat/ChatInput.test.tsx`: submit handler called with message text
    - `frontend/src/stores/alertStore.test.ts`: add alert rule, verify state (Zustand unit test)
    - `frontend/src/hooks/useListings.test.ts`: uses MSW to mock `/api/v1/listings`, verifies data transforms

---

### Phase F — Cross-Service & Pipeline E2E Tests

27. **Cross-service test infrastructure**
    - Create `tests/integration/cross_service/conftest.py`:
      - Session-scoped fixtures that start all required services as subprocesses
      - Shared PostgreSQL, Redis, NATS, MinIO containers
      - Service startup readiness polling (HTTP health check or NATS ping)
      - `pytest.ini` marks these as `integration` + `slow`

28. **`tests/integration/cross_service/test_alert_engine_dispatcher.py`**
    - Start alert-engine and alert-dispatcher services
    - Insert an alert rule in DB matching a known listing
    - Publish the listing to `scored.listings` NATS stream
    - Poll `alert_history` table for up to 10s
    - Assert: one history record with `status=dispatched`

29. **`tests/integration/cross_service/test_scrape_orchestrator_spiders.py`**
    - Start scrape-orchestrator service + NATS
    - POST `/api/v1/internal/scrape-jobs` to trigger job scheduling
    - Subscribe to `scrape.jobs` NATS subject
    - Assert: job message published within 5s with correct portal and region

30. **`tests/integration/test_pipeline_e2e.py`** (new file)
    - Fixture: start normalizer, deduplicator, enricher, scorer services as subprocesses
    - Shared containers: PostgreSQL (with migrations), NATS, Redis, MinIO (with test ML model)
    - `test_single_listing_e2e`: publish raw listing JSON → poll DB → assert `deal_score IS NOT NULL` within 30s
    - `test_batch_100_listings`: publish 100 listings → assert all processed within 60s → verify counts
    - `test_recovery_after_restart`: publish listing, kill enricher mid-flight, restart it, verify listing processed

---

### Phase G — Contract Tests

31. **Protobuf wire format fixtures**
    - Create `tests/contracts/api/proto_fixtures/` directory
    - Write Go test `libs/testhelpers/proto_contracts_test.go`:
      - Load each `.proto`-generated struct, populate with representative data
      - Marshal to binary, write to fixture file (first run creates fixtures)
      - Subsequent runs: marshal again, compare binary, fail if different (wire stability test)
    - Fixtures committed to git; regenerated only via `make update-proto-fixtures`

32. **OpenAPI response fixtures**
    - Create `tests/contracts/frontend/GET_listings.json` etc. with representative API response shapes
    - Create `tests/contracts/frontend/README.md` documenting the update process
    - MSW handlers (Phase E) consume these fixtures, ensuring frontend tests use the same data as E2E tests

33. **Frontend type generation validation in CI**
    - Add step to `ci-frontend.yml`: `npm run generate-api-types && git diff --exit-code src/types/api.ts`
    - This ensures the committed type file always matches the current OpenAPI spec
    - If the spec changes without regenerating types, CI fails

---

## Complexity Tracking

No constitution violations. All additions are in the correct layers (`libs/` for shared helpers, `services/` for service tests, `tests/` for cross-service tests).
