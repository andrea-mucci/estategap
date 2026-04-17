# Data Model: ML Inference & Scoring

**Phase**: 1 — Design
**Date**: 2026-04-17
**Feature**: specs/015-ml-inference-scoring

---

## Entities

### 1. `listings` Table — New Scoring Columns (migration 017)

The existing `listings` table (partitioned by `country_code`) gains scoring columns written by the scorer service after each inference pass. All new columns are nullable; a `NULL` value means the listing has not been scored yet.

```sql
-- Migration: services/pipeline/alembic/versions/017_listings_scoring_columns.py
ALTER TABLE listings ADD COLUMN IF NOT EXISTS estimated_price_eur  NUMERIC(14, 2);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS deal_score            NUMERIC(6, 2);   -- (est-ask)/est*100
ALTER TABLE listings ADD COLUMN IF NOT EXISTS deal_tier             SMALLINT;        -- 1=great 2=good 3=fair 4=overpriced
ALTER TABLE listings ADD COLUMN IF NOT EXISTS confidence_low_eur    NUMERIC(14, 2);  -- q05 model
ALTER TABLE listings ADD COLUMN IF NOT EXISTS confidence_high_eur   NUMERIC(14, 2);  -- q95 model
ALTER TABLE listings ADD COLUMN IF NOT EXISTS model_version         VARCHAR(100);    -- version_tag FK ref
ALTER TABLE listings ADD COLUMN IF NOT EXISTS scored_at             TIMESTAMPTZ;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS shap_features         JSONB NOT NULL DEFAULT '[]';
ALTER TABLE listings ADD COLUMN IF NOT EXISTS comparable_ids        UUID[];

CREATE INDEX listings_deal_tier_idx  ON listings (deal_tier)  WHERE deal_tier  IS NOT NULL;
CREATE INDEX listings_scored_at_idx  ON listings (scored_at)  WHERE scored_at  IS NOT NULL;
```

**`shap_features` JSONB schema** (array of up to 5 objects, ordered by |shap_value| descending):
```json
[
  {
    "feature":    "zone_median_price_m2",
    "value":      4800.0,
    "shap_value": 15000.0,
    "label":      "Zone median price of 4,800€/m² pushes estimate up"
  },
  {
    "feature":    "built_area_m2",
    "value":      85.0,
    "shap_value": -8200.0,
    "label":      "85m² built area pulls estimate down"
  }
]
```

**DB write pattern** (scorer → asyncpg):
```sql
UPDATE listings
SET
    estimated_price_eur = $1,
    deal_score          = $2,
    deal_tier           = $3,
    confidence_low_eur  = $4,
    confidence_high_eur = $5,
    model_version       = $6,
    scored_at           = $7,
    shap_features       = $8::jsonb,
    comparable_ids      = $9::uuid[]
WHERE id = $10
  AND country_code = $11;  -- partition pruning
```

**Batch write**: `executemany()` via asyncpg with a list of tuples, flushed every 50 messages or every 5 seconds (whichever comes first).

---

### 2. `model_versions` Table — Read-Only from Scorer

Defined in feature 014. The scorer reads this table to:
- Load the active model on startup.
- Poll for new active versions every 60 seconds (hot-reload).

Relevant columns the scorer reads:
```sql
SELECT
    version_tag,
    artifact_path,    -- points to {version_tag}.onnx in MinIO
    country_code,
    status,
    feature_names,
    trained_at
FROM model_versions
WHERE status = 'active'
ORDER BY country_code, trained_at DESC;
```

The scorer derives artefact paths by convention:
| Artefact | Path |
|----------|------|
| Main ONNX (point estimate) | `artifact_path` (from `model_versions`) |
| Lower bound ONNX (q05) | `artifact_path.replace('.onnx', '_q05.onnx')` |
| Upper bound ONNX (q95) | `artifact_path.replace('.onnx', '_q95.onnx')` |
| LightGBM text model (SHAP) | `artifact_path.replace('.onnx', '.lgb')` |
| FeatureEngineer (joblib) | `artifact_path.replace('.onnx', '_feature_engineer.joblib')` |

