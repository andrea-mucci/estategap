# Data Model: ML Training Pipeline

**Phase**: 1 — Design
**Date**: 2026-04-17
**Feature**: specs/014-ml-training-pipeline

---

## Entities

### 1. `model_versions` Table (new — migration 016)

Persistent registry of all trained model artefacts. One row per training run per country. Mirrors the `MlModelVersion` Pydantic model already defined in `libs/common/estategap_common/models/ml.py`.

```sql
CREATE TABLE model_versions (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code   CHAR(2)     NOT NULL,
    algorithm      VARCHAR(50) NOT NULL DEFAULT 'lightgbm',
    version_tag    VARCHAR(100) NOT NULL,        -- e.g. "es_national_v12"
    artifact_path  TEXT        NOT NULL,        -- MinIO path, e.g. "models/es_national_v12.onnx"
    dataset_ref    TEXT,                        -- snapshot identifier for reproducibility
    feature_names  JSONB       NOT NULL DEFAULT '[]',
    metrics        JSONB       NOT NULL DEFAULT '{}',
    -- metrics shape: {
    --   "mape_national": 0.094,
    --   "mae_national": 12450.0,
    --   "r2_national": 0.87,
    --   "per_city": {"Madrid": {"mape": 0.081, "mae": 9800}, ...},
    --   "n_train": 85000,
    --   "n_val": 18000,
    --   "n_test": 18000
    -- }
    status         VARCHAR(20) NOT NULL DEFAULT 'staging',  -- staging | active | retired
    trained_at     TIMESTAMPTZ NOT NULL,
    promoted_at    TIMESTAMPTZ,
    retired_at     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX model_versions_country_status
    ON model_versions (country_code, status);

CREATE UNIQUE INDEX model_versions_version_tag_unique
    ON model_versions (country_code, version_tag);
```

**Status transitions**:
```
staging  →  active   (on promotion: challenger beats champion by ≥2%)
active   →  retired  (when a new challenger is promoted)
staging  →  retired  (when challenger fails to beat champion; kept for audit)
```

**Key invariant**: At most one row per `country_code` has `status = 'active'` at any time. Enforced by the promotion transaction.

---

### 2. `zone_statistics` View / Precomputed Lookup

Not a new table — derived at training time from existing tables. The trainer queries this before calling `FeatureEngineer.fit()`:

```sql
SELECT
    z.id                           AS zone_id,
    z.country_code,
    z.level,
    z.parent_id,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.price_per_m2_eur)
                                   AS median_price_m2,
    COUNT(l.id)                    AS listing_density,
    AVG(z.avg_income_eur)          AS avg_income   -- if column exists, else NULL
FROM zones z
JOIN listings l ON l.zone_id = z.id
    AND l.status IN ('active', 'sold', 'delisted')
    AND l.created_at > NOW() - INTERVAL '12 months'
WHERE l.country = $1
GROUP BY z.id, z.country_code, z.level, z.parent_id;
```

Result is stored as `dict[UUID, ZoneStats]` inside the fitted `FeatureEngineer` (serialised with joblib alongside the ONNX model).

---

### 3. Training Dataset Export (in-memory, not persisted)

The raw training dataset is a `pandas.DataFrame` fetched via asyncpg and never written to disk. Schema of the exported columns:

| Column | Source | Notes |
|--------|--------|-------|
| `id` | listings.id | UUID |
| `country` | listings.country | CHAR(2) |
| `city` | listings.city | for stratification |
| `zone_id` | listings.zone_id | UUID, nullable |
| `lat` | ST_Y(listings.location) | float |
| `lon` | ST_X(listings.location) | float |
| `asking_price_eur` | listings.asking_price_eur | target (fallback) |
| `final_price_eur` | listings.final_price_eur | target (preferred for sold) |
| `price_per_m2_eur` | listings.price_per_m2_eur | |
| `built_area_m2` | listings.built_area_m2 | |
| `usable_area_m2` | listings.usable_area_m2 | nullable |
| `bedrooms` | listings.bedrooms | nullable int |
| `bathrooms` | listings.bathrooms | nullable int |
| `floor_number` | listings.floor_number | nullable int |
| `total_floors` | listings.total_floors | nullable int |
| `has_lift` | listings.has_lift | nullable bool |
| `parking_spaces` | listings.parking_spaces | nullable int |
| `has_terrace` | listings.has_terrace | nullable bool |
| `orientation` | listings.orientation | nullable str (N/S/E/W/NE/...) |
| `property_type` | listings.property_type | str |
| `property_category` | listings.property_category | enum |
| `energy_cert` | listings.energy_cert | nullable str (A–G) |
| `condition` | listings.condition | nullable str |
| `building_year` | listings.building_year | nullable int |
| `community_fees_eur` | listings.community_fees_eur | nullable Decimal |
| `photo_count` | listings.photo_count | nullable int |
| `days_on_market` | derived: (NOW() - listed_at) in days | int |
| `listed_at` | listings.listed_at | for month encoding |
| `status` | listings.status | for target selection |
| `dist_metro_m` | listings.dist_metro_m | nullable int (from enrichment) |
| `dist_train_m` | listings.dist_train_m | nullable int |
| `dist_beach_m` | listings.dist_beach_m | nullable int |

