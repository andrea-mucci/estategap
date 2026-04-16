# Tasks: Monorepo Foundation

**Input**: Design documents from `/specs/001-monorepo-foundation/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: No test tasks generated — the empty-but-valid scaffold passes linting and CI by construction; tests are added per-service in subsequent features.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup (Root Scaffolding)

**Purpose**: Create the top-level repository structure, workspace manifests, and shared tooling config.

- [x] T001 Create top-level directory tree: `services/`, `libs/pkg/`, `libs/common/`, `proto/estategap/v1/`, `frontend/`, `helm/estategap/templates/`, `.github/workflows/`
- [x] T002 Create `go.work` at repo root (Go 1.23, empty `use` block — populated per service in Phase 3) at `go.work`
- [x] T003 [P] Create root `.golangci.yml` enabling `errcheck`, `gosimple`, `govet`, `staticcheck`, `unused`, `gofmt`, `goimports`, `misspell` at `.golangci.yml`
- [x] T004 [P] Create `.gitignore` covering Go binaries, Python `__pycache__`/`.venv`/`dist`, Node `node_modules`/`.next`, generated proto stubs (`libs/pkg/proto/`, `libs/common/estategap_common/proto/`), `.env` files at `.gitignore`
- [x] T005 [P] Create root `Makefile` skeleton with variable declarations (`REGISTRY`, `TAG`, `GO_SERVICES`, `PYTHON_SERVICES`) and `.PHONY` list — targets stubbed with `@echo` placeholders at `Makefile`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared libraries for both Go and Python that every service depends on. Must complete before any service scaffold.

**⚠️ CRITICAL**: No service work begins until this phase is complete.

### Go Shared Library (`libs/pkg`)

- [x] T006 Create `libs/pkg/go.mod` with module path `github.com/estategap/libs`, Go 1.23, and dependencies: `github.com/spf13/viper`, `github.com/nats-io/nats.go`, `google.golang.org/grpc`, `google.golang.org/protobuf` at `libs/pkg/go.mod`
- [x] T007 [P] Create `libs/pkg/logger/logger.go` — `slog`-based JSON logger with `New(level string) *slog.Logger`, `WithContext(ctx context.Context) *slog.Logger` at `libs/pkg/logger/logger.go`
- [x] T008 [P] Create `libs/pkg/config/config.go` — viper-based loader exposing `Load(prefix string) (*viper.Viper, error)` reading env vars and optional K8s ConfigMap mount path at `libs/pkg/config/config.go`
- [x] T009 [P] Create `libs/pkg/natsutil/natsutil.go` — `Connect(url string) (*nats.Conn, error)` and `EnsureStream(js nats.JetStreamContext, cfg nats.StreamConfig) error` at `libs/pkg/natsutil/natsutil.go`
- [x] T010 [P] Create `libs/pkg/grpcutil/grpcutil.go` — `Dial(target string, opts ...grpc.DialOption) (*grpc.ClientConn, error)` with exponential-backoff retry and basic circuit-breaker (fail after 5 consecutive errors) at `libs/pkg/grpcutil/grpcutil.go`
- [x] T011 Add `libs/pkg` to `go.work` with `use ./libs/pkg` at `go.work`

### Python Shared Library (`libs/common`)

- [x] T012 Create `libs/common/pyproject.toml` with package name `estategap-common`, version `0.1.0`, Python `>=3.12`, dependencies: `pydantic>=2`, `nats-py[nkeys]>=2`, `asyncpg>=0.29`, `structlog>=24`, `grpcio>=1.62`, `grpcio-tools>=1.62`; dev deps: `pytest`, `pytest-asyncio`, `mypy`, `ruff`, `grpcio-stubs` at `libs/common/pyproject.toml`
- [x] T013 [P] Create `libs/common/estategap_common/__init__.py` and `libs/common/estategap_common/models/__init__.py` (package markers) at `libs/common/estategap_common/__init__.py`
- [x] T014 [P] Create `libs/common/estategap_common/models/listing.py` — `ListingType` (Enum), `ListingStatus` (Enum), `Listing` and `RawListing` Pydantic v2 models per data-model.md at `libs/common/estategap_common/models/listing.py`
- [x] T015 [P] Create `libs/common/estategap_common/models/zone.py` — `Zone` Pydantic v2 model per data-model.md at `libs/common/estategap_common/models/zone.py`
- [x] T016 [P] Create `libs/common/estategap_common/models/alert.py` — `AlertRule` Pydantic v2 model per data-model.md at `libs/common/estategap_common/models/alert.py`
- [x] T017 [P] Create `libs/common/estategap_common/models/scoring.py` — `ShapValue` and `ScoringResult` Pydantic v2 models per data-model.md at `libs/common/estategap_common/models/scoring.py`
- [x] T018 [P] Create `libs/common/estategap_common/models/conversation.py` — `ChatMessage` and `ConversationState` Pydantic v2 models per data-model.md at `libs/common/estategap_common/models/conversation.py`
- [x] T019 [P] Create `libs/common/estategap_common/nats_client.py` — async `NatsClient` class with `connect(url: str)`, `publish(subject: str, payload: bytes)`, `subscribe(subject: str, cb: Callable)`, `close()` at `libs/common/estategap_common/nats_client.py`
- [x] T020 [P] Create `libs/common/estategap_common/db.py` — `create_pool(dsn: str) -> asyncpg.Pool` factory and `get_connection(pool: asyncpg.Pool)` async context manager at `libs/common/estategap_common/db.py`
- [x] T021 [P] Create `libs/common/estategap_common/logging.py` — `configure_logging(level: str = "INFO", service: str = "unknown")` using structlog with JSON renderer and ISO timestamp at `libs/common/estategap_common/logging.py`

**Checkpoint**: `cd libs/pkg && go build ./...` succeeds. `cd libs/common && uv sync && uv run mypy --strict estategap_common/ && uv run ruff check .` passes.

---

## Phase 3: User Story 1 — Developer Bootstraps a New Service (Priority: P1) 🎯 MVP

**Goal**: All 10 service directories and the frontend exist with valid empty-but-compilable code. `make build-all`, `make test`, and `make lint` pass from the repo root.

**Independent Test**: `make build-all && make test && make lint` — all three complete with exit code 0.

### Go Service Scaffolds

- [x] T022 Scaffold `services/api-gateway`: create `go.mod` (`github.com/estategap/services/api-gateway`, Go 1.23, require `github.com/estategap/libs`), `cmd/main.go` (minimal `main()`), empty `internal/handler/`, `internal/middleware/`, `internal/config/`, `internal/grpc/` packages, `.env.example`; add `use ./services/api-gateway` to `go.work` at `services/api-gateway/`
- [x] T023 [P] Scaffold `services/ws-server`: same pattern as T022; module `github.com/estategap/services/ws-server` at `services/ws-server/`
- [x] T024 [P] Scaffold `services/scrape-orchestrator`: module `github.com/estategap/services/scrape-orchestrator` at `services/scrape-orchestrator/`
- [x] T025 [P] Scaffold `services/proxy-manager`: module `github.com/estategap/services/proxy-manager` at `services/proxy-manager/`
- [x] T026 [P] Scaffold `services/alert-engine`: module `github.com/estategap/services/alert-engine` at `services/alert-engine/`
- [x] T027 [P] Scaffold `services/alert-dispatcher`: module `github.com/estategap/services/alert-dispatcher` at `services/alert-dispatcher/`

### Python Service Scaffolds

- [ ] T028 [P] Scaffold `services/spider-workers`: `pyproject.toml` (package `spider-workers`, Python `>=3.12`, dep `estategap-common @ file://../../libs/common`, dev deps `pytest ruff mypy`), `spider_workers/__init__.py`, `main.py` (prints `"spider-workers starting"` and exits), `.env.example` at `services/spider-workers/`
- [ ] T029 [P] Scaffold `services/pipeline`: same pattern; package `pipeline`, entrypoint `pipeline/__init__.py` + `main.py` at `services/pipeline/`
- [ ] T030 [P] Scaffold `services/ml`: package `ml`, entrypoint `ml/__init__.py` + `main.py` at `services/ml/`
- [ ] T031 [P] Scaffold `services/ai-chat`: package `ai-chat`, module dir `ai_chat/__init__.py` + `main.py` at `services/ai-chat/`

