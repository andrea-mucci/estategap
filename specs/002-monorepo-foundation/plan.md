# Implementation Plan: Monorepo Foundation

**Branch**: `002-monorepo-foundation` | **Date**: 2026-04-16 | **Spec**: [spec input via /speckit.plan]  
**Input**: Feature specification — EstateGap polyglot monorepo bootstrap

## Summary

Establish a production-ready monorepo for the EstateGap platform: six Go microservices and four Python microservices, a Next.js 15 frontend, shared Go and Python libraries, Protobuf contracts via buf, multi-stage Dockerfiles meeting size targets, a root Makefile orchestrating all build/test/lint tasks, and four GitHub Actions CI pipelines. All services must compile, lint, and test clean from a fresh checkout using only `make proto && make build-all && make test && make lint`.

## Technical Context

**Language/Version**: Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend)  
**Primary Dependencies**: Go — chi, pgx, slog, viper, nats.go, grpc; Python — Pydantic v2, asyncpg, structlog, nats-py, LightGBM, Scrapy, Playwright, LiteLLM, FastAPI; Frontend — Next.js 15, Tailwind CSS 4, shadcn/ui, TanStack Query, Zustand  
**Storage**: N/A (foundation only — no runtime data layer)  
**Testing**: Go: table-driven tests (`go test`); Python: `pytest` + `pytest-asyncio`; Frontend: Vitest + React Testing Library  
**Target Platform**: Linux containers (Kubernetes), local macOS/Linux dev  
**Project Type**: Polyglot microservices monorepo  
**Performance Goals**: Go service images < 20 MB; Python service images < 200 MB; Frontend image < 100 MB; `make build-all` < 3 min  
**Constraints**: No service-to-service REST/HTTP; all inter-service communication via NATS JetStream (async) or gRPC (sync); no secrets in code  
**Scale/Scope**: 10 services + 1 frontend; 5 proto files; 4 CI workflows

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Architecture — Go for latency-sensitive, Python for ML/data, Next.js for frontend | ✅ PASS | 6 Go + 4 Python + 1 Next.js — correct split |
| I. Services independently deployable in `services/`; shared code in `libs/` | ✅ PASS | `libs/pkg` (Go) and `libs/common` (Python) are the only cross-service shared code |
| II. NATS JetStream for async; gRPC+Protobuf for sync; no inter-service REST | ✅ PASS | natsutil + grpcutil in `libs/pkg`; proto contracts in `proto/`; no REST wiring in services |
| II. All contracts in `proto/` via buf | ✅ PASS | 5 `.proto` files + buf.yaml + buf.gen.yaml |
| IV. ML layer — LightGBM + ONNX + MLflow + SHAP + LiteLLM | ✅ PASS | `estategap-ml` service scaffold includes lightgbm, onnxruntime, shap in pyproject.toml |
| V. Go — golangci-lint, slog, pgx, explicit errors, no panics | ✅ PASS | `.golangci.yml` configured; logger uses slog; no ORM |
| V. Python — Pydantic v2, asyncio+httpx, ruff+mypy strict, uv | ✅ PASS | all enforced in pyproject.toml + CI |
| V. Frontend — TypeScript strict, App Router, TanStack Query, Zustand, next-intl | ✅ PASS | tsconfig strict; App Router scaffold |
| V. buf for proto linting and generation | ✅ PASS | ci-proto.yml enforces buf lint + generate + diff |
| VI. No secrets in code (12-factor env vars) | ✅ PASS | all config from env; `.env.example` files only |
| VII. Every service containerized with Dockerfile | ✅ PASS | 10 service Dockerfiles + 1 frontend Dockerfile |
| VII. Helm charts in `helm/` | ✅ PASS | `helm/estategap/` scaffold |

