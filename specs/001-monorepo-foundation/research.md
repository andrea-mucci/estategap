# Research: Monorepo Foundation

**Branch**: `001-monorepo-foundation` | **Date**: 2026-04-16

## Decision Log

---

### D-001: Go Workspace Strategy

**Decision**: Use `go.work` (Go workspaces, introduced in Go 1.18) to manage all Go modules in the monorepo.

**Rationale**: Each service is an independent module with its own `go.mod` and module path (e.g., `github.com/estategap/services/api-gateway`). `go.work` replaces directives at the repo root so `go build ./...` and `go test ./...` operate across all modules without `replace` directives. This enables independent versioning while enabling cross-module tooling.

**Alternatives considered**:
- Single `go.mod` at root: rejected — prevents independent deployment cadence per service.
- `replace` directives: rejected — requires every service's `go.mod` to reference local paths, creating maintenance burden.

**Implementation**: `go.work` with `use` directives for `libs/pkg` and each `services/<name>` directory. Go version: 1.23.

---

### D-002: Python Package Manager and Monorepo Layout

**Decision**: `uv` as the package manager. Each Python service has its own `pyproject.toml` with isolated virtual environments. `libs/common` is an editable path dependency.

**Rationale**: `uv` (by Astral, also author of `ruff`) provides `pip`-compatible resolution 10–100× faster than pip. Isolated per-service virtualenvs prevent dependency conflicts between services with different runtime requirements (e.g., `spider-workers` needing Scrapy vs `ml` needing LightGBM). Path dependency via `"estategap-common @ file://${PROJECT_ROOT}/libs/common"` in each `pyproject.toml` allows sharing models without a private registry.

**Alternatives considered**:
- Poetry: rejected — slower resolver, less ergonomic workspace support.
- uv workspaces (single lock file): rejected — lock file conflicts between services with divergent deps; per-service isolation preferred.
- Shared `requirements.txt`: rejected — no transitive dependency management.

---

### D-003: Protobuf Tooling with buf

**Decision**: `buf` for proto linting, breaking-change detection, and code generation. Single `proto/buf.yaml` for the module. `buf.gen.yaml` at root with two plugins: `protoc-gen-go` + `protoc-gen-go-grpc` for Go; `grpcio-tools` for Python.

**Rationale**: `buf` replaces raw `protoc` invocations with declarative YAML config, enforces Uber-style proto lint rules, and provides breaking-change detection (critical for contract safety). The CI `ci-proto.yml` workflow uses `buf generate && git diff --exit-code` to enforce that stubs are always committed.

**Alternatives considered**:
- Raw `protoc`: rejected — no lint, no breaking-change detection, complex plugin management.
- `grpc_tools_node_protoc` for frontend: not needed — frontend consumes REST via API Gateway, not gRPC directly.

**Generated output paths**:
- Go stubs → `libs/pkg/proto/` (importable by all Go services)
- Python stubs → `libs/common/estategap_common/proto/` (importable by all Python services)

---

### D-004: Docker Multi-stage Build Strategy

**Decision**:
- **Go**: `golang:1.23-alpine` builder → `gcr.io/distroless/static-debian12` runtime. CGO disabled (`CGO_ENABLED=0`), single static binary. Target: < 20 MB.
- **Python**: `python:3.12-slim` builder with `uv` install → `python:3.12-slim` runtime (slim only, not distroless, due to Python runtime requirements). Install deps with `--no-dev`. Target: < 200 MB.
- **Frontend**: `node:22-alpine` builder with `next build` (standalone output) → `node:22-alpine` runtime copying `.next/standalone` and `.next/static`. Target: < 100 MB.

**Rationale**: Distroless for Go achieves < 20 MB by including only CA certs and the static binary. Python slim is the practical minimum given the Python interpreter itself is ~50 MB; distroless Python exists but is immature for 3.12. Next.js `output: 'standalone'` bundles only the minimal Node modules needed to run, hitting ~90 MB on Alpine.

**Alternatives considered**:
- `scratch` for Go: rejected — no CA certificates, complicates TLS; distroless includes them.
- `python:3.12-alpine` for Python: rejected — musl libc causes compilation issues with `asyncpg` and `grpcio`.

---

### D-005: Go Shared Library Module Path

**Decision**: Module path `github.com/estategap/libs` for `libs/pkg`. All Go services import it as `github.com/estategap/libs/logger`, etc. Resolved locally via `go.work` — never published to a registry in the monorepo phase.

**Rationale**: Using a proper module path allows future extraction to a separate repo without changing import paths. `go.work` provides local resolution during monorepo development.

---

### D-006: CI Pipeline Trigger Strategy

**Decision**: All four pipelines trigger on `push` to any branch and `pull_request` targeting `main`. Path filters applied: `ci-go.yml` only runs when `services/**/*.go`, `libs/pkg/**`, or `proto/**` change; similarly for Python and frontend.

**Rationale**: Path filters prevent unnecessary CI runs (e.g., changing a frontend file should not trigger Go builds). However, all pipelines run on every PR to `main` regardless of paths to catch cross-cutting regressions.

**Alternatives considered**:
- Single monolithic CI workflow: rejected — conflates failure domains; a Python lint failure should not block a Go build from reporting green.
- Matrix jobs per service: deferred — overkill for the empty-scaffold phase; revisited when services diverge.

---

### D-007: golangci-lint Configuration

**Decision**: `.golangci.yml` at the repo root enabling: `errcheck`, `gosimple`, `govet`, `staticcheck`, `unused`, `gofmt`, `goimports`, `misspell`. `exhaustruct` and `wrapcheck` disabled for the scaffold phase.

**Rationale**: Conservative starting set that catches real bugs without generating noise on empty packages. Strict linters (exhaustruct, wrapcheck) added incrementally as services grow.

---

### D-008: Python mypy --strict with stubs

**Decision**: Each Python service's `pyproject.toml` sets `[tool.mypy] strict = true`. `types-*` stubs installed as dev dependencies for third-party libs lacking inline types (e.g., `types-redis`). `grpcio-stubs` added for gRPC type coverage.

**Rationale**: `mypy --strict` in the scaffold phase costs nothing (empty modules pass trivially) but establishes the discipline from day one. Adding `strict = false` later is a constitution violation.

---

### D-009: Helm Chart Scope

**Decision**: `helm/estategap/` contains Chart.yaml, values.yaml, and a `_helpers.tpl` only. No service deployment templates in this phase.

**Rationale**: The monorepo foundation spec is about code structure and tooling, not deployment manifests. Helm templates per service are written in the service implementation phases. The chart scaffold ensures `helm lint helm/estategap/` passes in CI without requiring actual manifests.