### Frontend Scaffold

- [ ] T032 Scaffold `frontend/`: create `package.json` (`next@15`, `react@19`, `react-dom@19`, `typescript@5`, `tailwindcss@4`, `eslint`, `eslint-config-next`), `tsconfig.json` (strict mode, `target: ES2022`, `moduleResolution: bundler`), `next.config.ts` (`output: 'standalone'`), `tailwind.config.ts`, `src/app/layout.tsx` (root layout), `src/app/page.tsx` (placeholder home page) at `frontend/`

### Makefile Implementation

- [ ] T033 Implement `Makefile` `build-all` target: `go build ./...` from workspace root + loop `uv sync` in each `PYTHON_SERVICES` dir + `cd frontend && npm ci && npm run build` at `Makefile`
- [ ] T034 [P] Implement `Makefile` `test` target: `go test ./...` from workspace root + loop `cd services/$$s && uv run pytest` for each Python service at `Makefile`
- [ ] T035 [P] Implement `Makefile` `lint` target: `golangci-lint run ./...` + loop `cd services/$$s && uv run ruff check . && uv run mypy --strict .` for each Python service + `cd frontend && npm run lint && npx tsc --noEmit` at `Makefile`

### Helm Chart Scaffold

- [ ] T036 [P] Create `helm/estategap/Chart.yaml` (`apiVersion: v2`, `name: estategap`, `version: 0.1.0`, `appVersion: 0.1.0`), `helm/estategap/values.yaml` (empty placeholder), `helm/estategap/templates/_helpers.tpl` (standard name helper) at `helm/estategap/`

