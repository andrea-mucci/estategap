# Quickstart: ML Inference & Scoring

**Date**: 2026-04-17
**Feature**: 015-ml-inference-scoring

---

## Prerequisites

- Python 3.12 + `uv`
- PostgreSQL 16 running locally (or port-forward to staging)
- MinIO accessible with a trained model artefact in `estategap-models` bucket
- NATS server running locally (or port-forward)
- An active model registered in `model_versions` table (run the trainer first)
- `buf` installed for proto code generation

---

## Generate gRPC Stubs

```bash
# From repo root — regenerate after proto changes
buf generate

# Verify Python stubs exist
ls services/ml/proto/estategap/v1/
# ml_scoring_pb2.py  ml_scoring_pb2_grpc.py  ...
```

---

## Run the Database Migration

```bash
# From services/pipeline (migrations are co-located there)
cd services/pipeline
uv run alembic upgrade head
# Applies migration 017_listings_scoring_columns.py
# Adds: estimated_price_eur, deal_score, deal_tier, confidence_low_eur,
#        confidence_high_eur, model_version, scored_at, shap_features, comparable_ids
```

---

## Local Environment Setup

```bash
cd services/ml

uv sync  # picks up new grpcio + grpcio-tools deps

cp .env.example .env
# Edit .env — add scorer-specific vars:
#   GRPC_PORT=50051
#   SCORER_BATCH_SIZE=50
#   SCORER_BATCH_FLUSH_SECONDS=5
#   MODEL_POLL_INTERVAL_SECONDS=60
#   COMPARABLES_REFRESH_INTERVAL_SECONDS=3600
#   LOG_LEVEL=DEBUG
```

---

## Run the Scorer Locally

```bash
cd services/ml

# Start the scorer (gRPC server + NATS consumer + background tasks)
uv run python -m estategap_ml.scorer

# Expected startup output:
# [INFO] Loading active models from model_versions...
# [INFO] Downloading es_national_v12.onnx from MinIO...
# [INFO] ModelBundle loaded: country=es version=es_national_v12
# [INFO] gRPC server listening on [::]:50051
# [INFO] NATS consumer started: enriched.listings (durable: scorer-group)
# [INFO] KNN zone index refresh scheduled (hourly)
```

---

## Test On-Demand Scoring via gRPC

```bash
# Using grpcurl (install: brew install grpcurl)
grpcurl -plaintext \
  -d '{"listing_id": "<uuid>", "country_code": "es"}' \
  localhost:50051 \
  estategap.v1.MLScoringService/ScoreListing

# Expected response:
# {
#   "listingId": "<uuid>",
#   "dealScore": 18.5,
#   "estimatedPrice": 245000.0,
#   "askingPrice": 199500.0,
#   "confidenceLow": 210000.0,
#   "confidenceHigh": 280000.0,
#   "dealTier": 1,
#   "modelVersion": "es_national_v12",
#   "shapValues": [
#     {
#       "featureName": "zone_median_price_m2",
#       "value": 4800.0,
#       "contribution": 15000.0,
#       "label": "Zone median price of 4,800€/m² pushes estimate up"
#     },
#     ...
#   ]
# }
```

---

## Trigger Batch Scoring (NATS)

```bash
# Publish a synthetic enriched listing event to trigger batch scoring
cd services/ml

uv run python -c "
import asyncio, json, nats
from datetime import UTC, datetime
from uuid import uuid4

async def main():
    nc = await nats.connect('nats://localhost:4222')
    js = nc.jetstream()
    payload = json.dumps({
        'id': str(uuid4()),
        'country': 'es',
        'asking_price_eur': 199500,
        'built_area_m2': 85,
        'city': 'Madrid',
        'property_type': 'apartment',
        'listed_at': datetime.now(UTC).isoformat(),
        # ... other required fields
    }).encode()
    await js.publish('enriched.listings', payload)
    print('Published enriched listing event')
    await nc.drain()

asyncio.run(main())
"

# Check DB for scoring result:
psql \$DATABASE_URL -c \
  "SELECT id, deal_tier, deal_score, estimated_price_eur, model_version, scored_at
   FROM listings WHERE scored_at IS NOT NULL ORDER BY scored_at DESC LIMIT 5;"
```

