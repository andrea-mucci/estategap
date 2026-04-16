# Tasks: Monorepo Foundation

**Input**: Design documents from `/specs/002-monorepo-foundation/`
**Prerequisites**: plan.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: No dedicated test tasks — the acceptance criteria for this feature are build/lint/CI green on the empty codebase. Test infrastructure (pytest placeholders, go test stubs) is created as part of service scaffolding.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-progress tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- **[x]**: Already implemented and verified

---

## Phase 1: Setup (Shared Scaffolding)

**Purpose**: Root-level files and shared directory structure. No dependencies.

- [x] T001 Create all top-level directories: `services/`, `proto/estategap/v1/`, `libs/pkg/`, `libs/common/estategap_common/models/`, `frontend/`, `helm/estategap/templates/`, `.github/workflows/`
- [x] T002 [P] Write `.gitignore` covering Go binaries, Python `.venv`/`__pycache__`/`.mypy_cache`/`.ruff_cache`, Node `node_modules`, proto stubs pattern (`*.pb.go`, `*_pb2*.py`), `.env`, Docker build artifacts
- [x] T003 [P] Write `.golangci.yml` enabling: `errcheck`, `gosimple`, `govet`, `staticcheck`, `unused`, `gofmt`, `goimports`, `misspell`; set `run.timeout: 5m`; exclude `internal/` `.gitkeep` files
- [x] T004 [P] Write `helm/estategap/Chart.yaml` (apiVersion: v2, name: estategap, type: application, version: 0.1.0, appVersion: "0.1.0", description: "EstateGap platform Helm chart")
- [x] T005 [P] Write `helm/estategap/values.yaml` with top-level stub keys: `global: {}`, `services: {}`, `frontend: {}`
- [x] T006 [P] Write `helm/estategap/templates/_helpers.tpl` with standard helpers: `estategap.name`, `estategap.fullname`, `estategap.chart`, `estategap.labels`, `estategap.selectorLabels`

**Checkpoint**: Directory skeleton exists. Root config files committed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared Go library, shared Python library, and Go workspace file. All user stories depend on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Go Shared Library (`libs/pkg`)

- [x] T007 Write `libs/pkg/go.mod` with module `github.com/estategap/libs`, Go 1.23, deps: `github.com/spf13/viper`, `github.com/nats-io/nats.go`, `google.golang.org/grpc`, `google.golang.org/protobuf`
- [x] T008 [P] Write `libs/pkg/logger/logger.go` — slog-based JSON logger: `New(level string) *slog.Logger`, `WithContext(ctx context.Context) *slog.Logger`, `ToContext(ctx, log) context.Context`
- [x] T009 [P] Write `libs/pkg/config/config.go` — viper-based loader: `Load(prefix string) (*viper.Viper, error)` reads env vars with `AutomaticEnv()` and optional K8s ConfigMap path from `CONFIG_PATH` env var
- [x] T010 [P] Write `libs/pkg/natsutil/natsutil.go` — NATS JetStream helpers: `Connect(url string) (*nats.Conn, error)`, `EnsureStream(js nats.JetStreamContext, cfg *nats.StreamConfig) error`
- [x] T011 [P] Write `libs/pkg/grpcutil/grpcutil.go` — gRPC dialer: `Dial(target string, opts ...grpc.DialOption) (*grpc.ClientConn, error)` with exponential backoff, plus `CircuitBreaker` struct with `NewCircuitBreaker(threshold int)`, `RecordSuccess()`, `RecordFailure() bool`, `IsOpen() bool`

### Python Shared Library (`libs/common`)