**Checkpoint**: `make build-all && make test && make lint` all pass. `helm lint helm/estategap/` passes.

---

## Phase 4: User Story 2 — Developer Generates Proto Stubs (Priority: P2)

**Goal**: `make proto` runs `buf generate` and produces Go and Python stubs from the 5 `.proto` files defined in data-model.md and contracts/proto-overview.md.

**Independent Test**: `make proto && git diff --exit-code` — stubs generated with no uncommitted diff.

### buf Configuration

- [ ] T037 Create `proto/buf.yaml` (v2, module path `buf.build/estategap/estategap`, lint: DEFAULT, breaking: FILE) at `proto/buf.yaml`
- [ ] T038 Create `buf.gen.yaml` at repo root with two plugins: `buf.build/protocolbuffers/go` → `libs/pkg/proto` (paths=source_relative) and `buf.build/grpc/go` → `libs/pkg/proto`; Python: `buf.build/grpc/python` → `libs/common/estategap_common/proto` at `buf.gen.yaml`

### Proto Files

- [ ] T039 [P] Write `proto/estategap/v1/common.proto`: package `estategap.v1`; messages `Timestamp`, `Money`, `GeoPoint`, `PaginationRequest`, `PaginationResponse` per data-model.md at `proto/estategap/v1/common.proto`
- [ ] T040 [P] Write `proto/estategap/v1/listings.proto`: import common.proto; enums `ListingType`, `ListingStatus`; messages `Listing`, `RawListing`, `PriceHistory` per data-model.md at `proto/estategap/v1/listings.proto`
- [ ] T041 [P] Write `proto/estategap/v1/ai_chat.proto`: service `AIChatService` with `Chat` (bidi streaming), `GetConversation`, `ListConversations` RPCs; all request/response messages per data-model.md at `proto/estategap/v1/ai_chat.proto`
- [ ] T042 [P] Write `proto/estategap/v1/ml_scoring.proto`: service `MLScoringService` with `ScoreListing`, `ScoreBatch` (server-streaming), `GetComparables` RPCs; `ScoringResult`, `ShapValue` messages per data-model.md at `proto/estategap/v1/ml_scoring.proto`
- [ ] T043 [P] Write `proto/estategap/v1/proxy.proto`: service `ProxyService` with `GetProxy`, `ReportResult` RPCs; `Proxy`, `GetProxyRequest`, `ReportResultRequest`, `ReportResultResponse` messages per data-model.md at `proto/estategap/v1/proxy.proto`