---

## Test Comparables

```bash
grpcurl -plaintext \
  -d '{"listing_id": "<uuid>", "country_code": "es", "limit": 5}' \
  localhost:50051 \
  estategap.v1.MLScoringService/GetComparables
```

---

## Run Tests

```bash
cd services/ml

# Unit tests (no external deps)
uv run pytest tests/unit/ -v -k "scorer"

# Integration tests (PostgreSQL + MinIO + NATS via testcontainers)
uv run pytest tests/integration/test_scorer_grpc.py -v

# Acceptance tests (known listing expected deal scores)
uv run pytest tests/acceptance/test_scoring_e2e.py -v -s
```

---

## Test Hot-Reload

```bash
# While scorer is running locally, simulate a new model promotion:
psql $DATABASE_URL -c "
  INSERT INTO model_versions (
    country_code, algorithm, version_tag, artifact_path, status, trained_at, created_at
  ) VALUES (
    'es', 'lightgbm', 'es_national_v99',
    'models/es_national_v99.onnx', 'staging', NOW(), NOW()
  );
  UPDATE model_versions SET status='retired' WHERE country_code='es' AND status='active';
  UPDATE model_versions SET status='active', promoted_at=NOW()
    WHERE version_tag='es_national_v99';
"

# (requires the actual ONNX files to exist in MinIO at that path)
# Within 60 seconds, scorer logs:
# [INFO] Hot-reloaded model: country=es old=es_national_v12 new=es_national_v99
```

---

## Deploy to Kubernetes

```bash
# Build scorer image
docker build -t estategap/ml-scorer:latest services/ml/ \
  --build-arg SERVICE_MODE=scorer

# Seal scorer secrets
kubectl create secret generic ml-scorer-secrets \
  --namespace estategap-system \
  --from-literal=DATABASE_URL='postgresql://app:<password>@estategap-postgres-rw...' \
  --from-literal=NATS_URL='nats://nats.estategap-system.svc.cluster.local:4222' \
  --from-literal=MINIO_ENDPOINT='http://minio.estategap-system.svc.cluster.local:9000' \
  --from-literal=MINIO_ACCESS_KEY='<key>' \
  --from-literal=MINIO_SECRET_KEY='<secret>' \
  --dry-run=client -o yaml | kubeseal --cert pub-cert.pem --format yaml

# Deploy via Helm
helm upgrade --install estategap helm/estategap \
  --namespace estategap-system \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml
```

---

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | required | PostgreSQL DSN (read/write) |
| `NATS_URL` | required | NATS JetStream URL |
| `MINIO_ENDPOINT` | required | MinIO host:port |
| `MINIO_ACCESS_KEY` | required | MinIO access key |
| `MINIO_SECRET_KEY` | required | MinIO secret key (Sealed Secret in k8s) |
| `MINIO_BUCKET` | `estategap-models` | Bucket containing model artefacts |
| `GRPC_PORT` | `50051` | gRPC server port |
| `SCORER_BATCH_SIZE` | `50` | Max listings per NATS micro-batch |
| `SCORER_BATCH_FLUSH_SECONDS` | `5` | Flush micro-batch after N seconds |
| `MODEL_POLL_INTERVAL_SECONDS` | `60` | Hot-reload polling interval |
| `COMPARABLES_REFRESH_INTERVAL_SECONDS` | `3600` | KNN index refresh interval |
| `SHAP_TIMEOUT_SECONDS` | `2` | SHAP computation timeout per listing |
| `LOG_LEVEL` | `INFO` | structlog log level |
| `PROMETHEUS_PORT` | `9091` | Prometheus metrics server port |
