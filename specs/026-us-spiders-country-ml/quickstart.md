# Quickstart: US Spiders & Country-Specific ML Models

**Feature**: 026-us-spiders-country-ml  
**Date**: 2026-04-17

---

## Prerequisites

- Docker / K8s cluster with existing EstateGap services running
- Residential US proxy credentials configured in `PROXY_US_URL` env var (Zillow only)
- `uv` for Python dependency management
- Access to MinIO with `ml-models/` bucket and existing Spain champion model at `ml-models/es/champion/`

---

## 1. Run a US Spider (Development)

```bash
cd services/spider-workers

# Install deps
uv sync

# Run Zillow spider for NYC ZIP codes (dry-run — publishes to NATS but skips proxies)
PROXY_US_URL="" NATS_URL=nats://localhost:4222 \
  python -m estategap_spiders.runner \
    --country US --portal zillow \
    --zones 10001,10002,10003 \
    --dry-run

# Run Redfin spider (no proxy needed)
NATS_URL=nats://localhost:4222 \
  python -m estategap_spiders.runner \
    --country US --portal redfin \
    --zones 10001,10002,10003

# Run Realtor.com spider
NATS_URL=nats://localhost:4222 \
  python -m estategap_spiders.runner \
    --country US --portal realtor_com \
    --zones 10001,10002,10003
```

---

## 2. Import US Zone Boundaries

```bash
cd services/pipeline

# Import New York state (for development)
uv run python -m estategap_pipeline.zone_import.us_tiger \
    --level state county city zipcode \
    --state-fips 36 \
    --database-url postgresql://user:pass@localhost/estategap

# Full US import (all 50 states — takes ~20 minutes)
uv run python -m estategap_pipeline.zone_import.us_tiger \
    --level state county city zipcode neighbourhood \
    --state-fips all \
    --database-url postgresql://user:pass@localhost/estategap
```

---

## 3. Train Country-Specific ML Models

```bash
cd services/ml

# Train a single country
uv run python -m estategap_ml.trainer --country us

# Train all active countries
uv run python -m estategap_ml.trainer --countries-all

# Check model inventory in MLflow
mlflow ui --backend-store-uri postgresql://user:pass@localhost/mlflow
# Open: http://localhost:5000
```

---

## 4. Verify sqft → m² Conversion

```bash
cd services/spider-workers
uv run python -c "
from estategap_spiders.spiders.us_utils import sqft_to_m2
tests = [(1000, 92.90), (500, 46.45), (2500, 232.26)]
for sqft, expected_m2 in tests:
    result = sqft_to_m2(sqft)
    assert abs(result - expected_m2) <= 0.01, f'{sqft} sqft → {result} m² (expected {expected_m2})'
    print(f'✓ {sqft} sqft = {result} m²')
print('All conversions verified.')
"
```

---

## 5. Run Database Migration

```bash
cd services/pipeline

# Apply migration for new US listing columns
uv run alembic upgrade head

# Verify
uv run alembic current
```

---

## 6. Validate Scorer Multi-Country Dispatch

```bash
cd services/ml

# Score a synthetic US listing
uv run python -c "
from estategap_ml.scorer.client import score_listing_sync
result = score_listing_sync({
    'country': 'US',
    'area_m2': 92.9,
    'bedrooms': 2,
    'bathrooms': 1.0,
    'zone_id': 1,
    'hoa_fees_monthly_usd': 50000,   # cents
})
print(f'scoring_method: {result.scoring_method}')
print(f'confidence: {result.model_confidence}')
print(f'estimated_price_eur: {result.estimated_price_eur / 100:.2f}')
"
```

---

## 7. Run Tests

```bash
# Spider unit tests (mocked HTTP)
cd services/spider-workers
uv run pytest tests/spiders/test_us_zillow.py tests/spiders/test_us_redfin.py tests/spiders/test_us_realtor.py -v

# sqft conversion test
uv run pytest tests/spiders/test_us_utils.py -v

# ML trainer tests
cd services/ml
uv run pytest tests/trainer/ -v

# Transfer learning test (uses fixture Spain model)
uv run pytest tests/trainer/test_transfer_learning.py -v
```

---

## Configuration Reference

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `PROXY_US_URL` | Residential US proxy URL for Zillow | *(required for Zillow)* |
| `ZILLOW_RATE_LIMIT_SECONDS` | Seconds between Zillow requests | `3.0` |
| `REDFIN_RATE_LIMIT_SECONDS` | Seconds between Redfin requests | `2.0` |
| `ML_TRANSFER_MIN_LISTINGS` | Threshold below which transfer learning is used | `5000` |
| `ML_TRANSFER_MAPE_MAX` | MAPE threshold above which heuristic fallback is triggered | `0.20` |
| `ML_TRANSFER_BASE_COUNTRY` | Base country for transfer learning | `ES` |
| `MINIO_ML_BUCKET` | MinIO bucket for model artefacts | `ml-models` |
