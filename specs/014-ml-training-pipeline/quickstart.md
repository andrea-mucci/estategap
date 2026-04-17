# Quickstart: ML Training Pipeline

**Date**: 2026-04-17
**Feature**: 014-ml-training-pipeline

---

## Prerequisites

- Python 3.12 + `uv`
- PostgreSQL 16 running locally (or port-forward to staging)
- MinIO accessible (or `minio/minio` Docker container)
- MLflow Tracking Server running locally (or port-forward)

---

## Local Environment Setup

```bash
# From repo root
cd services/ml

# Install dependencies (adds new ML training deps)
uv sync

# Copy and fill environment variables
cp .env.example .env
# Edit .env:
#   DATABASE_URL=postgresql://user:pass@localhost:5432/estategap
#   MLFLOW_TRACKING_URI=http://localhost:5000
#   MINIO_ENDPOINT=localhost:9000
#   MINIO_ACCESS_KEY=minioadmin
#   MINIO_SECRET_KEY=minioadmin
#   MINIO_BUCKET=estategap-models
#   PROMOTION_MAPE_IMPROVEMENT_PCT=0.02
#   LOG_LEVEL=DEBUG
```

---

## Run the Database Migration

```bash
# From services/pipeline (migrations are co-located with pipeline service)
cd services/pipeline
uv run alembic upgrade head
# Applies migration 016_model_versions.py
```

---

## Run Feature Engineering Smoke Test

```bash
cd services/ml

# Generate a feature vector for a single listing (fetches live from DB)
uv run python -m estategap_ml.features --smoke-test --country es --limit 100

# Expected output:
# [INFO] Loaded 100 listings from DB
# [INFO] Zone stats loaded: 847 zones
# [INFO] Feature matrix shape: (100, 36) — no NaN, no Inf ✓
```

---

## Run a Training Job Locally (Dry Run)

```bash
cd services/ml

# Full pipeline: data export → feature engineering → training → evaluation
# --dry-run: skips ONNX export, MinIO upload, and DB promotion
uv run python -m estategap_ml.trainer --country es --dry-run

# Expected output:
# [INFO] Exported 12,456 training listings
# [INFO] Split: train=8719, val=1869, test=1869
# [INFO] Starting Optuna study (50 trials)...
# [INFO] Trial 1/50: MAPE=0.143
# ...
# [INFO] Best MAPE (val): 0.098, params: {num_leaves: 127, lr: 0.05, ...}
# [INFO] Test set evaluation: MAE=11200, MAPE=0.096, R²=0.883
# [INFO] [DRY RUN] Skipping ONNX export and promotion
```

---

## Run a Full Training Job Locally

```bash
cd services/ml

uv run python -m estategap_ml.trainer --country es

# On success: model promoted/rejected, NATS event published to ml.training.completed
# Check MLflow UI at http://localhost:5000 for run details
# Check MinIO at http://localhost:9001 for model artefacts
```

---

## Run Tests

```bash
cd services/ml

# Unit tests (no DB required)
uv run pytest tests/unit/ -v

# Integration tests (requires PostgreSQL + MinIO running)
uv run pytest tests/integration/ -v

# Full acceptance test (end-to-end with seeded data)
uv run pytest tests/acceptance/ -v -s
```

---

## Trigger the CronJob Manually in Kubernetes

```bash
# Create a one-off job from the CronJob spec
kubectl create job ml-training-manual-$(date +%Y%m%d) \
  --from=cronjob/ml-trainer \
  -n estategap-system

# Follow logs
kubectl logs -f job/ml-training-manual-$(date +%Y%m%d) -n estategap-system

# Check model_versions table
kubectl exec -it <pipeline-pod> -n estategap-system -- \
  psql $DATABASE_URL -c "SELECT version_tag, status, metrics->>'mape_national' AS mape FROM model_versions ORDER BY created_at DESC LIMIT 5;"
```

## Seal the Trainer Secrets

```bash
kubectl create secret generic ml-trainer-secrets \
  --namespace estategap-system \
  --from-literal=DATABASE_URL='postgresql://app:<password>@estategap-postgres-rw.estategap-system.svc.cluster.local:5432/estategap' \
  --from-literal=MLFLOW_TRACKING_URI='http://mlflow.estategap-intelligence.svc.cluster.local:5000' \
  --from-literal=NATS_URL='nats://nats.estategap-system.svc.cluster.local:4222' \
  --from-literal=MINIO_ENDPOINT='http://minio.estategap-system.svc.cluster.local:9000' \
  --from-literal=MINIO_ACCESS_KEY='<minio-access-key>' \
  --from-literal=MINIO_SECRET_KEY='<minio-secret-key>' \
  --dry-run=client -o yaml | kubeseal --cert pub-cert.pem --format yaml
```

---

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | required | PostgreSQL DSN |
| `MLFLOW_TRACKING_URI` | required | MLflow server URL |
| `MINIO_ENDPOINT` | required | MinIO host:port |
| `MINIO_ACCESS_KEY` | required | MinIO access key |
| `MINIO_SECRET_KEY` | required | MinIO secret key (sealed secret in k8s) |
| `MINIO_BUCKET` | `estategap-models` | Bucket for model artefacts |
| `PROMOTION_MAPE_IMPROVEMENT_PCT` | `0.02` | Minimum relative MAPE improvement to promote |
| `MIN_LISTINGS_PER_COUNTRY` | `5000` | Threshold for full vs transfer model |
| `OPTUNA_N_TRIALS` | `50` | Number of Optuna trials |
| `LOG_LEVEL` | `INFO` | structlog log level |
| `NATS_URL` | required | NATS JetStream URL |
