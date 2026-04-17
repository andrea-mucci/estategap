# Tasks: ML Training Pipeline

**Input**: Design documents from `specs/014-ml-training-pipeline/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. Because US2 (Feature Engineering) and US3 (Registry) are technical prerequisites for US1 (Training Pipeline), implementation order is US2 → US3 → US1 → US4, even though P1 appears last in this sequence. Each phase remains independently testable at its checkpoint.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend the existing `services/ml/` scaffold with all new dependencies and directory structure before any story work begins.

- [X] T001 Add training dependencies to `services/ml/pyproject.toml`: scikit-learn>=1.5, optuna>=3.6, skl2onnx>=1.17, onnxmltools>=1.12, mlflow>=2.13, asyncpg>=0.29, nats-py>=2.6, structlog>=24.1, pydantic-settings>=2.2, prometheus-client>=0.20, pandas>=2.2, joblib>=1.4, matplotlib>=3.9, boto3>=1.34
- [X] T002 Create package directories: `services/ml/estategap_ml/features/`, `services/ml/estategap_ml/trainer/`; add `__init__.py` and `py.typed` stubs to each
- [X] T003 [P] Create `services/ml/estategap_ml/config.py` — pydantic-settings `Config` model with fields: `database_url`, `mlflow_tracking_uri`, `nats_url`, `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket` (default `estategap-models`), `promotion_mape_improvement_pct` (default `0.02`), `min_listings_per_country` (default `5000`), `optuna_n_trials` (default `50`), `log_level` (default `INFO`)
- [X] T004 [P] Create `services/ml/.env.example` with all env var names and placeholder values, matching the variable list in `quickstart.md`
- [X] T005 [P] Update `services/ml/Dockerfile` to install new system dependencies (`libgomp1` for LightGBM) and run `uv sync --frozen` with the updated `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database migration, data export query, zone statistics fetch, and NATS publisher — shared infrastructure that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Create Alembic migration `services/pipeline/alembic/versions/016_model_versions.py` — create `model_versions` table with columns: `id UUID PK DEFAULT gen_random_uuid()`, `country_code CHAR(2) NOT NULL`, `algorithm VARCHAR(50) NOT NULL DEFAULT 'lightgbm'`, `version_tag VARCHAR(100) NOT NULL`, `artifact_path TEXT NOT NULL`, `dataset_ref TEXT`, `feature_names JSONB NOT NULL DEFAULT '[]'`, `metrics JSONB NOT NULL DEFAULT '{}'`, `status VARCHAR(20) NOT NULL DEFAULT 'staging'`, `trained_at TIMESTAMPTZ NOT NULL`, `promoted_at TIMESTAMPTZ`, `retired_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`; add indexes on `(country_code, status)` and unique on `(country_code, version_tag)`
- [X] T007 [P] Implement `services/ml/estategap_ml/trainer/data_export.py` — async function `export_training_data(country: str, dsn: str) -> pd.DataFrame` that executes the SQL join of `listings` + `zones` with filter `(status IN ('sold','delisted') OR days_on_market > 30) AND asking_price_eur IS NOT NULL AND built_area_m2 > 0`, returns a DataFrame with all columns listed in `data-model.md` §3; include a `stratified_split(df, stratify_col, ratios=(0.70,0.15,0.15)) -> tuple[DataFrame,DataFrame,DataFrame]` function that assigns rare-city rows to an "other" stratum
- [X] T008 [P] Implement `services/ml/estategap_ml/features/zone_stats.py` — `ZoneStats` dataclass (`zone_id: UUID`, `median_price_m2: float`, `listing_density: int`, `avg_income: float | None`), async function `fetch_zone_stats(country: str, dsn: str) -> dict[UUID, ZoneStats]` executing the zone statistics query from `data-model.md` §2; include city-level and country-level aggregate fallback dicts as secondary return values
- [X] T009 [P] Implement `services/ml/estategap_ml/nats_publisher.py` — Pydantic models `TrainingCompletedEvent` and `TrainingFailedEvent` matching schemas in `contracts/nats-events.md`; async functions `publish_completed(event, nats_url)` and `publish_failed(event, nats_url)` that publish to subjects `ml.training.completed` and `ml.training.failed` on the `ML_EVENTS` JetStream stream
- [X] T010 Update `services/ml/estategap_ml/__init__.py` to re-export `Config` and configure `structlog` with JSON renderer and `LOG_LEVEL` from env

