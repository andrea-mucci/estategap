# Research: ML Training Pipeline

**Phase**: 0 — Research & Decisions
**Date**: 2026-04-17
**Feature**: specs/014-ml-training-pipeline

---

## Decision 1: ONNX Export Strategy

**Decision**: Export the full sklearn `Pipeline` (FeatureEngineer + LightGBM) as a single ONNX graph using `skl2onnx` with the `onnxmltools` LightGBM converter backend.

**Rationale**:
- A single ONNX graph encapsulates both feature engineering and inference so the scorer never touches Python scikit-learn at inference time.
- `skl2onnx` natively handles sklearn `Pipeline`, `ColumnTransformer`, `OrdinalEncoder`, `OneHotEncoder`, and `SimpleImputer` — all components used by `FeatureEngineer`.
- The LightGBM booster is converted via `onnxmltools.convert_lightgbm()` and stitched into the pipeline by `skl2onnx`.
- Alternative (LightGBM built-in `booster.to_onnx()`) cannot include the sklearn preprocessing steps.
- Alternative (ONNX from scratch via `onnx` primitives) is prohibitively complex.
- **Self-test**: After export, run `onnxruntime.InferenceSession` on a held-out batch and assert that predictions match LightGBM's native `predict()` output within float32 tolerance.

**Packages required**:
```
skl2onnx>=1.17
onnxmltools>=1.12
onnxruntime>=1.18   # already in pyproject.toml
```

**Alternatives considered**:
- LightGBM built-in ONNX: Cannot wrap sklearn preprocessors.
- Separate ONNX for preprocessor + LightGBM: Requires inference-side stitching, breaks the scorer contract.

---

## Decision 2: Hyperparameter Optimisation Framework