**Post-design re-check**: All constitution principles satisfied. No violations. No complexity justifications needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-monorepo-foundation/
├── plan.md              ← this file
├── research.md          ← tech decisions (Go workspace, uv, buf, Docker, CI)
├── data-model.md        ← structural entities: Go modules, Python packages, proto contracts
├── quickstart.md        ← developer setup guide
├── contracts/
│   ├── proto-contracts.md   ← all 5 .proto schemas + buf config
│   └── makefile-targets.md  ← Makefile and CI workflow contracts
└── tasks.md             ← 65-task implementation plan (phases 1–7)
```

### Source Code (repository root)

```text
estategap/
├── go.work                        # Go workspace: libs/pkg + 6 services
├── go.work.sum
├── buf.gen.yaml                   # buf code generation config (root)
├── Makefile                       # proto / test / lint / build-all / docker-build-all
├── .gitignore
├── .golangci.yml
│
├── proto/
│   ├── buf.yaml                   # buf workspace config
│   └── estategap/v1/
│       ├── common.proto           # Timestamp, Money, GeoPoint, Pagination*
│       ├── listings.proto         # Listing, ListingStatus, ListingType, PropertyType
│       ├── ai_chat.proto          # AIChatService (bidi streaming Chat, GetConversation, ListConversations)
│       ├── ml_scoring.proto       # MLScoringService (ScoreListing, ScoreBatch, GetComparables)
│       └── proxy.proto            # ProxyService (GetProxy, ReportResult)
│
├── libs/
│   ├── pkg/                       # Go shared library — github.com/estategap/libs
│   │   ├── go.mod
│   │   ├── logger/logger.go       # slog JSON wrapper
│   │   ├── config/config.go       # viper env+ConfigMap loader
│   │   ├── natsutil/natsutil.go   # NATS JetStream helpers
│   │   ├── grpcutil/grpcutil.go   # gRPC dial with retry
│   │   └── proto/estategap/v1/    # Generated Go stubs (committed)
│   │
│   └── common/                    # Python shared library — estategap-common
│       ├── pyproject.toml
│       ├── uv.lock
│       └── estategap_common/
│           ├── __init__.py
│           ├── py.typed
│           ├── nats_client.py     # async NATS JetStream wrapper
│           ├── db.py              # asyncpg pool factory
│           ├── logging.py         # structlog JSON config
│           ├── proto/estategap/v1/ # Generated Python stubs (committed)
│           └── models/
│               ├── __init__.py
│               ├── listing.py     # Listing, RawListing, ListingType, ListingStatus
│               ├── zone.py        # Zone
│               ├── alert.py       # AlertRule
│               ├── scoring.py     # ScoringResult, ShapValue
│               └── conversation.py # ConversationState, ChatMessage
│
├── services/
│   ├── api-gateway/               # Go — HTTP entry point
│   │   ├── go.mod
│   │   ├── cmd/main.go
│   │   ├── internal/{handler,middleware,config,grpc}/
│   │   ├── Dockerfile
│   │   └── .env.example
│   ├── ws-server/                 # Go — WebSocket real-time
│   ├── scrape-orchestrator/       # Go — spider scheduling
│   ├── proxy-manager/             # Go — proxy pool management
│   ├── alert-engine/              # Go — deal alert detection
│   ├── alert-dispatcher/          # Go — notification delivery
│   ├── spider-workers/            # Python — Scrapy+Playwright spiders
│   │   ├── pyproject.toml
│   │   ├── main.py
│   │   ├── estategap_spiders/__init__.py
│   │   ├── tests/conftest.py
│   │   └── Dockerfile
│   ├── pipeline/                  # Python — data normalization
│   ├── ml/                        # Python — LightGBM scoring + ONNX
│   └── ai-chat/                   # Python — LLM conversational search
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json              # strict mode, moduleResolution bundler
│   ├── next.config.ts             # output: 'standalone'
│   ├── Dockerfile
│   └── src/app/
│       ├── layout.tsx
│       └── page.tsx
│
├── helm/
│   └── estategap/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/_helpers.tpl
│
└── .github/
    └── workflows/
        ├── ci-go.yml              # golangci-lint + go test + go build matrix
        ├── ci-python.yml          # ruff + mypy --strict + pytest matrix
        ├── ci-frontend.yml        # eslint + tsc --noEmit + next build
        └── ci-proto.yml           # buf lint + buf generate + git diff
```

**Structure Decision**: Polyglot monorepo (Option 2 variant) — `services/` for all microservices regardless of language, `libs/` for shared code split by language runtime, `frontend/` at root for the Next.js app. This matches the constitution §I and §VII requirements exactly.

## Complexity Tracking

> No violations — no entries required.

## Implementation Gap Analysis

*Current state as of 2026-04-16 — what exists vs. what tasks.md requires:*

| Component | Status | Notes |
|-----------|--------|-------|
| `libs/pkg/` — go.mod, logger, config, natsutil, grpcutil | ✅ Done | All 4 packages implemented |
| `libs/common/` — pyproject.toml, all 6 modules | ✅ Done | models, nats_client, db, logging |
| `go.work` — all 6 Go services | ✅ Done | Needs py.typed + tests/ for Python |
| Go services (6) — go.mod + cmd/main.go + internal/ | ✅ Done | Dockerfiles missing |
| Python services (4) — spider-workers, pipeline, ml, ai-chat | ❌ Missing | pyproject.toml, main.py, tests/ |
| `proto/estategap/v1/` — 5 .proto files | ❌ Missing | buf.yaml also missing |
| `buf.gen.yaml` | ❌ Missing | |
| Generated proto stubs (Go + Python) | ❌ Missing | Requires buf generate |
| Frontend scaffold | ❌ Missing | package.json, tsconfig, next.config, src/ |
| `helm/estategap/` — Chart.yaml, values.yaml, _helpers.tpl | ❌ Missing | |
| Dockerfiles (all 10 services + frontend) | ❌ Missing | |
| Root Makefile — real implementation | ❌ Stub | Currently echoes "not implemented" |
| `.gitignore` | ❌ Missing | Listed as untracked |
| `.golangci.yml` | ❌ Missing | Listed as untracked |
| GitHub Actions workflows (4) | ❌ Missing | `.github/workflows/` exists but empty |

**Remaining work**: Tasks T030–T065 from tasks.md (Python services, proto, buf, frontend, helm, Dockerfiles, real Makefile, CI workflows, validation).

## Key References

- **Research**: [research.md](research.md) — 9 tech decisions with rationale
- **Data Model**: [data-model.md](data-model.md) — all entities with field-level contracts
- **Proto Contracts**: [contracts/proto-contracts.md](contracts/proto-contracts.md) — full proto schemas + buf config
- **Makefile Contracts**: [contracts/makefile-targets.md](contracts/makefile-targets.md) — target contracts + CI workflow schemas
- **Quickstart**: [quickstart.md](quickstart.md) — developer onboarding guide
- **Tasks**: [tasks.md](tasks.md) — 65 tasks across 7 phases with parallelism annotations