**Checkpoint**: Run `uv run python -c "from estategap_ml.config import Config; Config()"` — must succeed. Run `uv run alembic upgrade head` in `services/pipeline/` — migration 016 must apply cleanly.

---

## Phase 3: User Story 2 — Feature Engineering Reliability (Priority: P2)

**Goal**: `FeatureEngineer.transform()` produces a complete, finite float32 feature vector for any listing record, with no NaN or Inf values, covering all ~36 features from `data-model.md` §4.

**Independent Test**: `uv run python -m estategap_ml.features --smoke-test --country es --limit 10000` — must print shape `(10000, 36)` and `no NaN ✓ no Inf ✓`.

### Implementation for User Story 2

- [X] T011 [P] [US2] Implement `services/ml/estategap_ml/features/encoders.py` — `energy_cert_encoder()` returning a fitted `OrdinalEncoder(categories=[['G','F','E','D','C','B','A']])` mapping A→7 … G→1; `condition_encoder()` returning `OrdinalEncoder(categories=[['to_renovate','renovate','good','new']])` mapping new→4 … to_renovate→1; both encoders must handle unknown values by outputting 0 using `handle_unknown='use_encoded_value', unknown_value=0`
- [X] T012 [US2] Implement `services/ml/estategap_ml/features/engineer.py` — `FeatureEngineer(BaseEstimator, TransformerMixin)` class with: constructor accepting `zone_stats: dict[UUID, ZoneStats]`, `city_stats: dict[str, ZoneStats]`, `country_stats: ZoneStats`; `fit(df: pd.DataFrame) -> FeatureEngineer` that fits a `ColumnTransformer` with `SimpleImputer(strategy="median")` for all numeric nullable columns, `SimpleImputer(strategy="most_frequent")` for categorical nullables, `energy_cert_encoder()`, `condition_encoder()`, and `OneHotEncoder(sparse_output=False, handle_unknown='ignore', categories=[['apartment','house','studio','penthouse','duplex','other']])` for `property_type`; stores `feature_names_out_: list[str]`
- [X] T013 [US2] Complete `services/ml/estategap_ml/features/engineer.py` — implement `transform(df: pd.DataFrame) -> np.ndarray` that: (1) resolves zone stats per row using 3-level fallback (zone_id → city → country), (2) computes derived columns: `usable_built_ratio`, `price_per_m2_eur`, `month_sin = sin(2π*month/12)`, `month_cos = cos(2π*month/12)`, `building_age_years = current_year - building_year`, `data_completeness`, `has_energy_cert`, `has_photos`, (3) applies `ColumnTransformer.transform()`, (4) casts result to `float32`, (5) asserts `not np.any(np.isnan(X)) and not np.any(np.isinf(X))` raising `ValueError` on violation
- [X] T014 [US2] Implement `services/ml/estategap_ml/features/__main__.py` — CLI entry point with flags `--smoke-test`, `--country CHAR2`, `--limit INT`; loads zone stats from DB, instantiates and fits `FeatureEngineer` on a sample of `--limit` listings, prints feature matrix shape and NaN/Inf assertion result
- [X] T015 [P] [US2] Write unit tests in `services/ml/tests/unit/test_feature_engineer.py`: (1) test `transform()` on a fully-populated row returns shape `(1, N)` with no NaN/Inf; (2) test `transform()` on a row with all optional fields missing still returns no NaN/Inf; (3) test zone fallback chain correctly uses city-level stats when zone_id is absent; (4) test cyclical encoding: for month=6, assert `month_sin ≈ 1.0` and `month_cos ≈ 0.0`
- [X] T016 [P] [US2] Write unit tests in `services/ml/tests/unit/test_encoders.py`: (1) test `energy_cert_encoder` maps A→7, G→1, unknown→0; (2) test `condition_encoder` maps new→4, to_renovate→1, unknown→0; (3) test both encoders handle `None`/missing without raising

**Checkpoint**: `uv run pytest services/ml/tests/unit/test_feature_engineer.py services/ml/tests/unit/test_encoders.py -v` — all tests green. `uv run python -m estategap_ml.features --smoke-test --country es --limit 100` (against a seeded DB) — no NaN/Inf.

