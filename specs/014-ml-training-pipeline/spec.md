# Feature Specification: ML Training Pipeline

**Feature Branch**: `014-ml-training-pipeline`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Build the ML training pipeline: feature engineering, model training with hyperparameter tuning, and model registry."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Weekly Model Training (Priority: P1)

The system automatically retrains the property price estimation model every week using all available historical listing data. A data scientist or operator does not need to intervene; the pipeline runs on schedule, evaluates the new model, and promotes it only if it outperforms the current champion by a meaningful margin.

**Why this priority**: This is the core automation requirement. Without it, the model degrades over time as the market evolves, leading to inaccurate price estimates.

**Independent Test**: Can be fully tested by triggering the weekly job manually and verifying that it completes end-to-end: data export → feature engineering → training → evaluation → conditional promotion.

**Acceptance Scenarios**:

1. **Given** a running system with ≥ 10,000 Spanish listings in the database, **When** the weekly training job executes, **Then** a new model is trained, evaluated, and either promoted or rejected within the same run.
2. **Given** the new model achieves MAPE 2% better than the active champion, **When** evaluation completes, **Then** the new model is promoted to active status and the previous champion is archived.
3. **Given** the new model does not meet the improvement threshold, **When** evaluation completes, **Then** the previous champion remains active and an alert is recorded.

---

### User Story 2 - Feature Engineering Reliability (Priority: P2)

Given any raw listing record from the database, the feature engineering component produces a complete, finite numeric feature vector with no missing values or infinite entries, ready for model input.

**Why this priority**: Garbage-in, garbage-out. If the feature vector contains NaN or Inf values, the model produces invalid predictions silently, which is worse than failing visibly.

**Independent Test**: Can be fully tested by passing a batch of 10,000+ listings through the feature engineer and asserting that the output array contains no NaN or Inf values.

**Acceptance Scenarios**:

1. **Given** a listing record with all optional fields present, **When** the feature engineer transforms it, **Then** a 35-element numeric vector is returned with no NaN or Inf values.
2. **Given** a listing record with several optional fields missing (e.g., no energy certificate, no floor number), **When** the feature engineer transforms it, **Then** missing values are imputed, missingness indicator features are set, and the output is still NaN/Inf-free.
3. **Given** 10,000+ Spanish listing records, **When** batch-transformed, **Then** the entire output matrix contains no NaN or Inf values.

---

### User Story 3 - Champion/Challenger Model Registry (Priority: P2)

A data scientist can inspect the history of all trained models, view their performance metrics, compare the champion to challengers, and understand which model is currently serving predictions.

**Why this priority**: Without traceability, the team cannot audit why price estimates changed, reproduce prior results, or roll back a bad promotion.

**Independent Test**: Can be fully tested by verifying MLflow experiment records and the `model_versions` database table after a training run.

**Acceptance Scenarios**:

1. **Given** a completed training run, **When** a data scientist opens the MLflow UI, **Then** the run appears with all hyperparameters, MAE, MAPE, R², and per-city metrics logged.
2. **Given** a newly promoted model, **When** querying `model_versions` in the database, **Then** exactly one row has `is_active = true` and the ONNX artefact URL points to a valid file in object storage.
3. **Given** a training run where the challenger lost, **When** inspecting the registry, **Then** the run is logged but `is_active` remains on the previous champion.

---

### User Story 4 - Per-Country Model Support (Priority: P3)

The pipeline can train and manage separate price models for each country that has sufficient listing volume, and applies transfer learning for markets with limited data.

**Why this priority**: A single Spain-only model cannot generalise to Portugal or Italy. Supporting per-country models enables future geographic expansion.

**Independent Test**: Can be fully tested by seeding the database with > 5,000 listings for a second country and verifying that a separate named model is trained and registered for that country.

**Acceptance Scenarios**:

1. **Given** a country with > 5,000 listings in the database, **When** training runs, **Then** a dedicated model named `{country}_{city_or_national}_v{N}` is trained and registered for that country.
2. **Given** a country with < 5,000 listings, **When** training runs, **Then** the Spain base model is fine-tuned on that country's data at a reduced learning rate and registered separately.

---

### Edge Cases

