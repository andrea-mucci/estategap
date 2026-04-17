# Quickstart: Test Coverage Infrastructure

**Feature**: 030-test-coverage-infrastructure  
**Date**: 2026-04-17

## Prerequisites

- Docker running (for integration tests and testcontainers)
- Go 1.23: `go version`
- Python 3.12 + uv: `uv --version`
- Node 22 + npm: `node --version && npm --version`
- buf: `buf --version` (for proto contract tests)
- golangci-lint: `golangci-lint --version`

## Run Unit Tests (fast, no Docker required)

```bash
# All services, all languages
make test-unit

# Individual service (Go)
cd services/api-gateway && go test -race -coverprofile=coverage.out -covermode=atomic ./...

# Individual service (Python)
cd services/pipeline && uv run pytest -m "not integration and not slow" -v

# Frontend
cd frontend && npm test
```

## Run Integration Tests (requires Docker)

```bash
# All integration tests
make test-integration

# Go integration tests only (uses build tag)
cd services/alert-dispatcher && go test -race -tags integration ./...

# Python integration tests only
cd services/pipeline && uv run pytest -m integration -v

# Pipeline end-to-end test
uv run pytest tests/integration/test_pipeline_e2e.py -v

# Cross-service tests
uv run pytest tests/integration/cross_service/ -v
```

## View Coverage Reports

```bash
# Go: open HTML coverage for a service
cd services/api-gateway
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out

# Python: open HTML coverage
cd services/pipeline
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html

# Frontend: open HTML coverage
cd frontend
npm run test -- --coverage --reporter=html
open coverage/index.html
```

## Check Proto Breaking Changes

```bash
buf breaking --against '.git#branch=main'
```

## Run Linting (all languages)

```bash
make lint
```

## Add a New Integration Test (Go)

1. Create `<service>/internal/<package>/<something>_integration_test.go`
2. Add build tag at top: `//go:build integration`
3. Use helpers from `libs/testhelpers`:
   ```go
   import "github.com/estategap/testhelpers"

   func TestMyFeature(t *testing.T) {
       pool := testhelpers.StartPostgres(t)
       nc := testhelpers.StartNATS(t)
       // ... your test
   }
   ```
4. Run: `cd services/<service> && go test -race -tags integration ./internal/<package>/...`

## Add a New Integration Test (Python)

1. Create `services/<service>/tests/integration/test_<something>.py`
2. Mark with `@pytest.mark.integration`
3. Use fixtures from `libs/common/testing/fixtures.py`:
   ```python
   import pytest
   from estategap_common.testing.fixtures import db_pool, redis_client

   @pytest.mark.integration
   async def test_my_feature(db_pool, redis_client):
       # ... your test
   ```
4. Run: `cd services/<service> && uv run pytest -m integration tests/integration/test_<something>.py -v`

## Troubleshoot Coverage Threshold Failures

```bash
# Go: see per-package coverage
go tool cover -func=coverage.out | sort -k3 -n

# Python: see per-module coverage
cd services/<service>
uv run pytest --cov=src --cov-report=term-missing -m "not integration"

# Frontend: see uncovered lines
cd frontend
npm run test -- --coverage --reporter=verbose
```