- [x] T012 Write `libs/common/pyproject.toml` — package `estategap-common`, version `0.1.0`, Python `>=3.12`, hatchling build backend, deps: `pydantic>=2`, `nats-py[nkeys]>=2`, `asyncpg>=0.29`, `structlog>=24`, `grpcio>=1.62`, `grpcio-tools>=1.62`; dev extras: `pytest`, `pytest-asyncio`, `mypy`, `ruff`, `mypy-protobuf`
- [x] T013 [P] Write `libs/common/estategap_common/__init__.py` (empty)
- [x] T014 [P] Write `libs/common/estategap_common/models/__init__.py` (empty)
- [x] T015 [P] Write `libs/common/estategap_common/models/listing.py` — `ListingType(str, Enum)`, `ListingStatus(str, Enum)`, `RawListing(BaseModel)`, `Listing(BaseModel)` with id, external_id, portal, country_code, listing_type, status, price (Decimal), currency_code, price_eur, area_sqm, latitude, longitude, zone_id, created_at, updated_at
- [x] T016 [P] Write `libs/common/estategap_common/models/zone.py` — `Zone(BaseModel)` with id, name, country_code, geometry (dict), parent_id (Optional[str])
- [x] T017 [P] Write `libs/common/estategap_common/models/alert.py` — `AlertRule(BaseModel)` with id, user_id, country_code, filters (dict), notification_channels (list[str])
- [x] T018 [P] Write `libs/common/estategap_common/models/scoring.py` — `ShapValue(BaseModel)` with feature_name, value (float), contribution (float); `ScoringResult(BaseModel)` with listing_id, deal_score (float 0–1), shap_values (list[ShapValue]), model_version (str)
- [x] T019 [P] Write `libs/common/estategap_common/models/conversation.py` — `ChatMessage(BaseModel)` with role (str), content (str), timestamp (datetime); `ConversationState(BaseModel)` with conversation_id, turns (list[ChatMessage]), country_code
- [x] T020 [P] Write `libs/common/estategap_common/nats_client.py` — async context-manager `NatsClient` wrapping `nats-py` JetStream: `connect(url)`, `publish(subject, payload)`, `subscribe(subject, cb)`
- [x] T021 [P] Write `libs/common/estategap_common/db.py` — `create_pool(dsn: str) -> asyncpg.Pool` async factory
- [x] T022 [P] Write `libs/common/estategap_common/logging.py` — `configure_logging(level: str = "INFO")` sets up structlog with JSON renderer and stdlib integration

### Go Workspace

- [x] T023 Write `go.work` at repo root: `go 1.23`, `use` block listing `./libs/pkg`, `./services/api-gateway`, `./services/ws-server`, `./services/scrape-orchestrator`, `./services/proxy-manager`, `./services/alert-engine`, `./services/alert-dispatcher`

**Checkpoint**: `cd libs/pkg && go build ./...` succeeds. `cd libs/common && uv sync` succeeds. `go.work` exists.

---

## Phase 3: User Story 1 — Developer Bootstraps New Service (Priority: P1) 🎯 MVP

**Goal**: Developer clones repo, runs `make build-all` and `make lint` from root — all services compile and lint clean.

**Independent Test**: `make build-all` exits 0; `make lint` exits 0; `make test` exits 0.

### Go Service Scaffolds

- [x] T024 [P] [US1] Scaffold `services/api-gateway/`: `go.mod` (module `github.com/estategap/services/api-gateway`, Go 1.23), `cmd/main.go` (`package main; func main() {}`), `internal/handler/.gitkeep`, `internal/middleware/.gitkeep`, `internal/config/.gitkeep`, `internal/grpc/.gitkeep`
- [x] T025 [P] [US1] Scaffold `services/ws-server/`: same structure, module `github.com/estategap/services/ws-server`
- [x] T026 [P] [US1] Scaffold `services/scrape-orchestrator/`: same structure, module `github.com/estategap/services/scrape-orchestrator`
- [x] T027 [P] [US1] Scaffold `services/proxy-manager/`: same structure, module `github.com/estategap/services/proxy-manager`
- [x] T028 [P] [US1] Scaffold `services/alert-engine/`: same structure, module `github.com/estategap/services/alert-engine`
- [x] T029 [P] [US1] Scaffold `services/alert-dispatcher/`: same structure, module `github.com/estategap/services/alert-dispatcher`

### Python Service Scaffolds

