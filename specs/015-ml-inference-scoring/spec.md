# Feature Specification: ML Inference & Scoring

**Feature Branch**: `015-ml-inference-scoring`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Build the ML inference service that scores listings in real-time and provides deal explanations."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Batch Scoring of Enriched Listings (Priority: P1)

When a listing completes the enrichment pipeline, it is automatically scored by the ML service. The system assigns an estimated market price, a deal score, a deal tier, and a confidence interval. Results are persisted and forwarded downstream so that alerts and the frontend can display accurate deal quality immediately.

**Why this priority**: This is the core automation path. Without batch scoring, no listings ever get a deal score and the entire downstream alerting and discovery experience breaks.

**Independent Test**: Can be fully tested by publishing a synthetic enriched listing to `enriched.listings`, then asserting that the `listings` row is updated with non-null `estimated_price`, `deal_score`, `deal_tier`, `confidence_low`, `confidence_high`, and a `scored.listings` message appears.

**Acceptance Scenarios**:

1. **Given** an enriched listing published to `enriched.listings`, **When** the scorer processes it, **Then** the `listings` row is updated with `estimated_price`, `deal_score`, `deal_tier`, `confidence_low`, `confidence_high`, `model_version`, and `scored_at` within 3 seconds.
2. **Given** a batch of 100 enriched listings published consecutively, **When** the scorer processes them, **Then** all 100 rows are updated and 100 `scored.listings` events are published within 3 seconds total.
3. **Given** a listing from a country with no active model, **When** the scorer receives it, **Then** the listing is skipped with a structured warning log and no partial update is written.

---

### User Story 2 - On-Demand Scoring via API (Priority: P1)

A user triggers a manual property valuation through the API (e.g., by pasting a URL or entering details). The API gateway calls the scorer gRPC endpoint and receives a complete scoring result — estimated price, deal score, deal tier, confidence interval — within 100ms.

**Why this priority**: On-demand scoring is the user-facing valuation feature. It must be fast and reliable for the product to feel responsive.

**Independent Test**: Can be fully tested by calling `ScoreListing` via grpc with a known listing ID and asserting the response contains all required fields within the latency threshold.

**Acceptance Scenarios**:

1. **Given** a valid listing ID and country code, **When** `ScoreListing` is called, **Then** a `ScoringResult` is returned with `estimated_price`, `deal_score`, `deal_tier`, `confidence_low`, `confidence_high`, and `model_version` — all within 100ms.
2. **Given** a listing ID for a country without an active model, **When** `ScoreListing` is called, **Then** a structured gRPC error is returned with status `FAILED_PRECONDITION` and a human-readable message.
3. **Given** a listing ID that does not exist in the database, **When** `ScoreListing` is called, **Then** a `NOT_FOUND` gRPC error is returned.

---

### User Story 3 - Deal Explanation (SHAP Features) (Priority: P2)

For listings identified as great deals or good deals (Tier 1 and 2), the system provides a human-readable explanation of what drives the estimated price. The explanation lists the top 5 contributing factors with plain-language descriptions (e.g., "Zone median price of €4,800/m² pushes estimate up").

**Why this priority**: Explanations build user trust and differentiate the product from simple price estimates. They are required for Tier 1 and 2 deals, which are the most actionable for users.

**Independent Test**: Can be fully tested by scoring a Tier 1 or Tier 2 listing and asserting the `shap_features` JSONB column contains exactly 5 entries, each with a non-empty human-readable label.

**Acceptance Scenarios**:

1. **Given** a scored listing with `deal_tier = 1` or `deal_tier = 2`, **When** SHAP computation completes, **Then** the `shap_features` column contains a JSON array of 5 objects, each with `feature`, `value`, `shap_value`, and `label` fields.
2. **Given** a scored listing with `deal_tier = 3` or `deal_tier = 4`, **When** the scorer processes it, **Then** `shap_features` is set to an empty array (no computation performed).
3. **Given** the same model version scoring two identical listings, **When** both are scored separately, **Then** the SHAP labels and values are identical (deterministic output).

---

### User Story 4 - Comparable Properties (Priority: P2)

For any scored listing, the system identifies 5 comparable active listings in the same zone that are most similar in size, room count, and property type. These comparables are returned via gRPC and displayed in the frontend as a market reference.

**Why this priority**: Comparables anchor the estimated price in real market data, making the valuation credible to users who would otherwise question the estimate.

**Independent Test**: Can be fully tested by calling `GetComparables` for a listing in a zone with ≥ 10 active listings and asserting 5 results are returned, all in the same city and with similar physical attributes.

**Acceptance Scenarios**:

1. **Given** a listing in a zone with ≥ 5 active comparable listings, **When** `GetComparables` is called, **Then** 5 listing IDs are returned, all in the same city, with similar area (within 30%), room count (within 1), and the same property type.
2. **Given** a listing in a zone with fewer than 5 active listings, **When** `GetComparables` is called, **Then** as many results as available (0–4) are returned without error.
3. **Given** the KNN index for a zone was refreshed within the last hour, **When** `GetComparables` is called, **Then** the response latency is under 50ms.

---

### User Story 5 - Model Hot-Reload (Priority: P2)

When the ML training pipeline promotes a new model version, the scorer automatically picks it up within 60 seconds without any service restart. New scoring requests immediately use the updated model.

**Why this priority**: Without hot-reload, the only way to deploy a new model is a service restart, which disrupts batch scoring and on-demand API calls.

**Independent Test**: Can be fully tested by inserting a new `model_versions` row with `status = 'active'` and a new `version_tag`, waiting 60 seconds, then verifying that subsequent scoring responses report the new `model_version`.

**Acceptance Scenarios**:

1. **Given** a new model version is registered as active in the database, **When** 60 seconds elapse, **Then** all subsequent scoring responses reference the new `model_version`.
2. **Given** a hot-reload is in progress (downloading new model from object storage), **When** a scoring request arrives, **Then** it is served by the previous model version without error.

---

### Edge Cases

- What happens when MinIO is unreachable during model load on startup? Service fails to start with a clear error rather than starting with no loaded models.
- What happens when a listing's feature vector contains unseen property types? The FeatureEngineer handles unknown categories via `handle_unknown='ignore'` (OneHotEncoder), producing all-zero slots.
- What happens when the database is unavailable during a batch scoring write? The micro-batch is retried up to 3 times with exponential back-off; if all retries fail, the NATS message is NAK'd for redelivery.
- What if SHAP computation times out (e.g., > 2 seconds)? SHAP is skipped for that listing, `shap_features` is set to `[]`, and a warning is logged.
- What if the KNN index for a zone has not yet been built (scorer just started)? `GetComparables` returns an empty list rather than an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST expose a gRPC server implementing `MLScoringService` with `ScoreListing`, `ScoreBatch`, and `GetComparables` RPCs.
- **FR-002**: The service MUST load the active ONNX model and quantile models (q05, q95) per country from object storage on startup, indexed by country code.
- **FR-003**: The service MUST consume messages from the `enriched.listings` NATS subject, score each listing, write results to the `listings` table, and publish to `scored.listings`.
- **FR-004**: Batch consumption MUST process messages in micro-batches of 50 for DB write efficiency.
- **FR-005**: The scorer MUST compute `estimated_price` (point estimate), `confidence_low` (q05 model), and `confidence_high` (q95 model) for every scored listing.
- **FR-006**: The scorer MUST compute `deal_score = (estimated_price - asking_price) / estimated_price × 100` and assign `deal_tier` as: Tier 1 (≥ 15%), Tier 2 (5–14.9%), Tier 3 (-5–4.9%), Tier 4 (< -5%).
- **FR-007**: For Tier 1 and Tier 2 listings only, the service MUST compute SHAP values using the LightGBM model and store the top 5 features as a JSONB array in `listings.shap_features`.
- **FR-008**: Each SHAP feature entry MUST include a human-readable label derived from a feature-name-to-template mapping.
- **FR-009**: The service MUST maintain a KNN index per zone (n=5, Euclidean distance, normalised feature matrix) for comparable retrieval, refreshed from the database every hour.
- **FR-010**: The service MUST poll `model_versions` every 60 seconds and hot-reload any newly promoted active model without restarting the process.
- **FR-011**: The `listings` table MUST be updated atomically: `estimated_price`, `deal_score`, `deal_tier`, `confidence_low`, `confidence_high`, `model_version`, `scored_at`, `shap_features`.
- **FR-012**: After updating the database, the service MUST publish a `scored.listings` NATS event for downstream consumers.
- **FR-013**: SHAP results MUST be cached per model version to avoid redundant TreeExplainer instantiation.
- **FR-014**: The service MUST emit Prometheus metrics: scoring latency histogram, batch size histogram, model version gauge, SHAP computation errors counter, comparable cache hit rate.

### Key Entities

- **ScoringResult**: The computed output for one listing — estimated price, deal score, deal tier, confidence interval, SHAP features, model version, timestamp.
- **ModelBundle**: An in-memory bundle of three ONNX sessions (point, q05, q95) and the fitted FeatureEngineer for a given country and model version.
- **ShapFeature**: A single SHAP attribution entry: feature name, raw value, SHAP contribution, human-readable label.
- **ComparableEntry**: A neighbouring listing from the KNN index — listing ID and Euclidean distance in feature space.
- **ZoneIndex**: An in-memory KNN index for one zone — fitted `NearestNeighbors` instance, feature matrix, and list of listing IDs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single listing is fully scored (inference + SHAP + DB write + NATS publish) in under 100ms end-to-end.
- **SC-002**: A batch of 100 listings is fully scored and persisted in under 3 seconds.
- **SC-003**: After a new model version is registered as active, all scoring requests use the new model within 60 seconds — with zero service restarts required.
- **SC-004**: SHAP top-5 features are returned for every Tier 1 and Tier 2 listing with human-readable labels; Tier 3 and Tier 4 listings produce an empty SHAP array.
- **SC-005**: Comparables returned by `GetComparables` are always in the same city, within 30% area, within 1 room count, and of the same property type as the query listing.
- **SC-006**: Deal score and deal tier for 10 known test listings match pre-computed expected values to within ± 0.1% deal score.

## Assumptions

- The `model_versions` table and ONNX artefacts in MinIO are created by the ML training pipeline (feature 014-ml-training-pipeline) and are available before the scorer starts.
- The training pipeline exports three ONNX files per model version: `{version_tag}.onnx` (point estimate), `{version_tag}_q05.onnx` (lower bound), `{version_tag}_q95.onnx` (upper bound).
- The fitted `FeatureEngineer` joblib is available at `{version_tag}_feature_engineer.joblib` alongside the ONNX files in MinIO.
- The LightGBM `.txt` model is available at `{version_tag}.lgb` in MinIO for SHAP computation.
- The `listings` table already has the scoring columns (`estimated_price`, `deal_score`, `deal_tier`, `confidence_low`, `confidence_high`, `model_version`, `scored_at`, `shap_features`) from a prior migration; if not, this feature adds them.
- The scorer service co-locates with the trainer in `services/ml/` as a new `estategap_ml/scorer/` submodule.
- KNN comparables use the same feature vector as the main model, normalised with a per-zone `StandardScaler`.
- The NATS `enriched.listings` and `scored.listings` subjects already exist from the enrichment pipeline (feature 013-enrichment-change-detection).
