# Makefile Target Contracts

**Feature**: 002-monorepo-foundation

These are the public contracts for root `Makefile` targets — inputs, outputs, and success conditions.

---

## `make proto`

**Purpose**: Regenerate all Go and Python stubs from `.proto` files.

**Inputs**: `proto/estategap/v1/*.proto`, `buf.gen.yaml`, `proto/buf.yaml`  
**Outputs**: `libs/pkg/proto/estategap/v1/*.pb.go`, `libs/common/proto/estategap/v1/*_pb2*.py`  
**Success condition**: Exit 0, no stderr errors from buf  
**Prerequisite**: `buf` installed and on `$PATH`

---

## `make test`

**Purpose**: Run all tests across all Go services and Python services.

**Sub-targets invoked**:
- Go: `go test ./...` (workspace-wide)
- Python: `uv run pytest` per service (spider-workers, pipeline, ml, ai-chat)

**Inputs**: All `*_test.go` and `test_*.py` files  
**Success condition**: All tests pass; exit 0  
**Note**: Empty codebase has no tests; placeholder test files emit zero failures.

---

## `make lint`

**Purpose**: Run all linters across all languages.

**Sub-targets invoked**:
- Go: `golangci-lint run ./...` (workspace-wide using `.golangci.yml`)
- Python: `uv run ruff check .` + `uv run mypy --strict .` per service
- Proto: `buf lint`

**Success condition**: All linters exit 0  
**Note**: Empty service files are lint-clean by definition.

---

## `make build-all`

**Purpose**: Build all Go binaries and install all Python dependencies.

**Sub-targets invoked**:
- Go: `go build ./...` per service
- Python: `uv sync` per service (installs deps into `.venv/`)
- Frontend: `npm ci && npm run build` in `frontend/`

**Success condition**: All binaries produced; all venvs populated; frontend build succeeds  
**Output artifacts**: `services/<name>/cmd/<name>` binaries (gitignored)

---

## `make docker-build-all`

**Purpose**: Build Docker images for all services and the frontend.

**Sub-targets invoked**:
- `docker build -t estategap/<service>:dev` per service

**Success condition**: All images build; size constraints met (Go < 20 MB, Python < 200 MB, Frontend < 100 MB)  
**Note**: Requires Docker daemon running.

---

## CI Workflow Contracts

### `ci-go.yml`

```
Trigger: push / pull_request → branches: [main, 002-monorepo-foundation]
Jobs:
  lint:
    runs-on: ubuntu-latest
    steps: checkout, setup-go@v5 (1.23), golangci-lint-action@v6
  test:
    runs-on: ubuntu-latest
    steps: checkout, setup-go@v5, go test ./...
  build:
    runs-on: ubuntu-latest
    strategy.matrix.service: [api-gateway, ws-server, scrape-orchestrator, proxy-manager, alert-engine, alert-dispatcher]
    steps: checkout, setup-go@v5, go build ./cmd
```

### `ci-python.yml`

```
Trigger: push / pull_request → branches: [main, 002-monorepo-foundation]
Jobs:
  lint-typecheck:
    runs-on: ubuntu-latest
    strategy.matrix.service: [spider-workers, pipeline, ml, ai-chat]
    steps: checkout, install uv, uv sync, uv run ruff check ., uv run mypy --strict .
  test:
    runs-on: ubuntu-latest
    strategy.matrix.service: [spider-workers, pipeline, ml, ai-chat]
    steps: checkout, install uv, uv sync, uv run pytest
```

### `ci-frontend.yml`

```
Trigger: push / pull_request → branches: [main, 002-monorepo-foundation]
Jobs:
  lint-typecheck-build:
    runs-on: ubuntu-latest
    steps: checkout, setup-node@v4 (22), npm ci, npm run lint, npx tsc --noEmit, npm run build
```

### `ci-proto.yml`

```
Trigger: push / pull_request → branches: [main, 002-monorepo-foundation]
Jobs:
  lint-and-verify:
    runs-on: ubuntu-latest
    steps: checkout, buf-setup-action, buf lint, buf generate, git diff --exit-code
```