**Decision**: Optuna 3.x with `MedianPruner` and SQLite study persistence (`sqlite:///optuna_study.db` inside the job's ephemeral volume). Run 50 trials; parallelism = 1 (single Kubernetes Job pod).

**Rationale**:
- Optuna integrates directly with LightGBM via `optuna.integration.lightgbm` or via manual callbacks; supports early-stopping per trial.
- `MedianPruner` prunes trials whose intermediate MAPE exceeds the median of completed trials at the same step, saving ~30–40% of trial time.
- SQLite persistence allows resuming a failed run without re-running completed trials (CronJob pod restart scenario).
- 50 trials is sufficient to explore the 6-dimensional space empirically shown in similar property valuation work.

**Search space** (as specified):
```
num_leaves:       [31, 255]  (int)
learning_rate:    [0.01, 0.3] (log-uniform float)
n_estimators:     [100, 1000] (int)
min_child_samples:[5, 100]   (int)
subsample:        [0.6, 1.0] (float)
colsample_bytree: [0.6, 1.0] (float)
```

**Fixed hyperparameters**: `boosting_type=gbdt`, `objective=regression`, `metric=mape`, `verbose=-1`, `n_jobs=-1`.

**Alternatives considered**:
- Hyperopt: No built-in pruning; less maintained.
- Ray Tune: Heavy dependency; overkill for a single-node CronJob.

---

## Decision 3: Transfer Learning for Sub-5k Countries

**Decision**: Use LightGBM's `init_model` parameter. The Spain national booster is passed as the `init_model` when calling `lgb.train()` on the country's data, with `learning_rate=0.01` and `n_estimators` capped at 200. No Optuna tuning for transfer runs (fixed hyperparameters).

**Rationale**:
- LightGBM's `init_model` continues boosting from an existing model, adding new trees on top. This is the correct analogue of fine-tuning: the existing knowledge (Spain price dynamics) acts as a prior, and new trees specialise on local data.
- Reduced `learning_rate` (0.01) and capped `n_estimators` (200) prevent overfitting on small datasets.
- No Optuna tuning for transfer runs because 50 trials × LightGBM cross-validation on < 5k rows is fast but wasteful; the Spain hyperparameters already searched are reused.

**Pre-condition**: Spain national model must be trained first in each weekly run. Country loop processes Spain before all others.

**Alternatives considered**:
- Full retrain on country data alone: Insufficient data; high variance.
- Feature embedding transfer (match latent space): Too complex; no benefit over `init_model` at this scale.

---

## Decision 4: Champion/Challenger Promotion Logic

**Decision**: Read the current champion from `model_versions` where `status = 'active'` and `country_code = <country>`. Compare challenger MAPE on the national test set. Promote only if `challenger_mape < champion_mape * 0.98` (≥ 2% relative improvement). Promotion is transactional: set challenger to `ACTIVE`, set champion to `RETIRED` in a single `asyncpg` transaction.

**Rationale**:
- The `MlModelVersion` model in `estategap-common` uses `ModelStatus.ACTIVE/RETIRED/STAGING` — no new DB columns needed beyond what's already modelled.
- A 2% relative improvement threshold filters out noise from dataset drift (typical inter-run MAPE variance observed on similar datasets ≈ 0.5–1%).
- First-run case (no champion exists): the new model is always promoted regardless of MAPE.
- The `metrics` JSONB column stores the per-city MAPE breakdown.

**Alternatives considered**:
- Absolute MAPE threshold (e.g., < 10%): Ignores that a good champion at 8% could be degraded to 9.9% and still "pass". Relative improvement is stricter.
- Configurable threshold via env var: Accepted — expose as `PROMOTION_MAPE_IMPROVEMENT_PCT` (default `0.02`).

---

## Decision 5: Feature Fallback for Missing Zone Statistics

**Decision**: Three-level fallback for zone-level spatial features:
1. `zone_id` match → use precomputed zone stats.
2. City-level aggregate (all zones in same city) → use city median.
3. Country-level aggregate → use country median (always available).

**Rationale**:
- Not all enriched listings have a `zone_id`. Listings enriched but without zone match get city-level stats. Listings without city get country-level stats.
- All three levels are precomputed before training starts (single SQL query), stored in a `dict[UUID | str, ZoneStats]` inside `FeatureEngineer`.
- This guarantees no NaN in spatial features.

---

## Decision 6: MLflow Tracking and Model Registry

**Decision**: Use MLflow Tracking Server (already deployed in k8s via `003-k8s-infrastructure`). Log via environment variable `MLFLOW_TRACKING_URI`. Use `mlflow.set_experiment("estategap-price-models")`. Log:
- Parameters: all Optuna best hyperparameters + feature list hash.
- Metrics: MAE, MAPE, R² (national + per major city at end of training).
- Artifacts: ONNX model file, feature importance PNG, feature names JSON, fitted FeatureEngineer joblib.
- **Do NOT** use MLflow Model Registry (the `model_versions` PostgreSQL table is the registry, keeping the source of truth in our own DB).

**Rationale**:
- MLflow Model Registry adds a separate registry store that duplicates the `model_versions` table. Single source of truth in Postgres avoids drift.
- MLflow Tracking is used purely for experiment observability.

---

## Decision 7: Target Variable

**Decision**: `asking_price_eur` for all listings. For listings with `status = 'sold'` where a `final_price_eur` column exists (post-migration), prefer `final_price_eur`. Log count of each in MLflow.

**Assumption**: A future migration will add `final_price_eur` to the `listings` table. The data export query uses `COALESCE(final_price_eur, asking_price_eur)` so the code works today (where the column doesn't yet exist, the COALESCE defaults to asking price).

---

## Decision 8: model_versions Database Table

**Decision**: Add Alembic migration `016_model_versions.py` to create the `model_versions` table matching the `MlModelVersion` Pydantic schema. The trainer service owns this migration (alongside the existing pipeline migrations in `services/pipeline/alembic/`).

**Schema** (key columns):
```sql
CREATE TABLE model_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code CHAR(2)       NOT NULL,
    algorithm   VARCHAR(50)    NOT NULL DEFAULT 'lightgbm',
    version_tag VARCHAR(100)   NOT NULL,
    artifact_path TEXT         NOT NULL,
    dataset_ref  TEXT,
    feature_names JSONB        NOT NULL DEFAULT '[]',
    metrics      JSONB         NOT NULL DEFAULT '{}',
    status       VARCHAR(20)   NOT NULL DEFAULT 'staging',
    trained_at   TIMESTAMPTZ   NOT NULL,
    promoted_at  TIMESTAMPTZ,
    retired_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX model_versions_country_status ON model_versions (country_code, status);
```

**Rationale**: Uses the existing `MlModelVersion` Pydantic schema from `estategap-common`. Trainer reads/writes this table; scorer reads it to select the active model.

---

## Decision 9: NATS Event on Training Completion

**Decision**: On successful promotion, publish event to NATS subject `ml.training.completed`. On failure (any unhandled exception), publish to `ml.training.failed`. Events use Pydantic models defined in this feature's `estategap_ml` package. Both events carry `country_code`, `model_version_tag`, `mape_national`, and `timestamp`.

**Rationale**: Constitution §II mandates inter-service events via NATS. The alert-dispatcher can subscribe to `ml.training.failed` and send an operator notification. The scorer can subscribe to `ml.training.completed` to hot-reload the new model.

---

## Decision 10: Kubernetes CronJob Configuration

**Decision**:
```yaml
schedule: "0 3 * * 0"           # Sunday 03:00 UTC
concurrencyPolicy: Forbid        # no parallel runs
successfulJobsHistoryLimit: 3
failedJobsHistoryLimit: 3
restartPolicy: Never             # don't retry automatically
backoffLimit: 0                  # one attempt per trigger
```
`backoffLimit: 0` because the job manages its own retry-safety via Optuna SQLite study and champion retention; a failed run leaves the previous champion intact.

**Resource requests/limits**: `memory: 4Gi / 8Gi`, `cpu: 2 / 4`. Training a LightGBM model on 100k listings with Optuna fits comfortably within 4 GiB.