---

## Phase 4: User Story 3 — Champion/Challenger Model Registry (Priority: P2)

**Goal**: Every training run is logged in MLflow with all params/metrics/artefacts, the ONNX artefact exports and verifies successfully, and the `model_versions` table correctly tracks exactly one active model per country.

**Independent Test**: After a training run (even `--dry-run` skipping promotion), verify: (1) MLflow UI shows the run with all parameters and metrics; (2) ONNX file loads via `onnxruntime.InferenceSession` and produces the same predictions as the LightGBM native model on 100 test rows.

### Implementation for User Story 3

- [X] T017 [US3] Implement `services/ml/estategap_ml/trainer/onnx_export.py` — function `export_pipeline_to_onnx(feature_engineer: FeatureEngineer, lgb_model: lgb.Booster, version_tag: str, output_dir: Path) -> Path` that: (1) wraps the fitted `FeatureEngineer` and LightGBM booster in a sklearn `Pipeline`, (2) converts via `skl2onnx.convert_sklearn()` with `onnxmltools` backend for LightGBM, (3) saves to `output_dir/{version_tag}.onnx`, (4) runs self-test: load via `onnxruntime.InferenceSession`, run on 50 random training rows, assert predictions match native LGB within `atol=1.0` (EUR), (5) raises `OnnxSelfTestError` on mismatch
- [X] T018 [P] [US3] Implement `services/ml/estategap_ml/trainer/registry.py` — async functions: `get_active_champion(country: str, conn) -> MlModelVersion | None` (queries `model_versions WHERE status='active' AND country_code=$1 FOR UPDATE`); `insert_staging_version(metrics, artifact_path, fe_path, version_tag, country, conn) -> UUID`; `promote_version(new_id: UUID, champion_id: UUID | None, conn)` (atomic transaction: retire champion if present, set new to active with `promoted_at=NOW()`); `upload_artifacts(onnx_path: Path, fe_path: Path, minio_client, bucket: str, version_tag: str) -> str` (returns MinIO artifact URL); `maybe_promote(country, challenger_metrics, onnx_path, fe_path, config) -> bool` (orchestrates the full compare → upload → promote or retire flow)
- [X] T019 [P] [US3] Implement `services/ml/estategap_ml/trainer/mlflow_logger.py` — function `log_training_run(run_name: str, params: dict, metrics: Metrics, onnx_path: Path, fe_path: Path, feature_importances: dict[str, float], tracking_uri: str)` that: (1) sets experiment `"estategap-price-models"`, (2) logs all Optuna best params, (3) logs national MAE/MAPE/R² and per-city MAPE as MLflow metrics, (4) logs ONNX file and feature engineer joblib as MLflow artefacts, (5) generates and logs a feature importance bar chart PNG via matplotlib
- [X] T020 [P] [US3] Implement `services/ml/estategap_ml/trainer/evaluate.py` — `Metrics` dataclass (`mape_national`, `mae_national`, `r2_national`, `per_city: dict[str, dict]`, `n_train`, `n_val`, `n_test`); function `evaluate_model(model, X_test, y_test, city_labels: pd.Series) -> Metrics` computing sklearn `mean_absolute_error`, MAPE (manual: `mean(|y-ŷ|/y)`), and `r2_score`; compute per-city breakdown for cities with ≥ 30 test rows; aggregate smaller cities into "other"
- [X] T021 [P] [US3] Write integration tests in `services/ml/tests/integration/test_onnx_roundtrip.py`: (1) train a minimal LightGBM model on 200 synthetic rows, export to ONNX, reload, assert predictions match within `atol=1.0`; (2) assert self-test raises `OnnxSelfTestError` when a corrupted ONNX file is passed
- [X] T022 [P] [US3] Write integration tests in `services/ml/tests/integration/test_registry_db.py` using `testcontainers[postgres]`: (1) apply migration 016, insert a staging model, call `promote_version()`, assert exactly one row has `status='active'`; (2) insert an active champion, call `maybe_promote()` with a challenger whose MAPE is only 1% better (below threshold), assert champion remains active; (3) call `maybe_promote()` with a challenger 3% better, assert new champion promoted and previous retired; (4) first-run case: no champion → challenger always promoted

