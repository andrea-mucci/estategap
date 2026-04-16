# Research: Monorepo Foundation

**Phase**: 0 — Research & Decisions  
**Feature**: 002-monorepo-foundation  
**Date**: 2026-04-16

---

## Decision 1: Go Workspace Strategy

**Decision**: Use `go.work` at repository root linking all Go modules with `go 1.23` directive.

**Rationale**: Go workspaces (introduced in Go 1.18) allow multiple modules in a single repository to reference each other without publishing to a registry. `libs/pkg` is referenced directly by all Go services via `go.work`, meaning `replace` directives in individual `go.mod` files are not needed. `go build ./...` from the root resolves the entire workspace.

**Alternatives considered**:
- Single `go.mod` at root: Not viable for a microservices monorepo — binaries would bundle all transitive dependencies and lose per-service isolation.
- `replace` directives in each `go.mod`: Works but is fragile — every new service must manually add the replace; `go.work` is the idiomatic Go solution.

---

## Decision 2: Python Package Management — uv

**Decision**: Each Python service has its own `pyproject.toml` with `[build-system]` set to `hatchling`. `uv` is the package manager. `libs/common` is added as a local path dependency.

**Rationale**: `uv` is the fastest Python package manager (Rust-based, 10–100x faster than pip). It resolves and installs from `pyproject.toml` with a `uv.lock` per-service lockfile. Local path deps (`../../../libs/common`) are declared in `[tool.uv.sources]` so `uv sync` installs the shared lib in editable mode automatically.

**Alternatives considered**:
- Poetry: Slower, does not support local path deps as well as uv.
- pip + requirements.txt: No lock file, no dependency resolution quality guarantees.
- Single shared virtualenv: Breaks per-service isolation; a dependency conflict in one service would break all.

---

## Decision 3: Protobuf Generation — buf

**Decision**: `buf.yaml` defines the workspace at `proto/`. `buf.gen.yaml` at root with two plugins:
- `protoc-gen-go` + `protoc-gen-go-grpc` → output to `libs/pkg/proto/` (Go stubs shared across all Go services via go.work)
- `grpcio-tools` / `protoc-gen-python` → output per-service stub directories for Python services that need them

**Rationale**: buf provides linting (`buf lint`) and breaking-change detection (`buf breaking`) in addition to generation. A single `buf.gen.yaml` at repo root keeps generation reproducible. Stubs committed to git mean CI can verify no diff without running buf in prod.

**Alternatives considered**:
- Raw `protoc` invocations in Makefile: Brittle, plugin version management is painful.
- Separate buf.gen.yaml per service: More flexible but harder to keep consistent; root-level gen is cleaner for a monorepo.

---

## Decision 4: Go Shared Library Module Path

**Decision**: `libs/pkg/go.mod` uses module path `github.com/estategap/libs`. Sub-packages are imported as `github.com/estategap/libs/logger`, `github.com/estategap/libs/config`, etc.

**Rationale**: A single `go.mod` for all shared Go libraries keeps the dependency graph simple. Adding a new shared package is just a new directory — no new `go.mod` or `go.work` entry required.

**Alternatives considered**:
- One `go.mod` per library (logger, config, etc.): Overkill for internal shared code; adds management overhead with no benefit.

---

## Decision 5: Proto Output Structure

**Decision**: Go stubs go to `libs/pkg/proto/estategap/v1/`. Python stubs go to `libs/common/proto/estategap/v1/`. Both are committed to git (not gitignored).

**Rationale**: Committing generated stubs means services can import them without running buf locally. CI verifies stubs are up to date by running `buf generate` and checking for a git diff. This is the standard pattern for Go/Python proto monorepos.

**Alternatives considered**:
- Generate on the fly (never commit): Requires buf installed everywhere, including production Docker builds, which inflates image sizes.
- Per-service stub copies: Leads to stubs getting out of sync across services.

---

## Decision 6: Docker Build Strategy

**Decision**:
- **Go services**: `golang:1.23-alpine` builder → `gcr.io/distroless/static:nonroot` final. CGO disabled (`CGO_ENABLED=0`), static binary. Target: < 20 MB.
- **Python services**: `python:3.12-slim` builder with uv install → `python:3.12-slim` final (not distroless — Python runtime required). Virtual env copied. Target: < 200 MB.
- **Frontend**: `node:22-alpine` builder with Next.js standalone output → `node:22-alpine` final (standalone folder only). Target: < 100 MB.

**Rationale**: Distroless for Go eliminates shell, package manager, and OS utilities from the final image — maximum attack surface reduction. Python cannot use distroless easily due to dynamic linking and the interpreter. Slim base is the best practical option. Next.js standalone output copies only the required Node modules, reducing image size ~70% vs a full install.

**Alternatives considered**:
- `scratch` base for Go: Requires manual CA cert copy; distroless already handles this.
- `python:3.12-alpine` for Python: Alpine uses musl libc which causes issues with some Python native extensions (asyncpg, numpy). Slim (Debian) is safer.

---

## Decision 7: GitHub Actions CI Strategy

**Decision**: Four separate workflows triggered on `push` and `pull_request` to `main` and `002-monorepo-foundation`:
- `ci-go.yml`: matrix over all 6 Go services + libs/pkg
- `ci-python.yml`: matrix over all 4 Python services + libs/common
- `ci-frontend.yml`: single job for frontend
- `ci-proto.yml`: buf lint + generate + diff check

**Rationale**: Separate workflows allow per-language status checks so a Python failure doesn't block a Go-only PR. Matrix jobs keep the YAML DRY and scale automatically as new services are added.

**Alternatives considered**:
- Single monolithic CI workflow: Harder to read, impossible to require specific language checks only on relevant PRs.
- Per-service CI files: Excessive duplication; matrix jobs handle service-level granularity cleanly.

---

## Decision 8: Helm Chart Scaffold

**Decision**: `helm/estategap/Chart.yaml` (apiVersion: v2, type: application), `values.yaml` (empty stubs), `templates/_helpers.tpl` (standard name helpers). No actual deployment templates in this phase.

**Rationale**: The scaffold establishes the chart structure and validates `helm lint` passes. Full deployment templates are out of scope for the monorepo foundation phase.

---

## Decision 9: Next.js Scaffold Approach

**Decision**: Use `create-next-app` scaffold with: TypeScript strict mode, App Router, Tailwind CSS, ESLint, `src/` directory. No `pages/` directory. Add `output: 'standalone'` to `next.config.ts`.

**Rationale**: App Router is the current Next.js standard (constitution mandates it). Standalone output is required for Docker image size targets.

---

## Resolved Clarifications

All technical choices were supplied by the user in the `/speckit.plan` input. No NEEDS CLARIFICATION items remain.