**Filter**: `(status IN ('sold', 'delisted') OR days_on_market > 30) AND asking_price_eur IS NOT NULL AND built_area_m2 > 0`

---

### 4. Feature Vector Schema (~35 features)

Output of `FeatureEngineer.transform()`. All values are `float32`. Named columns documented here for contract with the scorer.

#### Spatial (6)
| Feature | Derivation |
|---------|-----------|
| `lat` | listings.lat, imputed with country centroid |
| `lon` | listings.lon, imputed with country centroid |
| `dist_metro_m` | enrichment column; median-imputed |
| `dist_beach_m` | enrichment column; median-imputed |
| `zone_median_price_m2` | zone_statistics lookup; country median fallback |
| `zone_listing_density` | zone_statistics lookup; 0 fallback |

#### Physical (8)
| Feature | Derivation |
|---------|-----------|
| `built_area_m2` | required; no imputation needed (filtered) |
| `usable_area_m2` | median-imputed |
| `bedrooms` | median-imputed |
| `bathrooms` | median-imputed |
| `floor_number` | median-imputed |
| `total_floors` | median-imputed |
| `has_lift` | mode-imputed (bool → 0/1) |
| `parking_spaces` | median-imputed |

#### Condition (4)
| Feature | Derivation |
|---------|-----------|
| `energy_cert_encoded` | OrdinalEncoder: A=7, B=6, C=5, D=4, E=3, F=2, G=1; missing→0 |
| `condition_encoded` | OrdinalEncoder: new=4, good=3, renovated=2, to_renovate=1; missing→0 |
| `building_age_years` | current_year - building_year; median-imputed |
| `has_energy_cert` | 1 if energy_cert present, 0 otherwise |

#### Contextual / Property Type (4 + n_types)
| Feature | Derivation |
|---------|-----------|
| `community_fees_eur` | median-imputed |
| `property_type_*` | OneHotEncoded from property_type (apartment, house, studio, penthouse, duplex, other) |

#### Temporal (2)
| Feature | Derivation |
|---------|-----------|
| `month_sin` | sin(2π × listed_at.month / 12) |
| `month_cos` | cos(2π × listed_at.month / 12) |

#### Derived (5)
| Feature | Derivation |
|---------|-----------|
| `usable_built_ratio` | usable_area_m2 / built_area_m2; 0 if usable missing |
| `price_per_m2_eur` | asking_price_eur / built_area_m2 |
| `photo_count` | median-imputed |
| `has_photos` | 1 if photo_count > 0 |
| `data_completeness` | count of non-null optional fields / total optional fields |

**Total**: ~36 features (exact count varies with OneHot expansion of property_type).

---

### 5. NATS Event Payloads

#### `ml.training.completed`
```json
{
  "country_code": "es",
  "model_version_tag": "es_national_v12",
  "mape_national": 0.094,
  "promoted": true,
  "previous_champion_tag": "es_national_v11",
  "artifact_path": "models/es_national_v12.onnx",
  "timestamp": "2026-04-20T03:47:12Z"
}
```

#### `ml.training.failed`
```json
{
  "country_code": "es",
  "error": "asyncpg.PostgresError: connection timeout",
  "stage": "data_export",
  "timestamp": "2026-04-20T03:05:01Z"
}
```

---

### 6. FeatureEngineer Serialisation (joblib)

The fitted `FeatureEngineer` object is serialised as a separate artefact alongside the ONNX model. It contains:
- Fitted sklearn `ColumnTransformer` (all encoders + imputers)
- `zone_stats: dict[UUID, ZoneStats]` — in-memory lookup
- `feature_names_out: list[str]` — ordered output column names
- `training_dataset_ref: str` — hash/timestamp for reproducibility

Both artefacts are uploaded to MinIO:
```
models/{version_tag}.onnx
models/{version_tag}_feature_engineer.joblib
```

And the `artifact_path` in `model_versions` points to the ONNX file; the joblib path is `artifact_path.replace('.onnx', '_feature_engineer.joblib')` by convention.
