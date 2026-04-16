# Feature Specification: Monorepo Foundation

**Feature Branch**: `001-monorepo-foundation`
**Created**: 2026-04-16
**Status**: Draft
**Input**: User description: "Build the monorepo foundation for the EstateGap platform."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Bootstraps a New Service (Priority: P1)

A developer cloning the repository for the first time can build and test all Go and Python services from the repo root without any per-service setup ritual. Running a single Makefile target produces working binaries and passes all checks.

**Why this priority**: This is the foundational experience — if the monorepo is not bootstrappable in one step, every subsequent development task is slowed down. It directly gates all other features.

**Independent Test**: Clone the repo, run `make build-all` and verify all services compile. Run `make test` and verify all tests pass (including empty placeholder tests).

**Acceptance Scenarios**:

1. **Given** a clean checkout with Go 1.23 and uv installed, **When** `make build-all` is run, **Then** all Go binaries compile without error and all Python services install dependencies successfully.
2. **Given** the repository is set up, **When** `make test` is run, **Then** all Go tests (`go test ./...`) and Python tests (`pytest`) pass on the empty codebase.
3. **Given** the repository is set up, **When** `make lint` is run, **Then** `golangci-lint`, `ruff check`, and `mypy --strict` all pass with zero errors.

---

### User Story 2 - Developer Generates Proto Stubs (Priority: P2)

A developer modifying a `.proto` file in `proto/` can regenerate Go and Python stubs with a single command and commit the result. No manual code-gen steps.

**Why this priority**: Protobuf contracts underpin all inter-service communication. If stubs cannot be regenerated reliably, any contract change breaks the entire development workflow.

**Independent Test**: Run `make proto`, then verify generated files exist under `libs/pkg/proto/` (Go) and each Python service's stub directory.

**Acceptance Scenarios**:

1. **Given** `buf` is installed, **When** `make proto` is run from the repo root, **Then** Go and Python stubs are generated in the correct output directories with no errors.
2. **Given** generated stubs exist, **When** the CI `ci-proto.yml` workflow runs, **Then** `buf lint` passes and `buf generate` produces no diff against committed stubs.

---

### User Story 3 - CI Pipeline Validates All Services on PR (Priority: P3)

When a developer opens a pull request, GitHub Actions automatically runs lint, type-check, and build for Go, Python, and Frontend. The pipeline passes on the empty-but-valid codebase.

**Why this priority**: CI is the safety net that enforces the constitution's quality gates. Without it, quality discipline degrades as the team grows.

**Independent Test**: Push a commit and verify all four CI workflows (`ci-go.yml`, `ci-python.yml`, `ci-frontend.yml`, `ci-proto.yml`) report green on GitHub Actions.

**Acceptance Scenarios**:

1. **Given** a PR is opened, **When** CI runs, **Then** all four workflows complete successfully with no failures.
2. **Given** a `.proto` file is changed, **When** `ci-proto.yml` runs, **Then** the workflow fails if generated stubs were not committed alongside the change.

---

### User Story 4 - Multi-stage Docker Images Built for Every Service (Priority: P4)

Every service has a Dockerfile producing a minimal image. Go images are under 20 MB, Python images under 200 MB, and the frontend image under 100 MB.

**Why this priority**: Image size directly affects cluster startup time and container registry costs. This acceptance criterion locks in the constraint early before Dockerfiles accumulate bloat.

**Independent Test**: Run `make docker-build-all` and inspect each image's size with `docker images`.

**Acceptance Scenarios**:

1. **Given** Docker is available, **When** `make docker-build-all` is run, **Then** all images build successfully and meet size constraints.
2. **Given** Go Dockerfiles use distroless base, **When** image is inspected, **Then** size is under 20 MB.

---

### Edge Cases