- [x] T030 [P] [US1] Scaffold `services/spider-workers/`: write `pyproject.toml` (name `estategap-spiders`, Python `>=3.12`, hatchling, deps: `scrapy>=2.11`, `playwright>=1.43`; `[tool.uv.sources] estategap-common = {path = "../../libs/common", editable = true}`; dev deps: `pytest`, `pytest-asyncio`, `mypy`, `ruff`), write `main.py` (async `main()` stub), write `estategap_spiders/__init__.py`, write `estategap_spiders/py.typed`, write `tests/__init__.py`, write `tests/conftest.py` (empty)
- [x] T031 [P] [US1] Scaffold `services/pipeline/`: write `pyproject.toml` (name `estategap-pipeline`, deps: `httpx>=0.27`; same uv.sources and dev deps pattern as T030), write `main.py`, write `estategap_pipeline/__init__.py`, write `estategap_pipeline/py.typed`, write `tests/__init__.py`, write `tests/conftest.py`
- [x] T032 [P] [US1] Scaffold `services/ml/`: write `pyproject.toml` (name `estategap-ml`, deps: `lightgbm>=4.3`, `onnxruntime>=1.18`, `shap>=0.45`; same uv.sources and dev deps pattern), write `main.py`, write `estategap_ml/__init__.py`, write `estategap_ml/py.typed`, write `tests/__init__.py`, write `tests/conftest.py`
- [x] T033 [P] [US1] Scaffold `services/ai-chat/`: write `pyproject.toml` (name `estategap-ai-chat`, deps: `litellm>=1.35`, `fastapi>=0.111`, `uvicorn>=0.30`; same uv.sources and dev deps pattern), write `main.py`, write `estategap_ai_chat/__init__.py`, write `estategap_ai_chat/py.typed`, write `tests/__init__.py`, write `tests/conftest.py`

### Frontend Scaffold

- [x] T034 [US1] Scaffold `frontend/`: write `package.json` (name `estategap-frontend`, private: true, scripts: `dev: "next dev"`, `build: "next build"`, `lint: "next lint"`, `typecheck: "tsc --noEmit"`, deps: `next@15`, `react@19`, `react-dom@19`, devDeps: `typescript@5`, `@types/react@19`, `@types/node@22`, `eslint`, `eslint-config-next`); write `tsconfig.json` (strict: true, target: ES2022, lib: ["dom","es2022"], moduleResolution: bundler, jsx: preserve, incremental: true, paths: {"@/*": ["./src/*"]}); write `next.config.ts` (`output: 'standalone'`, no other config); write `src/app/layout.tsx` (root layout with `<html lang="en"><body>{children}</body></html>`); write `src/app/page.tsx` (returns `<main><h1>EstateGap</h1></main>`)

### Root Makefile

- [x] T035 [US1] Write root `Makefile` replacing the existing stub with real implementations:
  - `REGISTRY ?= ghcr.io/estategap`, `TAG ?= dev`
  - `GO_SERVICES := api-gateway ws-server scrape-orchestrator proxy-manager alert-engine alert-dispatcher`
  - `PYTHON_SERVICES := spider-workers pipeline ml ai-chat`
  - `proto`: `buf generate`
  - `test`: `go test ./...` + loop `cd services/$$svc && uv run pytest -x` per Python service
  - `lint`: `golangci-lint run ./...` + `buf lint` + loop `cd services/$$svc && uv run ruff check . && uv run mypy --strict .` per Python service + `cd frontend && npm run lint`
  - `build-all`: loop `cd services/$$svc && go build ./cmd` per Go service + loop `cd services/$$svc && uv sync` per Python service + `cd frontend && npm ci && npm run build`
  - `docker-build-all`: loop `docker build -t $(REGISTRY)/$$svc:$(TAG) -f services/$$svc/Dockerfile .` per service + `docker build -t $(REGISTRY)/frontend:$(TAG) -f frontend/Dockerfile .`
  - Add `py.typed` to `libs/common/estategap_common/py.typed` (empty marker file)

**Checkpoint**: `make build-all` exits 0. `make test` exits 0. `make lint` exits 0.

---

## Phase 4: User Story 2 — Developer Generates Proto Stubs (Priority: P2)

