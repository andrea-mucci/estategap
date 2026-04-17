# Implementation Plan: ML Inference & Scoring

**Branch**: `015-ml-inference-scoring` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/015-ml-inference-scoring/spec.md`

## Summary

Build the ML scorer service — a Python gRPC server that loads ONNX models per country from MinIO, consumes NATS `enriched.listings` events for batch scoring, and exposes `ScoreListing` / `ScoreBatch` / `GetComparables` RPCs for on-demand use. The scorer writes estimated price, deal score, deal tier, 90% confidence interval, top-5 SHAP feature explanations, and comparable listing IDs back to PostgreSQL and publishes to `scored.listings`. Models are hot-reloaded every 60 seconds when a new active version is detected; KNN zone indices for comparables are refreshed hourly.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: onnxruntime 1.18+, shap 0.45+, scikit-learn 1.5+, lightgbm 4.3+, grpcio 1.63+, grpcio-tools 1.63+, nats-py 2.6+, asyncpg 0.29+, boto3 1.34+, pydantic-settings 2.2+, structlog 24.x, prometheus-client 0.20+, estategap-common
**Storage**: PostgreSQL 16 + PostGIS 3.4 (`listings` table — write scoring columns); MinIO (ONNX + joblib + LGB artefacts read-only)
**Testing**: pytest + pytest-asyncio; grpc testing via `grpc.aio` channel; testcontainers for PostgreSQL
**Target Platform**: Linux server (Kubernetes pod — `services/ml/` container)
**Project Type**: gRPC microservice + NATS consumer
**Performance Goals**: < 100ms per single listing (ScoreListing RPC); < 3s for batch of 100
**Constraints**: No service restart for model updates; SHAP only for Tier 1–2; KNN cache refreshed hourly
**Scale/Scope**: ~10k–100k active listings per country; 1 scorer pod per deployment; up to 3 model bundles in memory simultaneously (es, pt, it)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Status | Notes |
|-----------|-------------|--------|-------|
| I. Polyglot Service Architecture | Python for ML/inference workload | ✅ PASS | Scorer is Python, co-located in `services/ml/` |
| I. Single deployable unit | No cross-service internal imports | ✅ PASS | Scorer imports only `estategap-common` from `libs/` |
| II. NATS for async events | Batch consume from `enriched.listings`, publish to `scored.listings` | ✅ PASS | Uses nats-py JetStream |
| II. gRPC for synchronous calls | `ScoreListing`, `ScoreBatch`, `GetComparables` via Protobuf | ✅ PASS | Proto already defined in `proto/estategap/v1/ml_scoring.proto` |
| II. No direct HTTP between services | Scorer does not call any service via REST | ✅ PASS | Only PostgreSQL + MinIO + NATS + gRPC |
| III. Country-first data | Models loaded per `country_code`; all queries scoped by country | ✅ PASS | `dict[country_code] → ModelBundle` |
| IV. ONNX for inference | Point estimate + q05 + q95 via ONNX Runtime | ✅ PASS | LightGBM `.txt` kept only for SHAP |
| IV. SHAP explainability | SHAP values accompany every Tier 1–2 deal score | ✅ PASS | TreeExplainer on LGB model |
| V. Pydantic v2, structlog, ruff, mypy strict | Already enforced in `services/ml/pyproject.toml` | ✅ PASS | No relaxations needed |
| V. pytest + pytest-asyncio | Tests use existing test infrastructure | ✅ PASS | |
| VI. No secrets in code | NATS URL, DB URL, MinIO creds via env vars + Sealed Secrets | ✅ PASS | |
| VII. Containerised, Helm-managed | `services/ml/Dockerfile` already exists; Helm chart updated | ✅ PASS | |

**Gate result**: All principles satisfied. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/015-ml-inference-scoring/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── grpc-ml-scoring.md
│   └── nats-events.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
services/ml/
├── Dockerfile                          # existing — updated CMD for scorer mode
├── pyproject.toml                      # existing — grpcio + grpcio-tools added
├── main.py                             # existing — updated to route trainer vs scorer
├── estategap_ml/
│   ├── config.py                       # existing — scorer env vars added
│   ├── features/                       # existing — reused as-is
│   │   ├── engineer.py
│   │   ├── zone_stats.py
│   │   └── ...
│   ├── trainer/                        # existing — unchanged
│   └── scorer/                         # NEW
│       ├── __init__.py
│       ├── __main__.py                 # entry point: python -m estategap_ml.scorer
│       ├── server.py                   # gRPC server lifecycle (grpc.aio)
│       ├── servicer.py                 # MLScoringServicer implementation
│       ├── model_registry.py           # ModelBundle loading + hot-reload loop
│       ├── inference.py                # ONNX inference + deal score/tier calc
│       ├── shap_explainer.py           # SHAP TreeExplainer + label rendering
│       ├── comparables.py              # KNN zone index + GetComparables logic
│       ├── nats_consumer.py            # enriched.listings JetStream consumer
│       ├── db_writer.py                # asyncpg UPDATE listings + scoring cols
│       └── feature_labels.py           # feature_name → human-readable template map
├── proto/                              # generated stubs (via buf)
│   └── estategap/v1/
│       ├── ml_scoring_pb2.py
│       └── ml_scoring_pb2_grpc.py
└── tests/
    ├── unit/
    │   ├── test_inference.py           # deal_score / deal_tier calc
    │   ├── test_shap_explainer.py      # label rendering
    │   └── test_comparables.py         # KNN logic
    ├── integration/
    │   ├── test_scorer_grpc.py         # ScoreListing / ScoreBatch / GetComparables
    │   └── test_nats_consumer.py       # end-to-end batch scoring flow
    └── acceptance/
        └── test_scoring_e2e.py         # known test listing expected values
```

**Structure Decision**: Scorer is a submodule (`estategap_ml/scorer/`) within the existing `services/ml/` Python package. This avoids a separate service container, reuses the FeatureEngineer from training, and shares the existing `pyproject.toml` dependency manifest. The gRPC server runs in a separate entry point (`python -m estategap_ml.scorer`) distinct from the trainer CronJob entry point.