- What happens when a new service is added but `go.work` is not updated? `go build ./...` should fail with a clear error.
- How does `make proto` behave when `buf` is not installed? It should fail fast with an actionable error message.
- What if `uv sync` fails due to a conflicting dependency in a Python service? Each service has an isolated virtual environment, so failures are scoped to that service.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST contain a `services/` directory with subdirectories for each of the 10 microservices (api-gateway, ws-server, scrape-orchestrator, proxy-manager, alert-engine, alert-dispatcher, spider-workers, pipeline, ml, ai-chat).
- **FR-002**: The repository MUST contain a `go.work` file at the root that links all Go service modules and `libs/pkg`.
- **FR-003**: The repository MUST contain a `proto/` directory with `buf.yaml`, `buf.gen.yaml`, and five `.proto` files (common, ai_chat, ml_scoring, proxy, listings).
- **FR-004**: Each Go service MUST have a `go.mod`, `cmd/main.go`, `internal/` package structure, and a multi-stage `Dockerfile`.
- **FR-005**: Each Python service MUST have a `pyproject.toml` (uv-compatible), a main entrypoint, and a multi-stage `Dockerfile`.
- **FR-006**: The repository MUST contain a `libs/` directory with Go shared packages (`pkg/logger`, `pkg/config`, `pkg/natsutil`, `pkg/grpcutil`) and Python shared library (`libs/common/`).
- **FR-007**: The repository MUST contain a root `Makefile` with targets: `proto`, `test`, `lint`, `build-all`, `docker-build-all`.
- **FR-008**: The repository MUST contain a `helm/estategap/` directory with a valid Helm chart scaffold.
- **FR-009**: The repository MUST contain `.github/workflows/` with four CI pipeline files: `ci-go.yml`, `ci-python.yml`, `ci-frontend.yml`, `ci-proto.yml`.
- **FR-010**: The `frontend/` directory MUST contain a Next.js 15 application scaffold with TypeScript strict mode and a multi-stage Dockerfile.

### Key Entities

- **Go Service Module**: A Go module with its own `go.mod`, linked into `go.work`. Has `cmd/main.go` and `internal/` sub-packages.
- **Python Service Package**: A Python package managed by `uv` with `pyproject.toml`. Has a main entrypoint and isolated virtual environment.
- **Proto Contract**: A `.proto` file defining a gRPC service or shared message types, processed by `buf` to produce Go and Python stubs.
- **Shared Library**: Code in `libs/` that may be imported by any service of the appropriate language. No cross-service direct imports allowed.
- **CI Workflow**: A GitHub Actions YAML file that runs quality gates (lint, test, build) for a specific language or toolchain.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can clone the repository and run `make build-all` successfully in under 5 minutes on a standard CI runner, with no manual configuration steps.
- **SC-002**: `tree -L 3` output matches the defined monorepo structure exactly — all 10 service directories, `proto/`, `libs/`, `frontend/`, `helm/`, and `.github/workflows/` are present.
- **SC-003**: All four CI workflows pass on the initial empty codebase without modifications.
- **SC-004**: `make proto` completes without errors and produces stubs in under 60 seconds on a standard developer machine.
- **SC-005**: All Docker images build successfully and meet size targets: Go < 20 MB, Python < 200 MB, Frontend < 100 MB.
- **SC-006**: `go build ./...` succeeds across the entire workspace with no errors.
- **SC-007**: `uv sync` succeeds in each Python service directory independently.
- **SC-008**: `ruff check` and `mypy --strict` pass across all Python services with zero errors on the empty codebase.

## Assumptions

- Developers have Go 1.23, Python 3.12, `uv`, `buf`, and Docker installed locally.
- CI runners are GitHub-hosted (ubuntu-latest) with sufficient resources for multi-language builds.
- The `frontend/` Next.js application scaffold uses the App Router and TypeScript strict mode as mandated by the constitution.
- `buf` generates stubs into `libs/pkg/proto/` for Go and into each Python service's package directory.
- Each Python service's `pyproject.toml` declares `libs/common` as a local path dependency.
- The Go `libs/pkg` module is included in `go.work` as a shared module, not published to a registry.
- Helm chart in `helm/estategap/` is a scaffold only — no values files are populated in this foundation phase.
- All service `cmd/main.go` files contain only a minimal `main()` function returning immediately (empty-but-valid pattern for CI).