- What happens when the training dataset contains fewer than the minimum required listings (e.g., < 1,000 rows)? The job must fail gracefully with a clear error, not train a degenerate model.
- How does the system handle a database outage during data export? The job must abort and fire an alert; no partial model should be registered.
- What if MLflow is unreachable during logging? The job should fail loudly rather than silently skip metric logging.
- What if the ONNX export produces a file that fails a self-test round-trip? The model must not be promoted.
- What if all candidate hyperparameter trials result in MAPE > 20% (catastrophically bad data)? The champion remains active and an alert is raised.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST export training data from the listings database, filtered to records that are sold, delisted, or have been on market for more than 30 days.
- **FR-002**: The feature engineering component MUST transform a raw listing record into a numeric feature vector of approximately 35 features covering spatial, physical, condition, contextual, temporal, and derived categories.
- **FR-003**: The feature engineer MUST impute all missing numerical values using the median and all missing categorical values using the mode, computed on the training set.
- **FR-004**: The feature engineer MUST produce binary missingness-indicator features (e.g., `has_energy_cert`) for fields with meaningful absence rates.
- **FR-005**: The feature engineer MUST encode energy certificate (A–G) and property condition as ordered numeric values, and property type and orientation as one-hot encoded features.
- **FR-006**: The feature engineer MUST encode the listing month as cyclical sine/cosine features.
- **FR-007**: The training pipeline MUST perform a stratified 70/15/15 train/validation/test split, stratified by city.
- **FR-008**: The training pipeline MUST run automated hyperparameter search over at least 50 trials, minimising MAPE on the validation set.
- **FR-009**: The pipeline MUST evaluate the trained model on the held-out test set and compute MAE, MAPE, and R² globally and per major city.
- **FR-010**: The pipeline MUST export the trained model to ONNX format and verify it loads and produces valid outputs before registration.
- **FR-011**: The pipeline MUST log all hyperparameters, evaluation metrics, and a feature importance chart to MLflow.
- **FR-012**: The pipeline MUST promote a new model to champion status only if its national MAPE is at least 2% relatively better than the current active champion.
- **FR-013**: On promotion, the pipeline MUST upload the ONNX artefact to object storage, update `model_versions` to mark the new model active, and deactivate the previous champion.
- **FR-014**: The pipeline MUST train a separate model per country when that country has > 5,000 listings; for countries below this threshold it MUST fine-tune from the Spain base model.
- **FR-015**: The training job MUST be scheduled to run automatically once per week (Sunday 03:00 UTC) via a Kubernetes CronJob.
- **FR-016**: On job failure, the system MUST send an alert and leave the previous champion active.
- **FR-017**: The feature engineer artefact (fitted transformers and statistics) MUST be serialisable and reloadable alongside the model for inference.

### Key Entities

- **Listing**: A property listing record with price, location, physical attributes, condition fields, and temporal metadata.
- **Zone Statistics**: Aggregated zone-level metrics (median price per m², listing density, average income) used as spatial lookup features.
- **Feature Vector**: A fixed-length numeric array produced by the feature engineer for a single listing.
- **Model Version**: A registry entry representing one trained model, containing: name, version number, ONNX artefact location, evaluation metrics, active flag, and creation timestamp.
- **MLflow Run**: An experiment record capturing hyperparameters, metrics, and artefact references for a single training trial.
- **Training Job**: The scheduled process that orchestrates data export, feature engineering, model training, evaluation, and conditional promotion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The feature engineer processes 10,000+ Spanish listing records and produces an output matrix with zero NaN or Inf values.
- **SC-002**: The trained model achieves a national MAPE below 12% and a MAPE below 10% for Madrid and Barcelona on the held-out test set.
- **SC-003**: The ONNX artefact exports and reloads successfully, producing identical predictions to the LightGBM model on the same inputs.
- **SC-004**: Every training run is fully recorded in MLflow with all hyperparameters, evaluation metrics, and artefacts attached.
- **SC-005**: The weekly training job executes without manual intervention, completing successfully or raising a visible alert on failure.
- **SC-006**: The champion/challenger promotion logic correctly activates the new model when the 2% improvement threshold is met and retains the existing champion otherwise.

## Assumptions

- The `listings` and `zone_statistics` tables exist in PostgreSQL with the schema defined in the database feature (004-database-schema and 013-enrichment-change-detection).
- A `model_versions` table exists (or will be created as part of this feature) with columns: `id`, `name`, `version`, `country`, `city_scope`, `artifact_url`, `mape_national`, `mae_national`, `r2_national`, `per_city_metrics` (JSON), `is_active`, `created_at`.
- MLflow and MinIO (or equivalent object storage) are available in the Kubernetes cluster as configured in the infrastructure feature (003-k8s-infrastructure).
- The Spain market is the primary market; other country models are secondary and do not block delivery of the Spain model.
- Asking price in EUR is used as the target variable; final sale price is used when available for sold listings.
- The model is retrained from scratch each week; incremental/online learning is out of scope.
- The inference service that consumes the ONNX model is a separate feature and is out of scope here.
- City stratification uses the `city` field on the listing record; listings without a city are assigned to an "unknown" stratum.
