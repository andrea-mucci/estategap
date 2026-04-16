# Data Model: Monorepo Foundation

**Phase**: 1 — Design  
**Feature**: 002-monorepo-foundation  
**Date**: 2026-04-16

> Note: The monorepo foundation is infrastructure, not a data feature. This document captures the structural entities — modules, packages, contracts — that make up the foundation.

---

## Entity: Go Service Module

**What it is**: An independently compilable Go module for a single microservice.

| Field | Value |
|-------|-------|
| `go.mod` module path | `github.com/estategap/services/<name>` |
| Go version | 1.23 |
| Entry point | `cmd/main.go` — minimal `main()` |
| Internal packages | `internal/handler`, `internal/middleware`, `internal/config`, `internal/grpc` |
| Shared dep | `github.com/estategap/libs` via `go.work` |
| Build artifact | Static binary via `CGO_ENABLED=0 go build ./cmd` |

**Services** (6 total):

| Service | Module Path |
|---------|-------------|
| api-gateway | `github.com/estategap/services/api-gateway` |
| ws-server | `github.com/estategap/services/ws-server` |
| scrape-orchestrator | `github.com/estategap/services/scrape-orchestrator` |
| proxy-manager | `github.com/estategap/services/proxy-manager` |
| alert-engine | `github.com/estategap/services/alert-engine` |
| alert-dispatcher | `github.com/estategap/services/alert-dispatcher` |

---

## Entity: Go Shared Library (`libs/pkg`)

| Field | Value |
|-------|-------|
| Module path | `github.com/estategap/libs` |
| Go version | 1.23 |
| Packages | `logger`, `config`, `natsutil`, `grpcutil`, `proto/estategap/v1` |

**Package contracts**:

| Package | Exports | Key Dependencies |
|---------|---------|-----------------|
| `logger` | `New(opts) *slog.Logger`, `FromContext(ctx)`, `WithContext(ctx, log)` | stdlib `log/slog` |
| `config` | `Load(target any) error` — reads env vars + K8s ConfigMap via viper | `github.com/spf13/viper` |
| `natsutil` | `Connect(url string) (*nats.Conn, error)`, `EnsureStream(js, name, subjects)` | `github.com/nats-io/nats.go` |
| `grpcutil` | `Dial(addr string, opts...) (*grpc.ClientConn, error)` — retry + circuit breaker | `google.golang.org/grpc` |
| `proto/estategap/v1` | Generated stubs for all .proto files | `google.golang.org/protobuf` |

---

## Entity: Python Service Package

**What it is**: An independently runnable Python service managed by uv.

| Field | Value |
|-------|-------|
| `pyproject.toml` build backend | `hatchling` |
| Python version | `>=3.12` |
| Package manager | `uv` (lockfile: `uv.lock`) |
| Local dep | `estategap-common` via `tool.uv.sources` path reference |
| Entry point | `main.py` — minimal async `main()` returning immediately |
| Virtual env | `.venv/` (gitignored) |

**Services** (4 total):

| Service | Package Name | Description |
|---------|-------------|-------------|
| spider-workers | `estategap-spiders` | Scrapy + Playwright spiders |
| pipeline | `estategap-pipeline` | Data normalization, dedup, enrichment |
| ml | `estategap-ml` | LightGBM scoring + ONNX inference |
| ai-chat | `estategap-ai-chat` | LLM conversational search |

---

## Entity: Python Shared Library (`libs/common`)

| Field | Value |
|-------|-------|
| Package name | `estategap-common` |
| Version | `0.1.0` |
| Python version | `>=3.12` |

**Module contracts**:

| Module | Exports | Key Dependencies |
|--------|---------|-----------------|
| `models.listing` | `Listing`, `RawListing`, `ListingType`, `ListingStatus` | `pydantic>=2` |
| `models.zone` | `Zone` | `pydantic>=2` |
| `models.alert` | `AlertRule` | `pydantic>=2` |
| `models.scoring` | `ScoringResult`, `ShapValue` | `pydantic>=2` |
| `models.conversation` | `ConversationState`, `ChatMessage` | `pydantic>=2` |
| `nats_client` | `NatsClient` (async context manager, JetStream publish/subscribe) | `nats-py[nkeys]>=2` |
| `db` | `create_pool(dsn) -> asyncpg.Pool` | `asyncpg>=0.29` |
| `logging` | `configure_logging(level)` — structlog JSON renderer | `structlog>=24` |

---

## Entity: Protobuf Contract

**What it is**: A `.proto` file in `proto/estategap/v1/` defining a gRPC service or shared message types.

| File | Service / Messages |
|------|--------------------|
| `common.proto` | Messages: `Timestamp`, `Money`, `GeoPoint`, `PaginationRequest`, `PaginationResponse` |
| `ai_chat.proto` | Service: `AIChatService` — RPCs: `Chat` (bidi streaming), `GetConversation`, `ListConversations` |
| `ml_scoring.proto` | Service: `MLScoringService` — RPCs: `ScoreListing`, `ScoreBatch`, `GetComparables` |
| `proxy.proto` | Service: `ProxyService` — RPCs: `GetProxy`, `ReportResult` |
| `listings.proto` | Messages: `Listing`, `ListingStatus`, `ListingType`, `PropertyType` (shared internal types) |

**Generated output paths**:

| Language | Output Path |
|----------|-------------|
| Go | `libs/pkg/proto/estategap/v1/` |
| Python | `libs/common/proto/estategap/v1/` |

---

## Entity: CI Workflow

| File | Trigger | Jobs |
|------|---------|------|
| `ci-go.yml` | push/PR to main | matrix: golangci-lint, go test, go build per service |
| `ci-python.yml` | push/PR to main | matrix: ruff check, mypy --strict, pytest per service |
| `ci-frontend.yml` | push/PR to main | eslint, tsc --noEmit, next build |
| `ci-proto.yml` | push/PR to main | buf lint, buf generate, git diff check |

---

## Entity: Helm Chart Scaffold

| File | Purpose |
|------|---------|
| `helm/estategap/Chart.yaml` | Chart metadata (name, version, appVersion, type: application) |
| `helm/estategap/values.yaml` | Default values stub (empty in foundation phase) |
| `helm/estategap/templates/_helpers.tpl` | Standard name/label helpers |

---

## State Transitions

No user-facing state machines in this foundation phase. The relevant "state" is build system state:

```
[Source Code] → make proto → [Generated Stubs] → go build / uv sync → [Built Artifacts]
[Built Artifacts] → docker build → [Container Images]
[Container Images] → helm template → [K8s Manifests]
```