**Goal**: `make proto` regenerates Go and Python stubs from `.proto` files. CI verifies no diff.

**Independent Test**: Run `make proto`; verify files appear in `libs/pkg/proto/estategap/v1/` and `libs/common/proto/estategap/v1/`; `git diff --exit-code` exits 0 (stubs committed).

### Proto Definitions

- [x] T036 [US2] Write `proto/buf.yaml` — buf v2 config: `version: v2`, `modules: [{path: ., name: buf.build/estategap/estategap}]`, `lint: {use: [DEFAULT]}`, `breaking: {use: [FILE]}`
- [x] T037 [P] [US2] Write `proto/estategap/v1/common.proto` — `syntax = "proto3"`, `package estategap.v1`, `option go_package = "github.com/estategap/libs/proto/estategap/v1;estategapv1"`, messages: `Timestamp {int64 millis = 1}`, `Money {int64 amount = 1; string currency_code = 2; int64 eur_amount = 3}`, `GeoPoint {double latitude = 1; double longitude = 2}`, `PaginationRequest {int32 page = 1; int32 page_size = 2}`, `PaginationResponse {int32 total_count = 1; int32 page = 2; int32 page_size = 3; bool has_next = 4}`
- [x] T038 [P] [US2] Write `proto/estategap/v1/listings.proto` — `syntax = "proto3"`, `package estategap.v1`, import `common.proto`, enums: `ListingStatus` (UNSPECIFIED/ACTIVE/SOLD/RENTED/WITHDRAWN with LISTING_STATUS_ prefix), `ListingType` (UNSPECIFIED/SALE/RENT with LISTING_TYPE_ prefix), `PropertyType` (UNSPECIFIED/RESIDENTIAL/COMMERCIAL/INDUSTRIAL/LAND with PROPERTY_TYPE_ prefix); `message Listing` with all fields matching data-model.md (id, portal_id, country_code, status, listing_type, property_type, price Money, area_sqm float, location GeoPoint, created_at Timestamp, updated_at Timestamp)
- [x] T039 [P] [US2] Write `proto/estategap/v1/ai_chat.proto` — `AIChatService`: `rpc Chat(stream ChatRequest) returns (stream ChatResponse)`, `rpc GetConversation(GetConversationRequest) returns (GetConversationResponse)`, `rpc ListConversations(ListConversationsRequest) returns (ListConversationsResponse)`; all request/response messages per contracts/proto-contracts.md
- [x] T040 [P] [US2] Write `proto/estategap/v1/ml_scoring.proto` — `MLScoringService`: `rpc ScoreListing`, `rpc ScoreBatch`, `rpc GetComparables`; all messages per contracts/proto-contracts.md including `ShapValue` with feature_name, value (float), contribution (float)
- [x] T041 [P] [US2] Write `proto/estategap/v1/proxy.proto` — `ProxyService`: `rpc GetProxy(GetProxyRequest) returns (GetProxyResponse)`, `rpc ReportResult(ReportResultRequest) returns (ReportResultResponse)`; messages per contracts/proto-contracts.md

### Buf Generation Config & Run

- [x] T042 [US2] Write `buf.gen.yaml` at repo root — `version: v2`, `inputs: [{directory: proto}]`, plugins: `buf.build/protocolbuffers/go` → `libs/pkg/proto` (paths=source_relative), `buf.build/grpc/go` → `libs/pkg/proto` (paths=source_relative, require_unimplemented_servers=false), `buf.build/protocolbuffers/python` → `libs/common/proto`, `buf.build/grpc/python` → `libs/common/proto`
- [ ] T043 [US2] Run `buf generate` from repo root to produce Go stubs in `libs/pkg/proto/estategap/v1/` and Python stubs in `libs/common/proto/estategap/v1/`; verify generated files exist; commit all generated stubs; verify Go workspace can import `github.com/estategap/libs/proto/estategap/v1` by adding a blank import test in `libs/pkg/go.mod`

**Checkpoint**: `make proto` exits 0. `buf lint` exits 0. Generated stubs exist and are committed.

---

## Phase 5: User Story 3 — CI Pipeline Validates on PR (Priority: P3)

