# Proto Contracts Overview

**Branch**: `001-monorepo-foundation` | **Date**: 2026-04-16

## Package Namespace

All proto files live under the package `estategap.v1`:

```
proto/
└── estategap/v1/
    ├── common.proto       → package estategap.v1; option go_package = "github.com/estategap/libs/proto/v1;estategapv1"
    ├── listings.proto     → package estategap.v1
    ├── ai_chat.proto      → package estategap.v1; service AIChatService
    ├── ml_scoring.proto   → package estategap.v1; service MLScoringService
    └── proxy.proto        → package estategap.v1; service ProxyService
```

## buf Configuration

### `proto/buf.yaml`
```yaml
version: v2
modules:
  - path: .
lint:
  use:
    - DEFAULT
breaking:
  use:
    - FILE
```

### `buf.gen.yaml` (repo root)
```yaml
version: v2
inputs:
  - directory: proto
plugins:
  - remote: buf.build/protocolbuffers/go
    out: libs/pkg/proto
    opt:
      - paths=source_relative
  - remote: buf.build/grpc/go
    out: libs/pkg/proto
    opt:
      - paths=source_relative
  - remote: buf.build/grpc/python
    out: libs/common/estategap_common/proto
```

## Service Contracts

### AIChatService

| RPC | Type | Request | Response |
|-----|------|---------|----------|
| `Chat` | Bidirectional streaming | `ChatMessage` | `ChatResponse` |
| `GetConversation` | Unary | `GetConversationRequest` | `Conversation` |
| `ListConversations` | Unary | `ListConversationsRequest` | `ListConversationsResponse` |

Used by: `ai-chat` service (server), `ws-server` (client for streaming responses to browser)

### MLScoringService

| RPC | Type | Request | Response |
|-----|------|---------|----------|
| `ScoreListing` | Unary | `ScoreListingRequest` | `ScoringResult` |
| `ScoreBatch` | Server streaming | `ScoreBatchRequest` | `ScoringResult` (stream) |
| `GetComparables` | Unary | `GetComparablesRequest` | `GetComparablesResponse` |

Used by: `ml` service (server), `pipeline` (client for scoring after normalization), `alert-engine` (client to check deal scores)

### ProxyService

| RPC | Type | Request | Response |
|-----|------|---------|----------|
| `GetProxy` | Unary | `GetProxyRequest` | `Proxy` |
| `ReportResult` | Unary | `ReportResultRequest` | `ReportResultResponse` |

Used by: `proxy-manager` service (server), `spider-workers` (client to acquire proxies)

## NATS JetStream Subjects

(Not proto-defined, but documented here as inter-service contracts)

| Subject | Publisher | Consumers | Payload |
|---------|-----------|-----------|---------|
| `listings.raw.{country}` | spider-workers | pipeline | `RawListing` (JSON) |
| `listings.normalized.{country}` | pipeline | alert-engine, ml | `Listing` (JSON) |
| `alerts.triggered.{country}` | alert-engine | alert-dispatcher | `AlertRule` + `Listing` |
| `ml.score.request.{country}` | pipeline | ml | `ScoreListingRequest` (JSON) |
| `ml.score.result.{country}` | ml | pipeline, alert-engine | `ScoringResult` (JSON) |