### Makefile Proto Target and Stub Generation

- [ ] T044 Implement `Makefile` `proto` target: `buf generate` (and pre-check that `buf` is installed, printing actionable error if not) at `Makefile`
- [ ] T045 Run `make proto` to generate stubs into `libs/pkg/proto/` (Go) and `libs/common/estategap_common/proto/` (Python); commit generated files at `libs/pkg/proto/` and `libs/common/estategap_common/proto/`

**Checkpoint**: `buf lint proto/` passes. `make proto` exits 0. `git diff --exit-code` shows no diff after generation.

---

## Phase 5: User Story 3 — CI Pipeline Validates All Services on PR (Priority: P3)

**Goal**: Four GitHub Actions workflows lint, type-check, and build all services. All pass on the empty codebase.

**Independent Test**: Push a commit and verify all four CI workflows report green on GitHub Actions.

- [ ] T046 Create `.github/workflows/ci-go.yml`: triggers on `push` and `pull_request` to `main`; path filters for `services/**/*.go`, `libs/pkg/**`, `proto/**`; jobs: `lint` (`golangci-lint-action@v6`), `test` (`go test ./...`), `build` (`go build ./...`); uses Go 1.23 setup action at `.github/workflows/ci-go.yml`
- [ ] T047 [P] Create `.github/workflows/ci-python.yml`: path filters for Python service dirs and `libs/common/**`; matrix over `[spider-workers, pipeline, ml, ai-chat]`; jobs per service: install `uv`, `uv sync`, `uv run ruff check .`, `uv run mypy --strict .`, `uv run pytest`; Python 3.12 at `.github/workflows/ci-python.yml`
- [ ] T048 [P] Create `.github/workflows/ci-frontend.yml`: path filter `frontend/**`; jobs: `npm ci`, `npm run lint`, `npx tsc --noEmit`, `npm run build`; Node 22 at `.github/workflows/ci-frontend.yml`
- [ ] T049 [P] Create `.github/workflows/ci-proto.yml`: path filter `proto/**`; jobs: install `buf`, `buf lint proto/`, `buf generate`, `git diff --exit-code` (fail if stubs not committed) at `.github/workflows/ci-proto.yml`

**Checkpoint**: All four workflow files are valid YAML. `act` local simulation or first push to branch confirms green.

---

## Phase 6: User Story 4 — Multi-stage Docker Images (Priority: P4)

**Goal**: Every service and the frontend has a multi-stage Dockerfile. `make docker-build-all` succeeds. Go images < 20 MB, Python images < 200 MB, Frontend < 100 MB.

**Independent Test**: `make docker-build-all && docker images | grep estategap` — all images present and within size targets.

### Go Dockerfiles (golang:1.23-alpine builder → gcr.io/distroless/static-debian12)

- [ ] T050 Write `services/api-gateway/Dockerfile`: stage 1 `golang:1.23-alpine` — `COPY go.work go.work`, copy `libs/pkg` and service source, `CGO_ENABLED=0 go build -o /api-gateway ./cmd/...`; stage 2 `gcr.io/distroless/static-debian12` — copy binary, `ENTRYPOINT ["/api-gateway"]` at `services/api-gateway/Dockerfile`
- [ ] T051 [P] Write `services/ws-server/Dockerfile` following the same Go distroless pattern at `services/ws-server/Dockerfile`
- [ ] T052 [P] Write `services/scrape-orchestrator/Dockerfile` at `services/scrape-orchestrator/Dockerfile`
- [ ] T053 [P] Write `services/proxy-manager/Dockerfile` at `services/proxy-manager/Dockerfile`
- [ ] T054 [P] Write `services/alert-engine/Dockerfile` at `services/alert-engine/Dockerfile`
- [ ] T055 [P] Write `services/alert-dispatcher/Dockerfile` at `services/alert-dispatcher/Dockerfile`

