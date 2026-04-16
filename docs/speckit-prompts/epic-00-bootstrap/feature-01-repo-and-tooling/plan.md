# Feature: Repository & Tooling Setup

## /plan prompt

```
Implement the monorepo and tooling setup with these technical decisions:

## Stack
- Go 1.23 with go.work workspace for multi-module monorepo
- Python 3.12 with uv as package manager. Each Python service has its own pyproject.toml.
- Protobuf with buf.gen.yaml generating Go (google.golang.org/protobuf) and Python (grpcio-tools) stubs
- Docker multi-stage builds: Go uses golang:1.23 builder → gcr.io/distroless/static. Python uses python:3.12-slim. Frontend uses node:22-alpine with Next.js standalone output.

## Proto Contracts
Define these .proto files:
- common.proto: shared types (Timestamp, Money, GeoPoint, PaginationRequest, PaginationResponse)
- ai_chat.proto: AIChatService with bidirectional streaming Chat RPC, GetConversation, ListConversations
- ml_scoring.proto: MLScoringService with ScoreListing, ScoreBatch, GetComparables
- proxy.proto: ProxyService with GetProxy, ReportResult
- listings.proto: internal listing types used across services

## Shared Libraries
- Go pkg/: logger (slog wrapper with JSON output), config (viper-based, reads env vars + K8s ConfigMaps), natsutil (NATS JetStream connection + stream creation helper), grpcutil (dial with retry + circuit breaker)
- Python libs/common/: models/ (Pydantic v2 models for Listing, RawListing, Zone, AlertRule, ScoringResult, ConversationState), nats_client.py (async NATS wrapper), db.py (asyncpg session factory), logging.py (structlog JSON config)

## CI Pipelines (GitHub Actions)
- ci-go.yml: golangci-lint, go test ./..., go build for each service
- ci-python.yml: ruff check, mypy --strict, pytest for each service
- ci-frontend.yml: eslint, tsc --noEmit, next build
- ci-proto.yml: buf lint, buf generate (verify no diff)

## File Conventions
- Each Go service: cmd/main.go, internal/ (handler, middleware, config, grpc), Dockerfile, go.mod
- Each Python service: main entrypoint, Dockerfile, pyproject.toml
- All configs from environment variables (12-factor)
```
