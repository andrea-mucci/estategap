# Proto Contracts: EstateGap v1

**Feature**: 002-monorepo-foundation  
**Proto package**: `estategap.v1`  
**Go import prefix**: `github.com/estategap/libs/proto/estategap/v1`  
**Python import prefix**: `estategap.v1`

---

## common.proto

Shared message types used across all services.

```proto
syntax = "proto3";
package estategap.v1;

// Timestamp — ISO 8601 epoch millis
message Timestamp {
  int64 millis = 1;
}

// Money — amount in smallest currency unit (e.g. cents), with ISO 4217 currency code
message Money {
  int64 amount = 1;           // e.g. 150000 for €1,500.00
  string currency_code = 2;   // e.g. "EUR", "USD"
  int64 eur_amount = 3;       // EUR-normalized amount (constitution §III)
}

// GeoPoint — WGS84 coordinates
message GeoPoint {
  double latitude = 1;
  double longitude = 2;
}

// PaginationRequest
message PaginationRequest {
  int32 page = 1;       // 1-indexed
  int32 page_size = 2;  // max 100
}

// PaginationResponse
message PaginationResponse {
  int32 total_count = 1;
  int32 page = 2;
  int32 page_size = 3;
  bool has_next = 4;
}
```

---

## listings.proto

Internal listing types — shared across services via proto stubs.

```proto
syntax = "proto3";
package estategap.v1;

import "estategap/v1/common.proto";

enum ListingStatus {
  LISTING_STATUS_UNSPECIFIED = 0;
  LISTING_STATUS_ACTIVE = 1;
  LISTING_STATUS_SOLD = 2;
  LISTING_STATUS_RENTED = 3;
  LISTING_STATUS_WITHDRAWN = 4;
}

enum ListingType {
  LISTING_TYPE_UNSPECIFIED = 0;
  LISTING_TYPE_SALE = 1;
  LISTING_TYPE_RENT = 2;
}

enum PropertyType {
  PROPERTY_TYPE_UNSPECIFIED = 0;
  PROPERTY_TYPE_RESIDENTIAL = 1;
  PROPERTY_TYPE_COMMERCIAL = 2;
  PROPERTY_TYPE_INDUSTRIAL = 3;
  PROPERTY_TYPE_LAND = 4;
}

message Listing {
  string id = 1;
  string portal_id = 2;        // Source portal identifier
  string country_code = 3;     // ISO 3166-1 alpha-2
  ListingStatus status = 4;
  ListingType listing_type = 5;
  PropertyType property_type = 6;
  Money price = 7;
  float area_sqm = 8;          // Area in m² (constitution §III)
  GeoPoint location = 9;
  Timestamp created_at = 10;
  Timestamp updated_at = 11;
}
```

---

## ai_chat.proto

AIChatService for conversational property search with streaming.

```proto
syntax = "proto3";
package estategap.v1;

import "estategap/v1/common.proto";

service AIChatService {
  // Bidirectional streaming chat — client sends messages, server streams response chunks
  rpc Chat(stream ChatRequest) returns (stream ChatResponse);

  rpc GetConversation(GetConversationRequest) returns (GetConversationResponse);
  rpc ListConversations(ListConversationsRequest) returns (ListConversationsResponse);
}

message ChatRequest {
  string conversation_id = 1;  // Empty to start new conversation
  string user_message = 2;
  string country_code = 3;
}

message ChatResponse {
  string conversation_id = 1;
  string chunk = 2;            // Streaming text chunk
  bool is_final = 3;
  repeated string listing_ids = 4;  // Referenced listings (on final chunk)
}

message GetConversationRequest {
  string conversation_id = 1;
}

message GetConversationResponse {
  string conversation_id = 1;
  repeated ConversationTurn turns = 2;
  Timestamp created_at = 3;
}

message ConversationTurn {
  string role = 1;   // "user" or "assistant"
  string content = 2;
  Timestamp timestamp = 3;
}

message ListConversationsRequest {
  string user_id = 1;
  PaginationRequest pagination = 2;
}

message ListConversationsResponse {
  repeated ConversationSummary conversations = 1;
  PaginationResponse pagination = 2;
}

message ConversationSummary {
  string conversation_id = 1;
  string preview = 2;
  Timestamp created_at = 3;
}
```

---

## ml_scoring.proto

MLScoringService for deal scoring and comparable property lookup.

```proto
syntax = "proto3";
package estategap.v1;

import "estategap/v1/common.proto";
import "estategap/v1/listings.proto";

service MLScoringService {
  rpc ScoreListing(ScoreListingRequest) returns (ScoreListingResponse);
  rpc ScoreBatch(ScoreBatchRequest) returns (ScoreBatchResponse);
  rpc GetComparables(GetComparablesRequest) returns (GetComparablesResponse);
}

message ScoreListingRequest {
  string listing_id = 1;
  string country_code = 2;
}

message ScoreListingResponse {
  string listing_id = 1;
  float deal_score = 2;          // 0.0–1.0, higher is better deal
  repeated ShapValue shap_values = 3;
  string model_version = 4;
}

message ShapValue {
  string feature_name = 1;
  float value = 2;
  float contribution = 3;        // SHAP contribution to deal_score
}

message ScoreBatchRequest {
  repeated string listing_ids = 1;
  string country_code = 2;
}

message ScoreBatchResponse {
  repeated ScoreListingResponse scores = 1;
}

message GetComparablesRequest {
  string listing_id = 1;
  string country_code = 2;
  int32 limit = 3;               // Default 10, max 50
}

message GetComparablesResponse {
  repeated Listing comparables = 1;
}
```

---

## proxy.proto

ProxyService for geo-targeted proxy management.

```proto
syntax = "proto3";
package estategap.v1;

service ProxyService {
  rpc GetProxy(GetProxyRequest) returns (GetProxyResponse);
  rpc ReportResult(ReportResultRequest) returns (ReportResultResponse);
}

message GetProxyRequest {
  string country_code = 1;   // ISO 3166-1 alpha-2
  string portal_id = 2;      // Helps select portal-appropriate proxy
}

message GetProxyResponse {
  string proxy_url = 1;      // Format: http://user:pass@host:port
  string proxy_id = 2;       // Opaque identifier for result reporting
}

message ReportResultRequest {
  string proxy_id = 1;
  bool success = 2;
  int32 status_code = 3;
  int64 latency_ms = 4;
}

message ReportResultResponse {
  bool acknowledged = 1;
}
```

---

## buf Configuration

### buf.yaml (at `proto/`)

```yaml
version: v2
modules:
  - path: .
    name: buf.build/estategap/estategap
lint:
  use:
    - DEFAULT
breaking:
  use:
    - FILE
```

### buf.gen.yaml (at repo root)

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
      - require_unimplemented_servers=false
  - remote: buf.build/protocolbuffers/python
    out: libs/common/proto
  - remote: buf.build/grpc/python
    out: libs/common/proto
```