---

### 3. In-Memory: `ModelBundle`

Not persisted. One instance per active country.

```python
@dataclass
class ModelBundle:
    country_code:     str
    version_tag:      str
    session_point:    ort.InferenceSession   # point estimate
    session_q05:      ort.InferenceSession   # lower bound
    session_q95:      ort.InferenceSession   # upper bound
    lgb_booster:      lgb.Booster            # for SHAP
    feature_engineer: FeatureEngineer        # for transform()
    input_name:       str                    # ONNX input tensor name
    feature_names:    list[str]              # ordered, for SHAP indexing
    loaded_at:        datetime
```

**Memory footprint per bundle** (estimated):
- 3 × ONNX sessions: ~150 MB
- LightGBM booster: ~30 MB
- FeatureEngineer (with zone stats): ~10–50 MB
- **Total per country**: ~190–230 MB

With 3 countries in memory simultaneously: ~600–700 MB — within the 4 GB pod limit.

---

### 4. In-Memory: `ZoneIndex`

Not persisted. One instance per zone that has ≥ 2 active listings.

```python
@dataclass
class ZoneIndex:
    zone_id:     UUID
    nn:          NearestNeighbors           # fitted sklearn estimator
    scaler:      StandardScaler             # fitted on zone feature matrix
    listing_ids: list[UUID]                 # row order matches nn's training matrix
    built_at:    datetime                   # when this index was last refreshed
```

**Global store**:
```python
_zone_indices: dict[UUID, ZoneIndex] = {}  # refreshed hourly
```

---

### 5. NATS Event Payloads

#### `scored.listings` (published after each successful scoring)

Subject: `scored.listings`
Producer: scorer service
Consumers: alert-engine, websocket-server, analytics pipeline

```json
{
  "listing_id":           "550e8400-e29b-41d4-a716-446655440000",
  "country_code":         "es",
  "estimated_price_eur":  245000.00,
  "deal_score":           18.5,
  "deal_tier":            1,
  "confidence_low_eur":   210000.00,
  "confidence_high_eur":  280000.00,
  "model_version":        "es_national_v12",
  "scored_at":            "2026-04-17T14:32:10Z",
  "shap_features": [
    {
      "feature":    "zone_median_price_m2",
      "value":      4800.0,
      "shap_value": 15000.0,
      "label":      "Zone median price of 4,800€/m² pushes estimate up"
    }
  ]
}
```

**Pydantic model**: `ScoredListingEvent` added to `estategap_common/models/scoring.py`.

---

### 6. gRPC Proto Extension

The existing `ml_scoring.proto` is extended. See `contracts/grpc-ml-scoring.md` for the full annotated diff. Key changes:

- `ScoreListingResponse`: gains `confidence_low`, `confidence_high`, `deal_tier`, `estimated_price`, `asking_price`.
- `ShapValue`: gains `label` (human-readable string) and `value` (raw feature value).
- `GetComparablesResponse`: gains `distances` parallel array.

---

### 7. Prometheus Metrics

Exported at `:9091/metrics` (or pushed to Pushgateway) by the scorer:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `scorer_inference_duration_seconds` | Histogram | `country`, `mode` (batch/ondemand) | End-to-end time from feature transform to DB write |
| `scorer_batch_size` | Histogram | `country` | Number of listings per NATS micro-batch |
| `scorer_active_model_version` | Gauge | `country` | Currently loaded model version (label value) |
| `scorer_shap_errors_total` | Counter | `country` | SHAP computations that timed out or failed |
| `scorer_comparables_cache_hit_ratio` | Gauge | — | Fraction of GetComparables calls served from warm cache |
| `scorer_model_reload_total` | Counter | `country` | Hot-reload events triggered |