### Python Dockerfiles (python:3.12-slim builder and runtime)

- [ ] T056 [P] Write `services/spider-workers/Dockerfile`: stage 1 `python:3.12-slim` — install `uv`, `COPY pyproject.toml`, `COPY ../../libs/common libs/common`, `uv sync --no-dev`; stage 2 `python:3.12-slim` — copy venv and source, `CMD ["python", "main.py"]` at `services/spider-workers/Dockerfile`
- [ ] T057 [P] Write `services/pipeline/Dockerfile` following the same Python slim pattern at `services/pipeline/Dockerfile`
- [ ] T058 [P] Write `services/ml/Dockerfile` at `services/ml/Dockerfile`
- [ ] T059 [P] Write `services/ai-chat/Dockerfile` at `services/ai-chat/Dockerfile`

### Frontend Dockerfile (node:22-alpine, Next.js standalone)

- [ ] T060 Write `frontend/Dockerfile`: stage 1 `node:22-alpine` — `npm ci`, `npm run build` (standalone output); stage 2 `node:22-alpine` — copy `.next/standalone`, `.next/static`, `public`; `CMD ["node", "server.js"]` at `frontend/Dockerfile`

### Makefile docker-build-all Target

- [ ] T061 Implement `Makefile` `docker-build-all` target: loop over `GO_SERVICES` and `PYTHON_SERVICES` running `docker build -t $(REGISTRY)/$$s:$(TAG) services/$$s/`; build frontend image `$(REGISTRY)/frontend:$(TAG)`; note build context must be repo root for Go services (to include `go.work` and `libs/pkg`) at `Makefile`

**Checkpoint**: `make docker-build-all` exits 0. `docker images | grep estategap` shows all 11 images. `docker inspect` confirms sizes.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T062 Validate repo structure: run `tree -L 3` and confirm output matches the tree in `plan.md`; fix any missing directories at repo root
- [ ] T063 [P] Verify `go.work` contains `use` directives for all 6 Go service directories and `libs/pkg` (7 entries total) at `go.work`
- [ ] T064 [P] Add `[tool.uv.sources]` path dependency block to each Python service `pyproject.toml` pointing to `../../libs/common` with `editable = true` (verify T028–T031 included this correctly) at each `services/*/pyproject.toml`
- [ ] T065 [P] Create `libs/common/estategap_common/proto/__init__.py` placeholder so Python proto stub directory is a valid package (needed before `make proto` runs in CI) at `libs/common/estategap_common/proto/__init__.py`
- [ ] T066 [P] Create `libs/pkg/proto/.gitkeep` so the Go proto output directory exists before first `buf generate` run; add a `//go:generate buf generate` comment in `libs/pkg/logger/logger.go` at `libs/pkg/proto/.gitkeep`
- [ ] T067 Run end-to-end validation: `make proto && make build-all && make test && make lint && helm lint helm/estategap/ && make docker-build-all`; fix any failures found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — blocks all service work
- **Phase 3 (US1)**: Depends on Phase 2 — Go services import `libs/pkg`; Python services declare `libs/common` dependency
- **Phase 4 (US2)**: Depends on Phase 2 — proto generated stubs land in `libs/pkg/proto/` and `libs/common/.../proto/`
- **Phase 5 (US3)**: Depends on Phase 3 and Phase 4 — CI pipelines test both build and proto generation
- **Phase 6 (US4)**: Depends on Phase 3 — Dockerfiles reference service source created in US1
- **Phase 7 (Polish)**: Depends on all phases — final validation

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) — no dependency on US2, US3, or US4
- **US2 (P2)**: Can start after Foundational (Phase 2) — independent of US1 (proto stubs live in libs/, not in service cmd/)
- **US3 (P3)**: Requires US1 and US2 complete (CI tests both build and proto)
- **US4 (P4)**: Requires US1 complete (Dockerfiles build the service scaffolds)

### Within Each Phase