**Goal**: Four GitHub Actions workflows run lint + test + build for all languages on every push/PR to `main` and `002-monorepo-foundation`. All pass on the empty codebase.

**Independent Test**: Push to branch; verify all four workflow runs show green in GitHub Actions.

- [x] T044 [P] [US3] Write `.github/workflows/ci-go.yml` — trigger: `push`/`pull_request` to `[main, 002-monorepo-foundation]`; jobs: `lint` (golangci-lint-action@v6, Go 1.23, `go.work` present), `test` (`go test ./...`), `build` (matrix over `[api-gateway, ws-server, scrape-orchestrator, proxy-manager, alert-engine, alert-dispatcher]`, step: `go build ./cmd` in `services/${{ matrix.service }}`); all jobs use `actions/setup-go@v5` with `cache: true`
- [x] T045 [P] [US3] Write `.github/workflows/ci-python.yml` — trigger: `push`/`pull_request` to `[main, 002-monorepo-foundation]`; jobs: `lint-typecheck` and `test`, both matrix over `[spider-workers, pipeline, ml, ai-chat]`; steps: `astral-sh/setup-uv@v4`, `uv sync` in `services/${{ matrix.service }}`, `uv run ruff check .`, `uv run mypy --strict .` (lint job), `uv run pytest -x` (test job)
- [x] T046 [P] [US3] Write `.github/workflows/ci-frontend.yml` — trigger: `push`/`pull_request` to `[main, 002-monorepo-foundation]`; single job `lint-typecheck-build`; steps: `actions/setup-node@v4` (node 22, cache: npm), `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build`; working-directory: `frontend`
- [x] T047 [P] [US3] Write `.github/workflows/ci-proto.yml` — trigger: `push`/`pull_request` to `[main, 002-monorepo-foundation]`; single job `lint-and-verify`; steps: `bufbuild/buf-setup-action@v1`, `buf lint`, `buf generate`, `git diff --exit-code` (fails if stubs differ from committed)

**Checkpoint**: All 4 workflows run successfully in GitHub Actions. No failures on empty codebase.

---

## Phase 6: User Story 4 — Multi-Stage Docker Images (Priority: P4)

**Goal**: Every service has a Dockerfile producing a minimal image meeting size targets.

**Independent Test**: `make docker-build-all` exits 0; `docker images | grep estategap` shows Go images < 20 MB, Python < 200 MB, frontend < 100 MB.

### Go Service Dockerfiles (distroless, target < 20 MB)

- [x] T048 [P] [US4] Write `services/api-gateway/Dockerfile` — Stage 1 (`FROM golang:1.23-alpine AS builder`): `WORKDIR /build`, `COPY go.work go.work.sum ./`, `COPY libs/pkg libs/pkg`, `COPY services/api-gateway services/api-gateway`, `RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app ./services/api-gateway/cmd`; Stage 2 (`FROM gcr.io/distroless/static:nonroot`): `COPY --from=builder /app /app`, `USER nonroot:nonroot`, `ENTRYPOINT ["/app"]`
- [x] T049 [P] [US4] Write `services/ws-server/Dockerfile` — same pattern as T048, update service path to `services/ws-server`
- [x] T050 [P] [US4] Write `services/scrape-orchestrator/Dockerfile` — same pattern, path `services/scrape-orchestrator`
- [x] T051 [P] [US4] Write `services/proxy-manager/Dockerfile` — same pattern, path `services/proxy-manager`
- [x] T052 [P] [US4] Write `services/alert-engine/Dockerfile` — same pattern, path `services/alert-engine`
- [x] T053 [P] [US4] Write `services/alert-dispatcher/Dockerfile` — same pattern, path `services/alert-dispatcher`

### Python Service Dockerfiles (python:3.12-slim, target < 200 MB)