**Checkpoint**: `uv run pytest services/ml/tests/integration/test_onnx_roundtrip.py services/ml/tests/integration/test_registry_db.py -v` — all green. On a `--dry-run` training invocation, MLflow experiment shows a completed run with all metrics.

---

## Phase 5: User Story 1 — Automated Weekly Model Training (Priority: P1) 🎯 MVP

**Goal**: The training pipeline runs end-to-end — data export → feature engineering → Optuna tuning → evaluation → ONNX export → conditional promotion → NATS event — orchestrated by a Kubernetes CronJob that fires every Sunday at 03:00 UTC.

**Independent Test**: Trigger `uv run python -m estategap_ml.trainer --country es` against a seeded DB with 10k+ rows and verify: (1) a new model appears in `model_versions`; (2) MLflow run is logged; (3) NATS event published to `ml.training.completed`; (4) ONNX file in MinIO; (5) previous champion (if any) is retired.

### Implementation for User Story 1

- [X] T023 [US1] Implement `services/ml/estategap_ml/trainer/train.py` — `async def run_training(country: str, config: Config) -> TrainingResult`: (1) call `export_training_data(country, config.database_url)` and `stratified_split()`; (2) fetch zone stats and instantiate `FeatureEngineer`; (3) `fe.fit_transform(train_df)`, `fe.transform(val_df)`, `fe.transform(test_df)`; (4) run Optuna study: `optuna.create_study(direction="minimize", pruner=MedianPruner(), storage=f"sqlite:///optuna_{country}.db")`, `n_trials=config.optuna_n_trials`; objective calls `lgb.cv()` with `nfold=5`, `early_stopping_rounds=50`, returns mean MAPE; (5) retrain final model on `train+val` with `study.best_params`; (6) call `evaluate()`, `export_pipeline_to_onnx()`, `joblib.dump(fe, fe_path)`; (7) call `maybe_promote()`; (8) call `log_training_run()`; (9) return `TrainingResult`
- [X] T024 [US1] Implement `services/ml/estategap_ml/trainer/__main__.py` — CLI entry with flags `--country CHAR2`, `--countries-all` (reads distinct country codes from DB), `--dry-run` (skips MinIO upload and DB promotion); wraps `run_training()` in a try/except that calls `publish_failed()` on any unhandled exception; exits with code 1 on failure so the K8s Job reports `Failed`
- [X] T025 [US1] Add Helm CronJob template `helm/estategap/templates/ml-trainer-cronjob.yaml` — `schedule: "0 3 * * 0"`, `concurrencyPolicy: Forbid`, `backoffLimit: 0`, `restartPolicy: Never`, `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 3`; container image from `{{ .Values.mlTrainer.image.repository }}:{{ .Values.mlTrainer.image.tag }}`; command `["python", "-m", "estategap_ml.trainer", "--countries-all"]`; resource requests `memory: 4Gi, cpu: "2"`, limits `memory: 8Gi, cpu: "4"`; `envFrom` referencing `ml-trainer-secrets` sealed secret and `estategap-config` ConfigMap
- [X] T026 [P] [US1] Add `mlTrainer` stanza to `helm/estategap/values.yaml`: `image.repository`, `image.tag` (default `latest`), `resources.requests`, `resources.limits`, and `schedule` (default `"0 3 * * 0"`) — so the CronJob schedule is overridable per environment
- [X] T027 [P] [US1] Add `ml-trainer-secrets` to `helm/estategap/templates/sealed-secrets.yaml` (or create a new `ml-trainer-sealed-secret.yaml`) with placeholders for `DATABASE_URL`, `MLFLOW_TRACKING_URI`, `NATS_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`; document the sealing command in `quickstart.md`
- [X] T028 [P] [US1] Write acceptance test `services/ml/tests/acceptance/test_full_pipeline.py` using `testcontainers[postgres]` + a real MinIO container: seed 10,000 synthetic Spanish listing rows meeting the training filter; run `run_training("es", config)`; assert: output matrix has no NaN/Inf, `model_versions` has exactly one `status='active'` row, ONNX file exists in MinIO, MLflow run contains keys `mape_national` and `mae_national`

**Checkpoint**: `uv run pytest services/ml/tests/acceptance/test_full_pipeline.py -v -s` — green. `kubectl create job ml-training-smoke --from=cronjob/ml-trainer -n estategap-system` completes with exit 0.

---

