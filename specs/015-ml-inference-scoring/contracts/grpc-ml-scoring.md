# Contract: gRPC ML Scoring Service

**File**: `proto/estategap/v1/ml_scoring.proto`
**Date**: 2026-04-17
**Feature**: 015-ml-inference-scoring
**Change type**: Backward-compatible extension of existing proto (new fields in existing messages)

---

## Updated Proto Definition

```protobuf
syntax = "proto3";

package estategap.v1;

import "estategap/v1/common.proto";
import "estategap/v1/listings.proto";

option go_package = "github.com/estategap/libs/proto/estategap/v1;estategapv1";

service MLScoringService {
  // On-demand scoring for a single listing (< 100ms)
  rpc ScoreListing(ScoreListingRequest) returns (ScoreListingResponse);

  // Batch scoring for up to 500 listing IDs at once
  rpc ScoreBatch(ScoreBatchRequest) returns (ScoreBatchResponse);

  // Find 5 comparable listings in the same zone
  rpc GetComparables(GetComparablesRequest) returns (GetComparablesResponse);
}

// ── ScoreListing ────────────────────────────────────────────────────────────

message ScoreListingRequest {
  string listing_id   = 1;
  string country_code = 2;
}

message ScoreListingResponse {
  string listing_id         = 1;
  float  deal_score         = 2;  // (estimated - asking) / estimated * 100
  repeated ShapValue shap_values = 3;
  string model_version      = 4;
  // NEW fields (015-ml-inference-scoring):
  float  estimated_price    = 5;  // EUR, point estimate
  float  asking_price       = 6;  // EUR, from listing record
  float  confidence_low     = 7;  // EUR, q05 quantile model
  float  confidence_high    = 8;  // EUR, q95 quantile model
  int32  deal_tier          = 9;  // 1=great 2=good 3=fair 4=overpriced
  string scored_at          = 10; // RFC3339 timestamp
}

message ShapValue {
  string feature_name  = 1;
  float  value         = 2;   // raw feature value (e.g., 4800.0 for zone price/m²)
  float  contribution  = 3;   // SHAP value in EUR
  // NEW field (015-ml-inference-scoring):
  string label         = 4;   // human-readable explanation (e.g., "Zone median price of 4,800€/m² pushes estimate up")
}

// ── ScoreBatch ──────────────────────────────────────────────────────────────

message ScoreBatchRequest {
  repeated string listing_ids = 1;
  string country_code         = 2;
}

message ScoreBatchResponse {
  repeated ScoreListingResponse scores = 1;
}

// ── GetComparables ──────────────────────────────────────────────────────────

message GetComparablesRequest {
  string listing_id   = 1;
  string country_code = 2;
  int32  limit        = 3;  // default 5, max 10
}

message GetComparablesResponse {
  repeated Listing comparables = 1;
  // NEW field (015-ml-inference-scoring):
  repeated float distances     = 2;  // Euclidean distance in normalised feature space, parallel to comparables
}
```

---

## Field Additions Summary

| Message | Field | Number | Type | Notes |
|---------|-------|--------|------|-------|
| `ScoreListingResponse` | `estimated_price` | 5 | `float` | EUR point estimate |
| `ScoreListingResponse` | `asking_price` | 6 | `float` | EUR asking price from listing |
| `ScoreListingResponse` | `confidence_low` | 7 | `float` | EUR, q05 |
| `ScoreListingResponse` | `confidence_high` | 8 | `float` | EUR, q95 |
| `ScoreListingResponse` | `deal_tier` | 9 | `int32` | 1–4 |
| `ScoreListingResponse` | `scored_at` | 10 | `string` | RFC3339 |
| `ShapValue` | `label` | 4 | `string` | human-readable explanation |
| `GetComparablesResponse` | `distances` | 2 | `repeated float` | parallel to `comparables` |

All additions use new field numbers — no existing field renumbering. Proto3 compatibility is preserved (new fields default to zero/empty if not set by older producers).

---

## Error Codes

| Status | Condition |
|--------|-----------|
| `OK` | Scoring succeeded |
| `NOT_FOUND` | `listing_id` not found in `listings` table |
| `FAILED_PRECONDITION` | No active model loaded for `country_code` |
| `INVALID_ARGUMENT` | `listing_id` is not a valid UUID; `country_code` is not 2 chars |
| `INTERNAL` | ONNX inference error or DB write failure after 3 retries |
| `RESOURCE_EXHAUSTED` | `ScoreBatch` called with > 500 listing IDs |

---

## Performance Targets

| RPC | P50 latency | P99 latency |
|-----|-------------|-------------|
| `ScoreListing` | < 15ms | < 100ms |
| `ScoreBatch` (100 listings) | < 1.5s | < 3s |
| `GetComparables` | < 10ms | < 50ms |

---

## Buf Generation

```bash
# From repo root
buf generate
# Generates:
#   proto/gen/go/estategap/v1/ml_scoring.pb.go
#   proto/gen/go/estategap/v1/ml_scoring_grpc.pb.go
#   services/ml/proto/estategap/v1/ml_scoring_pb2.py
#   services/ml/proto/estategap/v1/ml_scoring_pb2_grpc.py
```
