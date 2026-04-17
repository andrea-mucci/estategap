# Data Model: Test Coverage Infrastructure

**Feature**: 030-test-coverage-infrastructure  
**Date**: 2026-04-17  
**Phase**: 1 — Design

This feature is infrastructure, not a data feature. The "entities" are configuration artifacts and file structures that define the testing system.

---

## Configuration Entities

### Go Coverage Profile
- **File**: `coverage.out` (per module, temp — gitignored)
- **Format**: `go test -coverprofile` standard format
- **Fields**: package, statement count, covered count
- **Consumed by**: CI coverage threshold check script, Codecov uploader

### Python Coverage Report
- **File**: `coverage.xml` (per service, temp — gitignored), `htmlcov/` (local only)
- **Format**: Cobertura XML
- **Fields**: line-rate, branch-rate, per-package hit/miss counts
- **Consumed by**: Codecov uploader, `--cov-fail-under` enforcement in pytest

### Frontend Coverage Report
- **File**: `frontend/coverage/` directory (temp — gitignored)
- **Format**: v8 coverage (JSON + LCOV)
- **Fields**: lines, functions, branches, statements percentages
- **Consumed by**: Codecov uploader, vitest threshold enforcement

### Codecov Configuration
- **File**: `.codecov.yml` (repository root)
- **Fields**:
  - `coverage.project.default.target`: 80%
  - `coverage.project.default.threshold`: 2%
  - Per-flag overrides for `go`, `python`, `frontend`
  - `comment.layout`: diff, files
  - `comment.behavior`: default

### golangci-lint Configuration
- **File**: `.golangci.yml` (repository root, already exists)
- **Current linters**: errcheck, gosimple, govet, staticcheck, unused, gofmt, goimports, misspell
- **Added linters**: gosec, revive, ineffassign, typecheck
- **Retained**: all existing linters
- **Scope**: applies to all Go modules (each module picks up root config via `golangci-lint-action` `working-directory`)

### pytest Configuration Block (per Python service)
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "--strict-markers --cov=src --cov-branch --cov-report=xml --cov-report=term-missing --cov-fail-under=80"
markers = [
    "unit: Unit tests (fast, isolated, no external dependencies)",
    "integration: Integration tests (require Docker/testcontainers)",
    "slow: Slow tests (>5s individual test runtime)",
]
```
- Applied to: `spider-workers`, `pipeline`, `ml`, `ai-chat`, `libs/common`
- The `--cov` path varies per service source layout

### vitest Coverage Configuration
```ts
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'lcov'],
  exclude: ['src/test/**', '**/*.d.ts', 'src/types/**'],
  thresholds: {
    lines: 70,
    functions: 70,
    branches: 70,
    statements: 70,
  },
},
```

---

## File Structure Entities

### `libs/testhelpers/` — Go Shared Test Helpers
```
libs/testhelpers/
├── go.mod                    # module github.com/estategap/testhelpers
├── go.sum
├── postgres.go               # StartPostgres(t) → *pgxpool.Pool
├── redis.go                  # StartRedis(t) → *redis.Client
├── nats.go                   # StartNATS(t) → *nats.Conn (JetStream enabled)
├── minio.go                  # StartMinIO(t) → (endpoint, accessKey, secretKey)
└── wait.go                   # WaitForCondition(t, fn, timeout, interval)
```

**Module dependencies**:
- `github.com/testcontainers/testcontainers-go` v0.32+
- `github.com/testcontainers/testcontainers-go/modules/postgres`
- `github.com/testcontainers/testcontainers-go/modules/redis`
- `github.com/jackc/pgx/v5/pgxpool`
- `github.com/redis/go-redis/v9`
- `github.com/nats-io/nats.go`
- `github.com/stretchr/testify/require`

### `libs/common/testing/` — Python Shared Test Helpers
```
libs/common/testing/
├── __init__.py
├── fixtures.py               # Session-scoped pytest fixtures for all containers
├── factories.py              # Pydantic model factories (ListingFactory, etc.)
└── assertions.py             # Domain-specific assertion helpers
```

**Fixture inventory** (`fixtures.py`):
- `postgres_container` (session-scoped) → raw container
- `db_pool` (function-scoped) → `asyncpg.Pool`, runs migrations, truncates after each test
- `redis_container` (session-scoped) → raw container
- `redis_client` (function-scoped) → `redis.asyncio.Redis`, flushes after each test
- `nats_container` (session-scoped) → raw container with JetStream
- `nats_client` (function-scoped) → `nats.NATS` connection
- `minio_container` (session-scoped) → raw container
- `minio_client` (function-scoped) → `aiobotocore` S3 client

### `tests/contracts/` — Contract Fixtures
```
tests/contracts/
├── frontend/
│   ├── GET_listings.json             # Expected response shape for listing endpoints
│   ├── GET_zones.json
│   ├── POST_alert_rules.json
│   └── README.md                     # Contract update process
└── api/
    ├── proto_fixtures/               # Frozen proto wire format samples
    │   ├── ScoreListingRequest.bin
    │   ├── ScoreListingResponse.bin
    │   └── ChatMessage.bin
    └── README.md
```

### `tests/integration/cross_service/` — Cross-Service Tests
```
tests/integration/cross_service/
├── conftest.py                       # Shared fixtures for cross-service tests
├── test_api_gateway_ml_scorer.py     # api-gateway → ml-scorer gRPC
├── test_api_gateway_ai_chat.py       # api-gateway → ai-chat gRPC streaming
├── test_ws_server_ai_chat.py         # ws-server → ai-chat bidirectional gRPC
├── test_alert_engine_dispatcher.py   # alert-engine → alert-dispatcher NATS
└── test_scrape_orchestrator_spiders.py  # scrape-orchestrator → spider-workers NATS
```

### `tests/integration/test_pipeline_e2e.py` — Pipeline E2E
- Injects raw listing JSON to NATS `raw.listings.es`
- Polls DB until `deal_score IS NOT NULL` (30s timeout, 500ms interval)
- Verifies: listing exists, `deal_score`, `tier`, `model_version`, SHAP features set
- Batch test: 100 listings, all processed within 60s

---

## CI Artifact Entities

### ci-go.yml additions
- New job `test-coverage`:
  - Runs `go test -race -coverprofile=coverage.out -covermode=atomic ./...`
  - Uses `go tool cover -func coverage.out` and fails below 80%
  - Uploads `coverage.out` to Codecov with flag `go-{service}`
- New job `test-integration`:
  - Runs with `//go:build integration` tag: `-tags integration`
  - Requires Docker (ubuntu-latest runner has Docker)

### ci-python.yml additions
- Existing `test` job: add `-m "not integration"` to pytest command (unit only)
- New job `test-coverage`: runs full pytest with `--cov` flags, uploads to Codecov
- New job `test-integration`: runs `-m integration` only

### ci-frontend.yml additions
- New `test` job: `npm run test -- --coverage`
- Uploads `coverage/` to Codecov with flag `frontend`

### New: ci-integration.yml
- Docker-in-Docker for testcontainers
- Runs all integration tests across all languages
- 10-minute timeout
- Uses `services:` block for lightweight dependencies where possible

### New: ci-unit.yml (optional combined workflow)
- Matrix across all services for unit-only tests
- Fast path for PRs: no containers needed