## Phase 6: User Story 4 — Per-Country Model Support (Priority: P3)

**Goal**: The pipeline trains a dedicated model for each country with > 5,000 listings, and applies transfer learning via LightGBM `init_model` for smaller markets — all within the same weekly run.

**Independent Test**: Seed the DB with 6,000 rows for country `"pt"` (Portugal) and run `--countries-all`; verify a `model_versions` row appears for `country_code='pt'` with a version tag `pt_national_v1` and `status='active'`.

### Implementation for User Story 4

- [X] T029 [US4] Extend `services/ml/estategap_ml/trainer/train.py` — add `async def run_transfer_training(country: str, spain_booster: lgb.Booster, fe: FeatureEngineer, config: Config) -> TrainingResult` that: (1) exports country data; (2) reuses the fitted Spain `FeatureEngineer` (same feature schema cross-country); (3) calls `lgb.train({"learning_rate": 0.01, "n_estimators": 200, "objective": "regression", "metric": "mape"}, lgb_dataset, init_model=spain_booster)` — no Optuna; (4) evaluates, exports ONNX, promotes, logs to MLflow with tag `transfer_learning=True`
- [X] T030 [US4] Extend `services/ml/estategap_ml/trainer/__main__.py` — when `--countries-all` is set: (1) query distinct countries from `listings` ordered by listing count descending; (2) ensure `"es"` is processed first and its booster is stored as `spain_booster`; (3) for each subsequent country: if count ≥ `config.min_listings_per_country` → `run_training()`; else → `run_transfer_training()` with `spain_booster`; (4) if Spain training fails, log and skip all transfer countries, publish one `ml.training.failed` event per skipped country
- [X] T031 [US4] Implement version-tag generation in `services/ml/estategap_ml/trainer/registry.py` — function `next_version_tag(country: str, city_scope: str, conn) -> str` that queries `MAX(version_tag)` for the country, parses the version integer suffix, returns `f"{country}_{city_scope}_v{n+1}"`; use `"national"` as `city_scope` for country-level models
- [X] T032 [P] [US4] Write unit tests in `services/ml/tests/unit/test_registry.py`: (1) test `next_version_tag()` returns `"es_national_v1"` when no prior rows exist; (2) test it returns `"es_national_v13"` when `"es_national_v12"` is the latest; (3) test `"pt_national_v1"` is independent of Spain's version sequence

**Checkpoint**: `uv run pytest services/ml/tests/unit/test_registry.py -v` — green. With a seeded DB containing a Portugal dataset, `--countries-all` produces two rows in `model_versions` (one `es`, one `pt`), both `status='active'`.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Prometheus metrics, Helm lint, Dockerfile verification, integration test coverage for data export, and developer experience improvements.

- [X] T033 [P] Add Prometheus metrics to `services/ml/estategap_ml/trainer/train.py` and `trainer/__main__.py`: `ml_training_duration_seconds` (Gauge), `ml_training_mape_national` (Gauge labelled by country), `ml_model_promoted_total` (Counter labelled by country); push to Prometheus Pushgateway at job completion using `prometheus_client.push_to_gateway`
- [X] T034 [P] Write integration test `services/ml/tests/integration/test_data_export.py` using `testcontainers[postgres]`: apply migration 016, insert 50 synthetic listing rows (mix of `sold`, `active` with days_on_market > 30, and `active` with days_on_market < 30), call `export_training_data("es", dsn)`, assert only eligible rows are returned and no required column is NULL
- [X] T035 [P] Run `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml` and fix any lint errors introduced by the new `ml-trainer-cronjob.yaml` and values stanza
- [ ] T036 [P] Build and smoke-test the updated Docker image: `docker build -t estategap-ml:dev services/ml/ && docker run --rm estategap-ml:dev python -c "import lightgbm; import onnxruntime; import mlflow; import optuna; print('OK')"` — verify all new deps import cleanly
- [X] T037 Update `services/ml/pyproject.toml` `[dependency-groups].dev` to include `testcontainers[postgres]>=4.4` and `moto>=5.0` (MinIO/S3 mock for unit tests that do not use real MinIO)