- [x] T054 [P] [US4] Write `services/spider-workers/Dockerfile` — Stage 1 (`FROM python:3.12-slim AS builder`): install uv (`pip install uv --no-cache-dir`), `COPY libs/common /libs/common`, `COPY services/spider-workers /app`, `WORKDIR /app`, `RUN uv sync --no-dev`; Stage 2 (`FROM python:3.12-slim`): `COPY --from=builder /app/.venv /app/.venv`, `COPY --from=builder /app /app`, `WORKDIR /app`, `ENV PATH="/app/.venv/bin:$PATH"`, `CMD ["python", "main.py"]`
- [x] T055 [P] [US4] Write `services/pipeline/Dockerfile` — same pattern as T054, path `services/pipeline`
- [x] T056 [P] [US4] Write `services/ml/Dockerfile` — same pattern, path `services/ml`
- [x] T057 [P] [US4] Write `services/ai-chat/Dockerfile` — same pattern, path `services/ai-chat`

### Frontend Dockerfile (node:22-alpine standalone, target < 100 MB)

- [x] T058 [US4] Write `frontend/Dockerfile` — Stage 1 (`FROM node:22-alpine AS deps`): `WORKDIR /app`, `COPY package.json package-lock.json* ./`, `RUN npm ci`; Stage 2 (`FROM node:22-alpine AS builder`): `WORKDIR /app`, `COPY --from=deps /app/node_modules ./node_modules`, `COPY . .`, `RUN npm run build`; Stage 3 (`FROM node:22-alpine AS runner`): `ENV NODE_ENV=production`, `WORKDIR /app`, `RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs`, `COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./`, `COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static`, `USER nextjs`, `EXPOSE 3000`, `ENV PORT=3000`, `CMD ["node", "server.js"]`

**Checkpoint**: `make docker-build-all` exits 0. All images meet size targets.

---

## Phase 7: Polish & Validation

**Purpose**: End-to-end validation of all acceptance criteria and cross-cutting cleanup.

