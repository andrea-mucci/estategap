# Feature: Unit, Integration & Contract Tests

## /specify prompt

```
Set up the testing frameworks and test coverage infrastructure for all services in the monorepo: Go, Python, and TypeScript frontend. Include integration tests with testcontainers and contract tests for service boundaries.

## What

### 1. Unit test infrastructure

**Go services:**
- `go test ./...` with `-race -cover` flags
- Table-driven test pattern using `testify/assert`
- Coverage report per package via `go test -coverprofile`
- `golangci-lint` configured with strict rules (errcheck, gosec, govet, revive, staticcheck, unused)
- Mock interfaces with hand-written fakes in `internal/<package>/mocks/`

**Python services:**
- `pytest` with `pytest-asyncio`, `pytest-cov`, `pytest-mock`
- Parametrized tests using `@pytest.mark.parametrize`
- Coverage with `--cov-branch --cov-report=xml --cov-report=term`
- `ruff check` for linting, `mypy --strict` for type checking
- Pydantic model tests: valid construction, invalid data rejection, JSON round-trip, edge cases

**Frontend:**
- `vitest` with React Testing Library for components
- Mock Service Worker (`msw`) for API mocks
- `@testing-library/jest-dom` for DOM assertions
- `eslint` with strict React rules, `tsc --noEmit` for type checking

### 2. Coverage thresholds enforced in CI

- Go services: 80% statement coverage — CI fails below threshold
- Python services: 80% statement + branch coverage
- Frontend: 70% statement coverage
- Codecov integration for PR comments showing coverage diff
- Per-service thresholds configurable (some services can be stricter)

### 3. Integration tests with testcontainers

- Each service with external dependencies has integration tests that spin up real:
  - PostgreSQL 16 + PostGIS
  - Redis 7
  - NATS with JetStream enabled
  - MinIO
- Go: `testcontainers-go` library
- Python: `testcontainers-python` library
- Fresh container instance per test suite (parallel-safe)
- Shared test helpers in `libs/testhelpers/` (Go) and `libs/common/testing/` (Python)

### 4. Database migration tests

- All Alembic migrations apply successfully on empty DB
- All migrations rollback successfully (`alembic downgrade -1` per migration)
- Migrations are idempotent (re-running from head produces no diff in schema)
- No migration causes data loss on existing fixture data
- Test at `services/pipeline/tests/integration/test_migrations.py`

### 5. gRPC integration tests

- Each gRPC service (ai-chat, ml-scorer, proxy-manager) has tests that:
  - Start the real gRPC server in-process on a random port
  - Create a real client connection
  - Make calls via generated stubs
  - Verify response schemas match Protobuf definitions
  - Test streaming RPCs (Chat bidirectional, batch scoring)
  - Verify error handling (cancellation, deadlines, invalid args)

### 6. NATS integration tests

- Each NATS consumer has tests that:
  - Publish test messages to the stream
  - Wait for consumer to process (with timeout)
  - Verify side effects: DB writes, downstream events, Redis state
  - Test ack/nak behavior and redelivery
  - Test stream consumer configuration (durable, ack_wait, max_deliver)

### 7. Data pipeline integration tests

- Inject raw listing JSON → trace through normalizer → deduplicator → enricher → scorer → final DB state
- Pipeline latency assertion: < 30s per listing (end-to-end in test environment)
- Failure recovery: kill a pipeline component pod mid-flight, restart, verify no message loss
- Batch processing: inject 100 listings, verify all processed correctly

### 8. Cross-service integration tests

Key interaction paths have dedicated tests:
- api-gateway → ml-scorer (gRPC): request a valuation, verify response
- api-gateway → ai-chat (gRPC streaming): initiate conversation, verify tokens stream
- ws-server → ai-chat (bidirectional gRPC): full chat protocol
- alert-engine → alert-dispatcher (NATS): trigger alert, verify all channels dispatched
- scrape-orchestrator → spider-workers (NATS): schedule job, verify worker picks it up

### 9. Protobuf contract tests

- Every RPC has contract tests verifying:
  - Client and server agree on message format
  - Backward compatibility (new fields optional or have defaults)
  - Forward compatibility (old clients work with new servers)
- `buf breaking --against '.git#branch=main'` in CI to detect breaking changes
- Breaking changes must bump proto version explicitly

### 10. OpenAPI contract tests

- Frontend TypeScript types auto-generated from OpenAPI spec via `openapi-typescript-codegen`
- API responses validated against OpenAPI schema in E2E tests using `openapi-response-validator` or `openapi-backend`
- Consumer-driven contracts: frontend expectations codified as fixtures in `tests/contracts/frontend/`
- API returns fixtures in test mode for deterministic frontend tests

## Why

Tests catch regressions before they reach production. Unit tests are fast and run on every save. Integration tests verify services work with real dependencies. Contract tests prevent breaking changes across service boundaries in the polyglot architecture.

## Acceptance Criteria

- `make test-unit` runs all unit tests across all services in < 3 minutes
- `make test-integration` runs integration tests in < 10 minutes
- Coverage report shows ≥ 80% for Go/Python, ≥ 70% for frontend
- CI fails if coverage drops below threshold
- All DB migrations have corresponding down-migrations and are tested
- gRPC contract tests cover all RPCs in all proto files
- `buf breaking` runs on every PR and blocks breaking changes
- OpenAPI schema validation runs on every API response in E2E tests
- Pipeline integration test verifies end-to-end listing processing < 30s
- All services have ≥ 1 integration test demonstrating the happy path with real dependencies
```