**Checkpoint**: All phases pass. `uv run pytest services/ml/tests/ -v --tb=short` — full test suite green. Helm lint clean. Docker image builds and all imports succeed.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **Phase 3 (US2 — Feature Engineering)**: Depends on Phase 2; no dependency on US3 or US1
- **Phase 4 (US3 — Registry)**: Depends on Phase 2; no dependency on US2 (parallel with Phase 3)
- **Phase 5 (US1 — Training Pipeline)**: Depends on Phase 3 AND Phase 4 both complete
- **Phase 6 (US4 — Per-Country)**: Depends on Phase 5 (extends the Spain training loop)
- **Phase 7 (Polish)**: Depends on Phases 3–6 complete

### User Story Dependencies

- **US2 (Feature Engineering)**: Starts after Phase 2 — independent of US3
- **US3 (Registry)**: Starts after Phase 2 — independent of US2, can run in parallel
- **US1 (Training Pipeline)**: Requires US2 AND US3 complete
- **US4 (Per-Country)**: Requires US1 complete

### Within Each Phase

- Tasks marked `[P]` within the same phase have no file conflicts and can run in parallel
- Non-`[P]` tasks within a phase depend on the preceding task(s) in that phase
- The Optuna study in `train.py` (T023) depends on `FeatureEngineer` (T012–T013) and `evaluate.py` (T020)

---

## Parallel Execution Examples

### Phase 3 + Phase 4 (after Phase 2 completes)

```
# Two streams running concurrently:
Stream A (US2):  T011 → T012 → T013 → T014 → T015, T016
Stream B (US3):  T017 → T018, T019, T020 → T021, T022
```

### Within Phase 3 (US2)

```
# Parallel:
Task: T011 — encoders.py
(then sequentially)
Task: T012 → T013 → T014
# Parallel after T014:
Task: T015 — test_feature_engineer.py
Task: T016 — test_encoders.py
```

### Within Phase 4 (US3)

```
# All parallel after T017:
Task: T018 — registry.py
Task: T019 — mlflow_logger.py
Task: T020 — evaluate.py
# Then parallel:
Task: T021 — test_onnx_roundtrip.py
Task: T022 — test_registry_db.py
```

### Within Phase 5 (US1)

```
# Sequential core:
T023 (train.py) → T024 (__main__.py)
# Parallel infrastructure (start any time after Phase 2):
T025, T026, T027 — Helm + sealed secrets
# After T024:
T028 — acceptance test
```

---

## Implementation Strategy

### MVP First (US2 + US3 + US1, Spain only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — apply migration 016, verify DB schema
3. Complete Phase 3 (US2): `FeatureEngineer` with full smoke test green
4. Complete Phase 4 (US3): ONNX export self-test + registry promotion transaction passing
5. Complete Phase 5 (US1): End-to-end pipeline + CronJob manifest
6. **STOP and VALIDATE**: Run acceptance test + manually trigger CronJob in staging
7. Deploy — Spain model training is fully operational

### Incremental Delivery

1. Phase 1+2 → schema and infrastructure ready
2. Phase 3 (US2) → feature engineering verified in isolation
3. Phase 4 (US3) → registry and ONNX pipeline verified in isolation
4. Phase 5 (US1) → full weekly training loop for Spain live in staging
5. Phase 6 (US4) → per-country expansion (Portugal, Italy, etc.)
6. Phase 7 (Polish) → observability and Helm hardening

### Parallel Team Strategy

With two developers:

1. Both complete Phase 1 + Phase 2 together
2. Once Phase 2 is done:
   - Developer A: Phase 3 (US2 — FeatureEngineer)
   - Developer B: Phase 4 (US3 — Registry, ONNX, MLflow, Evaluate)
3. Reconvene for Phase 5 (US1 — training orchestration + CronJob)
4. Developer A: Phase 6 (US4 — transfer learning)
5. Developer B: Phase 7 (Polish — metrics, Helm, Docker smoke)

---

## Notes

- `[P]` tasks touch different files and have no shared state — safe to run in parallel
- `[Story]` labels map to user stories in `spec.md` for traceability
- Each phase checkpoint is independently runnable before proceeding
- The Alembic migration (T006) must be applied before any DB integration test runs
- Spain ("es") must complete before any transfer-learning country — enforced in `__main__.py`
- `--dry-run` flag skips MinIO upload and DB promotion — safe to use for local iteration
- MinIO mock (`moto`) is used in unit tests; real MinIO container used in integration/acceptance tests
