# Contract: Makefile Test Targets

**Version**: 1.0  
**Owner**: CI/Developer Experience  
**Consumers**: All developers, CI workflows

## Purpose

Defines the stable interface for running tests from the repository root. These Make targets are the single entry point for all test operations. CI workflows call these targets; they must not duplicate test invocation logic.

## Targets

### `make test-unit`

Runs all unit tests (no external dependencies) across all services.

**Preconditions**: Go 1.23, Python 3.12 + uv, Node 22 + npm installed.

**Behavior**:
- Go: `go test -race -coverprofile=coverage.out -covermode=atomic -tags !integration ./...` per module
- Python: `uv run pytest -m "not integration and not slow"` per service
- Frontend: `npm run test` in `frontend/`

**Exit codes**:
- `0` — all tests pass AND all coverage thresholds met
- `1` — any test failed OR any coverage below threshold

**Output**:
- Per-service coverage percentages to stdout
- `coverage.out` files in each Go module directory (gitignored)
- `coverage.xml` in each Python service directory (gitignored)

**Time budget**: < 3 minutes on CI hardware (4-core, 16GB RAM)

---

### `make test-integration`

Runs all integration tests that require Docker containers.

**Preconditions**: Docker daemon running, `make test-unit` passing.

**Behavior**:
- Go: `go test -race -tags integration ./...` per module that has integration tests
- Python: `uv run pytest -m integration` per service
- Cross-service: `uv run pytest tests/integration/cross_service/`
- Pipeline E2E: `uv run pytest tests/integration/test_pipeline_e2e.py`

**Exit codes**:
- `0` — all integration tests pass
- `1` — any integration test failed

**Time budget**: < 10 minutes on CI hardware

---

### `make test`

Runs `make test-unit` followed by `make test-integration`. Equivalent to full CI pass.

---

### `make coverage`

Generates combined coverage reports for all services without enforcing thresholds. Opens HTML report locally.

**Behavior**:
- Go: `go tool cover -html=coverage.out` per module
- Python: `uv run pytest --cov-report=html` per service
- Frontend: `npm run test -- --coverage --reporter=html`

---

### `make lint`

*(existing — no changes to contract, only adding gosec/revive/ineffassign to `.golangci.yml`)*

## Change Policy

- New Make targets MUST NOT break existing `make test`, `make lint`, `make build-all`.
- Coverage thresholds are encoded in service configs, not in the Makefile. The Makefile delegates threshold enforcement to pytest and vitest.
- The Go coverage threshold check lives in a small shell script `scripts/check-go-coverage.sh` called by `make test-unit`.