- [x] T059 [P] Add `libs/common/estategap_common/py.typed` empty marker file (enables mypy --strict to resolve the package)
- [x] T060 [P] Add `.env.example` to each of the 4 Python services (`services/spider-workers/.env.example`, `services/pipeline/.env.example`, `services/ml/.env.example`, `services/ai-chat/.env.example`) with commented placeholder vars
- [x] T061 Verify `go build ./...` succeeds workspace-wide: run from repo root with `go.work` present; confirms all 6 Go service `go.mod` files resolve correctly via workspace
- [ ] T062 Verify `uv sync` succeeds independently in each of the 4 Python service directories; confirm `estategap-common` installs as editable path dep in each
- [x] T063 Validate `tree -L 3` output matches plan.md project structure exactly — all 10 service directories, `proto/`, `libs/`, `frontend/`, `helm/`, `.github/workflows/` present
- [ ] T064 Validate full quickstart.md flow: `make proto` → `make build-all` → `make test` → `make lint` all exit 0 from a clean checkout
- [ ] T065 Verify `buf lint` exits 0 and `buf generate` produces no diff against committed stubs

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)         → no deps, start immediately
Phase 2 (Foundational)  → depends on Phase 1
Phase 3 (US1)           → depends on Phase 2
Phase 4 (US2)           → depends on Phase 2 + Phase 3 (Makefile proto target)
Phase 5 (US3)           → depends on Phase 3 + Phase 4 (CI needs working build + proto)
Phase 6 (US4)           → depends on Phase 3 (service dirs must exist for COPY in Dockerfiles)
Phase 7 (Polish)        → depends on all phases complete
```

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (Phase 2) only
- **US2 (P2)**: Depends on Phase 2 + US1 Makefile `proto` target exists (T035)
- **US3 (P3)**: Depends on US1 (build works) + US2 (proto gen works)
- **US4 (P4)**: Depends on US1 (service directory structure exists); can run in parallel with US2/US3

### Within Each Phase

- All `[P]`-marked tasks within a phase can run simultaneously
- Go service scaffolds (T024–T029): fully parallel — different directories ✅ (done)
- Python service scaffolds (T030–T033): fully parallel — different directories
- Proto files (T037–T041): fully parallel — different files
- Go Dockerfiles (T048–T053): fully parallel — different files
- Python Dockerfiles (T054–T057): fully parallel — different files
- CI workflows (T044–T047): fully parallel — different files

---

## Parallel Execution Examples

### Phase 3 US1 — run simultaneously

```
T030 services/spider-workers/ (pyproject.toml + main.py + pkg + tests)
T031 services/pipeline/       (pyproject.toml + main.py + pkg + tests)
T032 services/ml/             (pyproject.toml + main.py + pkg + tests)
T033 services/ai-chat/        (pyproject.toml + main.py + pkg + tests)
```

Then sequentially:
```
T034 frontend/ scaffold
T035 root Makefile (real implementation)
```

### Phase 4 US2 — run simultaneously

```
T037 proto/estategap/v1/common.proto
T038 proto/estategap/v1/listings.proto
T039 proto/estategap/v1/ai_chat.proto
T040 proto/estategap/v1/ml_scoring.proto
T041 proto/estategap/v1/proxy.proto
```

Then sequentially:
```
T042 buf.gen.yaml
T043 buf generate + commit stubs
```

### Phase 5 US3 — run simultaneously

```
T044 .github/workflows/ci-go.yml
T045 .github/workflows/ci-python.yml
T046 .github/workflows/ci-frontend.yml
T047 .github/workflows/ci-proto.yml
```

### Phase 6 US4 — run simultaneously

```
T048 services/api-gateway/Dockerfile
T049 services/ws-server/Dockerfile
T050 services/scrape-orchestrator/Dockerfile
T051 services/proxy-manager/Dockerfile
T052 services/alert-engine/Dockerfile
T053 services/alert-dispatcher/Dockerfile
T054 services/spider-workers/Dockerfile
T055 services/pipeline/Dockerfile
T056 services/ml/Dockerfile
T057 services/ai-chat/Dockerfile
```

Then sequentially:
```
T058 frontend/Dockerfile
```

---

## Implementation Strategy

### Current State (as of 2026-04-16)

Phase 1 (T001–T006), Phase 2 (T007–T023), Phase 3 (T024–T035), Phase 5 (T044–T047), and Phase 6 (T048–T058) are **complete**.

**Remaining work**: T043, T062, T064, and T065 require tool or network availability that was not present in the implementation environment.

### MVP Completion Path (User Story 1)

1. Complete Phase 1 remaining tasks (T002–T006) — root config files
2. Complete Python service scaffolds (T030–T033) — parallel
3. Complete Frontend scaffold (T034)
4. Complete root Makefile (T035)
5. **VALIDATE**: `make build-all` + `make lint` + `make test` all green
6. Foundation is usable — US1 acceptance criteria met

### Incremental Delivery

1. Phase 1 + Phase 2 → done (shared libs + Go services exist)
2. US1 remaining → `make build-all` works for all 10 services + frontend
3. US2 → `make proto` works, proto contracts committed
4. US3 → CI is green on every push
5. US4 → Docker images built and size-validated
6. Polish → all 6 acceptance criteria verified end-to-end

### Parallel Team Strategy

All Phase 2 foundational tasks are done. With the current state:
- **Developer A**: T030–T034 (Python services + frontend scaffold)
- **Developer B**: T002–T006 + T035 (root config files + Makefile)
- **Developer C**: T036–T043 (proto files + buf generate) — after T035 exists

---

## Notes

- All Dockerfiles **must** use repo root as build context: `docker build -f services/<name>/Dockerfile .` — required for `COPY libs/` in multi-stage builds
- Generated proto stubs (`libs/pkg/proto/`, `libs/common/proto/`) **must be committed** — not gitignored; CI verifies via `git diff --exit-code`
- `buf generate` uses remote plugins (BSR) — requires buf CLI and network access; no local `protoc` install needed
- Each Python service's `pyproject.toml` must declare: `[tool.uv.sources]\nestategap-common = {path = "../../libs/common", editable = true}`
- Go workspace resolution: `go.work` replaces the need for `replace` directives in individual `go.mod` files
- `[P]` = different files, no shared mutable state — safe to parallelize within the phase
- `[x]` = already implemented and verified via code audit (2026-04-16)