- For Go services (T022–T027): all are [P] once Phase 2 completes
- For Python services (T028–T031): all are [P] once Phase 2 completes
- For proto files (T039–T043): all are [P] once buf config (T037, T038) is written
- For Go Dockerfiles (T051–T055): all are [P] once api-gateway Dockerfile pattern is established (T050)
- For CI workflows (T047–T049): all are [P] once ci-go.yml is written (T046)

---

## Parallel Execution Example: Phase 2 (Foundational)

```bash
# After T006 (libs/pkg go.mod):
Launch in parallel:
  T007: "Create libs/pkg/logger/logger.go"
  T008: "Create libs/pkg/config/config.go"
  T009: "Create libs/pkg/natsutil/natsutil.go"
  T010: "Create libs/pkg/grpcutil/grpcutil.go"

# After T012 (libs/common pyproject.toml):
Launch in parallel:
  T013: "Create models/listing.py"
  T014: "Create models/zone.py"
  T015: "Create models/alert.py"
  T016: "Create models/scoring.py"
  T017: "Create models/conversation.py"
  T018: "Create nats_client.py"
  T019: "Create db.py"
  T020: "Create logging.py"
```

## Parallel Execution Example: Phase 3 (US1 — Go + Python Services)

```bash
# After Phase 2 checkpoint:
Launch in parallel:
  T022: "Scaffold api-gateway"
  T023: "Scaffold ws-server"
  T024: "Scaffold scrape-orchestrator"
  T025: "Scaffold proxy-manager"
  T026: "Scaffold alert-engine"
  T027: "Scaffold alert-dispatcher"
  T028: "Scaffold spider-workers"
  T029: "Scaffold pipeline"
  T030: "Scaffold ml"
  T031: "Scaffold ai-chat"
  T032: "Scaffold frontend"
  T036: "Helm chart scaffold"
```

## Parallel Execution Example: Phase 4 (US2 — Proto Files)

```bash
# After T037 + T038 (buf config):
Launch in parallel:
  T039: "Write common.proto"
  T040: "Write listings.proto"
  T041: "Write ai_chat.proto"
  T042: "Write ml_scoring.proto"
  T043: "Write proxy.proto"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational (T006–T021)
3. Complete Phase 3: US1 (T022–T036)
4. **STOP and VALIDATE**: `make build-all && make test && make lint` all pass
5. Monorepo is structurally complete and buildable

### Incremental Delivery

1. Phase 1 + Phase 2 → Shared libraries ready
2. Phase 3 (US1) → All services scaffold, `make build-all/test/lint` green → MVP ✅
3. Phase 4 (US2) → Proto contracts defined and generated, `make proto` green
4. Phase 5 (US3) → CI pipelines passing on GitHub Actions
5. Phase 6 (US4) → All Docker images built and within size targets
6. Phase 7 → Final end-to-end validation

### Total Task Count

| Phase | Tasks | Parallelizable |
|-------|-------|---------------|
| Phase 1: Setup | 5 | 3 |
| Phase 2: Foundational | 16 | 12 |
| Phase 3: US1 | 15 | 12 |
| Phase 4: US2 | 9 | 5 |
| Phase 5: US3 | 4 | 3 |
| Phase 6: US4 | 12 | 10 |
| Phase 7: Polish | 6 | 4 |
| **Total** | **67** | **49 (73%)** |

---

## Notes

- Go service Dockerfiles must use repo root as build context (pass `-f services/<name>/Dockerfile .` from repo root) so `go.work` and `libs/pkg` are accessible to the multi-stage build
- Python service Dockerfiles must `COPY libs/common libs/common` explicitly since each service's build context is the service directory — use `docker build --build-arg LIBS_PATH=../../libs/common` or use repo root as context
- `go.work` must be updated atomically with each new Go service scaffold (T022–T027) — never leave a service directory without a corresponding `use` entry
- All `cmd/main.go` files must be valid Go (package main, func main()) — empty `main()` is sufficient for the scaffold phase
- Python `main.py` files must be importable without errors for `mypy --strict` to pass — `if __name__ == "__main__": pass` is sufficient
