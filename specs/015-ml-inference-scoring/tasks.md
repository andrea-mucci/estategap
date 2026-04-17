# Tasks: ML Inference & Scoring

**Input**: Design documents from `specs/015-ml-inference-scoring/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to user story from spec.md (US1–US5)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Proto extension, dependency updates, scorer module scaffold, and config.

- [X] T001 Extend `proto/estategap/v1/ml_scoring.proto` with new fields: `estimated_price`, `asking_price`, `confidence_low`, `confidence_high`, `deal_tier`, `scored_at` on `ScoreListingResponse`; `label` on `ShapValue`; `distances` on `GetComparablesResponse` — per `contracts/grpc-ml-scoring.md`
- [X] T002 Run `buf generate` and commit generated stubs to `services/ml/proto/estategap/v1/ml_scoring_pb2.py` and `ml_scoring_pb2_grpc.py`
- [ ] T003 [P] Add `grpcio>=1.63`, `grpcio-tools>=1.63` to `services/ml/pyproject.toml` `[project.dependencies]`; run `uv sync`
- [X] T004 [P] Create `services/ml/estategap_ml/scorer/` directory with empty `__init__.py`; verify `uv run python -c "from estategap_ml import scorer"` succeeds
- [X] T005 [P] Extend `services/ml/estategap_ml/config.py` with scorer settings: `grpc_port: int = 50051`, `scorer_batch_size: int = 50`, `scorer_batch_flush_seconds: int = 5`, `model_poll_interval_seconds: int = 60`, `comparables_refresh_interval_seconds: int = 3600`, `shap_timeout_seconds: float = 2.0`, `prometheus_port: int = 9091`; add corresponding `alias` fields and update `.env.example`

**Checkpoint**: `buf generate` succeeds, proto stubs exist, scorer package importable, config extended.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database migration, shared Pydantic events, ModelBundle loading, feature label map, core inference math, and DB writer — all required before any user story can run end-to-end.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Write Alembic migration `services/pipeline/alembic/versions/017_listings_scoring_columns.py` adding columns `estimated_price_eur NUMERIC(14,2)`, `deal_score NUMERIC(6,2)`, `deal_tier SMALLINT`, `confidence_low_eur NUMERIC(14,2)`, `confidence_high_eur NUMERIC(14,2)`, `model_version VARCHAR(100)`, `scored_at TIMESTAMPTZ`, `shap_features JSONB NOT NULL DEFAULT '[]'`, `comparable_ids UUID[]` to `listings` plus indexes `listings_deal_tier_idx` and `listings_scored_at_idx` — per `data-model.md § 1`
- [X] T007 [P] Add `ScoredListingEvent` and `ShapFeatureEvent` Pydantic models to `libs/common/estategap_common/models/scoring.py`; extend `__all__`; verify `from estategap_common.models.scoring import ScoredListingEvent` works
- [X] T008 [P] Create `services/ml/estategap_ml/scorer/feature_labels.py` with `FEATURE_LABELS: dict[str, str]` mapping all 36 feature names to template strings and `render_label(feature_name, value, shap_value) -> str` function with fallback for unknown features — per `research.md § Decision 7`
- [X] T009 Implement `services/ml/estategap_ml/scorer/model_registry.py`:
  - `ModelBundle` dataclass (three `ort.InferenceSession` fields, `lgb.Booster`, `FeatureEngineer`, `input_name`, `feature_names`, `loaded_at`)
  - `download_bundle(version_tag, artifact_path, bucket) -> ModelBundle` — downloads five artefacts (`.onnx`, `_q05.onnx`, `_q95.onnx`, `.lgb`, `_feature_engineer.joblib`) from MinIO via boto3 to `/tmp/{version_tag}/` and loads them
  - `ModelRegistry` class with `bundles: dict[str, ModelBundle]`, `async load_active_models(db_pool, s3_client)` (startup), and stub `async poll_loop()` (returns immediately — filled in US5/Phase 7)
- [X] T010 Implement `services/ml/estategap_ml/scorer/inference.py`:
  - `run_onnx(session, feature_matrix) -> np.ndarray` (wraps `session.run()`)
  - `score_listing(bundle, listing_row) -> ScoringResult` — calls `bundle.feature_engineer.transform()`, runs all three ONNX sessions, computes `deal_score = (est - asking) / est * 100`, assigns `deal_tier` per thresholds in `research.md § Decision 6`, returns `ScoringResult` (from `estategap_common`)
  - `DEAL_TIER_THRESHOLDS` constant
- [X] T011 Implement `services/ml/estategap_ml/scorer/db_writer.py`:
  - `async write_scores(pool, results: list[ScoringResult]) -> None` — executes `executemany` `UPDATE listings SET estimated_price_eur=$1, deal_score=$2, deal_tier=$3, confidence_low_eur=$4, confidence_high_eur=$5, model_version=$6, scored_at=$7, shap_features=$8::jsonb, comparable_ids=$9::uuid[] WHERE id=$10 AND country_code=$11` via asyncpg

**Checkpoint**: Migration applies cleanly (`alembic upgrade head`). `inference.score_listing()` returns a `ScoringResult` with correct deal tier for a hand-crafted listing row. `db_writer.write_scores()` updates the DB.

---

## Phase 3: User Story 1 — Automated Batch Scoring (Priority: P1) 🎯 MVP

**Goal**: NATS consumer on `enriched.listings` processes micro-batches of 50, writes scoring columns to DB, publishes `scored.listings` events.

**Independent Test**: Publish a synthetic enriched listing to `enriched.listings`; assert within 5s that the `listings` row has non-null `estimated_price_eur`, `deal_score`, `deal_tier`, `scored_at`, and a `scored.listings` message is received.

- [X] T012 [US1] Implement `services/ml/estategap_ml/scorer/nats_consumer.py`:
  - `NatsConsumer` class with asyncpg pool, `ModelRegistry`, NATS JS client
  - `async consume_loop()` — durable JetStream subscribe to `enriched.listings` (durable: `scorer-group`, ack explicit, max_ack_pending: 200)
  - Accumulate messages into micro-batch up to `config.scorer_batch_size` or `config.scorer_batch_flush_seconds`, whichever fires first
  - For each batch: fetch listing details from DB, call `inference.score_listing()` per row, call `db_writer.write_scores()`, publish `ScoredListingEvent` to `scored.listings` via NATS JS, ACK all messages
  - NAK with 30s delay on transient DB/NATS errors (up to 3 retries); Term on missing model for country
- [X] T013 [US1] Write integration test `services/ml/tests/integration/test_nats_consumer.py`:
  - Spin up PostgreSQL (testcontainers), seed one listing row, register a mock `ModelBundle` in `ModelRegistry`
  - Publish one enriched listing event to NATS, await up to 5s, assert `listings.deal_tier IS NOT NULL` and `scored.listings` received
- [X] T014 [US1] Write acceptance test `services/ml/tests/acceptance/test_scoring_e2e.py`:
  - Parametrised with 6 known test listings (listing_id + expected deal_score ± 0.1%)
  - End-to-end: publish enriched event → wait → assert DB row matches expected values
  - Requires a real model bundle in MinIO (seeded fixture)

**Checkpoint**: `pytest tests/integration/test_nats_consumer.py` passes. Batch scoring observable end-to-end with `python -m estategap_ml.scorer` running locally.

---

## Phase 4: User Story 2 — On-Demand Scoring via gRPC (Priority: P1)

**Goal**: `ScoreListing` and `ScoreBatch` RPCs return a complete `ScoreListingResponse` within 100ms (single listing).

**Independent Test**: Call `ScoreListing` via grpcurl with a known listing ID; assert response contains `estimated_price`, `confidence_low`, `confidence_high`, `deal_tier`, `model_version` within 100ms.

- [X] T015 [US2] Implement `services/ml/estategap_ml/scorer/servicer.py`:
  - `MLScoringServicer(MLScoringServiceServicer)` class
  - `async ScoreListing(request, context)` — validate UUID + country, check `ModelRegistry` has bundle, fetch listing row from DB, call `inference.score_listing()`, call `db_writer.write_scores()`, publish `ScoredListingEvent`, build and return `ScoreListingResponse` proto
  - `async ScoreBatch(request, context)` — validate `len(listing_ids) <= 500`, fan out to `score_listing` for each, return `ScoreBatchResponse`; reject with `RESOURCE_EXHAUSTED` if > 500
  - Error mapping: `NOT_FOUND`, `FAILED_PRECONDITION`, `INVALID_ARGUMENT`, `INTERNAL` per `contracts/grpc-ml-scoring.md`
  - `GetComparables` stub: return empty `GetComparablesResponse` (implemented in Phase 6)
- [X] T016 [US2] Implement `services/ml/estategap_ml/scorer/server.py`:
  - `async serve(config, registry, db_pool, nats_client)` — creates `grpc.aio.server()`, registers `MLScoringServicer`, adds insecure port `[::]:config.grpc_port`, starts server, spawns `registry.poll_loop()`, `nats_consumer.consume_loop()`, and `comparables.refresh_loop()` (stubs) as `asyncio.Task`, awaits `server.wait_for_termination()`
- [X] T017 [US2] Implement `services/ml/estategap_ml/scorer/__main__.py`:
  - Wires together: `Config()` → asyncpg pool → boto3 S3 client → `ModelRegistry.load_active_models()` → `NatsConsumer` → `MLScoringServicer` → `serve()`
  - Structured startup logs via structlog
  - Fails fast (exit 1) if no active model found for any configured country
- [X] T018 [US2] Update `services/ml/main.py` to accept `--mode [trainer|scorer]` CLI flag and dispatch to `estategap_ml.trainer.__main__.main` or `estategap_ml.scorer.__main__.main`
- [X] T019 [US2] Write unit tests `services/ml/tests/unit/test_inference.py`:
  - `test_deal_score_calculation` — parametrised table: `(estimated, asking, expected_deal_score, expected_tier)`
  - `test_deal_tier_boundaries` — boundary values at 15%, 5%, -5%
  - Uses a mock `ModelBundle` with a trivial ONNX model (identity or constant output)
- [X] T020 [US2] Write integration test `services/ml/tests/integration/test_scorer_grpc.py`:
  - Start `grpc.aio.server` in-process with mock `ModelRegistry` and test DB
  - Call `ScoreListing` — assert status OK, all response fields populated, latency < 100ms
  - Call `ScoreBatch` with 100 IDs — assert 100 results, wall-clock < 3s
  - Call `ScoreListing` with unknown listing_id — assert `NOT_FOUND`
  - Call `ScoreListing` with unknown country — assert `FAILED_PRECONDITION`

**Checkpoint**: `pytest tests/unit/test_inference.py tests/integration/test_scorer_grpc.py` all pass. `grpcurl` against local scorer returns full `ScoreListingResponse` in < 100ms.

---

## Phase 5: User Story 3 — Deal Explanation / SHAP (Priority: P2)

**Goal**: Tier 1 and Tier 2 listings have `shap_features` JSONB populated with top-5 human-readable feature explanations.

**Independent Test**: Score a Tier 1 listing; assert `listings.shap_features` is a JSON array of exactly 5 objects each with non-empty `label` string. Score a Tier 3 listing; assert `shap_features = []`.

- [X] T021 [US3] Implement `services/ml/estategap_ml/scorer/shap_explainer.py`:
  - `ShapExplainer` class with `_cache: dict[str, shap.TreeExplainer]` (keyed by `version_tag`)
  - `get_explainer(bundle: ModelBundle) -> shap.TreeExplainer` — constructs `shap.TreeExplainer(bundle.lgb_booster)` on first call, caches by `bundle.version_tag`
  - `async compute_shap(bundle, feature_matrix, feature_names, timeout_seconds) -> list[ShapFeature]` — runs TreeExplainer under `asyncio.wait_for`, selects top-5 by `|shap_value|`, renders labels via `feature_labels.render_label()`, returns `[]` on timeout
  - `invalidate(version_tag: str)` — removes entry from cache on hot-reload
- [X] T022 [US3] Integrate SHAP into `services/ml/estategap_ml/scorer/inference.py`:
  - `score_listing()` now accepts optional `shap_explainer: ShapExplainer | None`
  - If `deal_tier in {1, 2}` and explainer provided: call `compute_shap()`, attach result to `ScoringResult.shap_features`
  - Otherwise: `shap_features = []`
- [X] T023 [US3] Wire `ShapExplainer` into `servicer.py` (`ScoreListing`, `ScoreBatch`) and `nats_consumer.py` (batch path), passing instance created in `__main__.py`
- [X] T024 [US3] Write unit tests `services/ml/tests/unit/test_shap_explainer.py`:
  - `test_top5_features_returned` — mock TreeExplainer returning synthetic SHAP values; assert exactly 5 results ordered by |shap_value|
  - `test_label_rendering` — parametrised: `(feature_name, value, shap_value, expected_label_fragment)` for 5 feature templates
  - `test_cache_hit` — assert `get_explainer()` called twice returns same object (no re-instantiation)
  - `test_timeout_returns_empty` — explainer that sleeps > timeout returns `[]`

**Checkpoint**: `pytest tests/unit/test_shap_explainer.py` passes. A locally scored Tier 1 listing has 5 labelled SHAP features in `listings.shap_features`. A Tier 3 listing has `[]`.

---

## Phase 6: User Story 4 — Comparable Properties (Priority: P2)

**Goal**: `GetComparables` RPC returns 5 nearest listings in the same zone within 50ms when KNN index is warm.

**Independent Test**: Call `GetComparables` for a listing in a zone with ≥ 10 active listings; assert 5 results returned, all in the same city, area within 30%, room count within 1, same property type.

- [X] T025 [US4] Implement `services/ml/estategap_ml/scorer/comparables.py`:
  - `ZoneIndex` dataclass: `zone_id: UUID`, `nn: NearestNeighbors`, `scaler: StandardScaler`, `listing_ids: list[UUID]`, `built_at: datetime`
  - `ComparablesFinder` class with `_indices: dict[UUID, ZoneIndex]`
  - `async refresh_zone_indices(db_pool, feature_engineer)` — fetches all `status='active'` listings with `zone_id IS NOT NULL` from DB, groups by `zone_id`, fits `StandardScaler` + `NearestNeighbors(n_neighbors=min(5,n), metric='euclidean', algorithm='ball_tree')` per zone, stores in `_indices`
  - `async refresh_loop()` — calls `refresh_zone_indices()` on startup then every `config.comparables_refresh_interval_seconds`
  - `get_comparables(listing_row, feature_engineer, limit=5) -> list[tuple[UUID, float]]` — transforms listing, looks up `_indices[zone_id]`, calls `nn.kneighbors()`, returns `(listing_id, distance)` pairs; returns `[]` if zone not in index
- [X] T026 [US4] Implement `GetComparables` RPC in `services/ml/estategap_ml/scorer/servicer.py` (replace stub):
  - Fetch listing row from DB; call `comparables_finder.get_comparables()`; bulk-fetch comparable listing rows; build `GetComparablesResponse` with `comparables` (full `Listing` protos) and `distances` parallel array
  - Return `NOT_FOUND` if listing missing; return empty response (no error) if zone index not built
- [X] T027 [US4] Wire `ComparablesFinder` into `server.py` and `__main__.py`: instantiate, call `refresh_zone_indices()` at startup, pass to servicer
- [X] T028 [US4] Write unit tests `services/ml/tests/unit/test_comparables.py`:
  - `test_knn_returns_5_nearest` — synthetic 20-listing zone; assert 5 results, ordered by distance ascending
  - `test_empty_zone_returns_empty` — zone with 0 listings returns `[]` without error
  - `test_small_zone_returns_all` — zone with 3 listings returns 3 results (not error)
  - `test_distance_ordering` — first result is closer than last result
- [X] T029 [US4] Write integration test `services/ml/tests/integration/test_scorer_grpc.py` (extend existing):
  - Add `test_get_comparables_warm_cache` — seed zone with 10 listings, refresh index, call `GetComparables`, assert 5 results within latency target
  - Add `test_get_comparables_cold_cache` — no zone index built; assert empty response, no error

**Checkpoint**: `pytest tests/unit/test_comparables.py` passes. `GetComparables` via grpcurl returns 5 comparable listings within 50ms on warm cache.

---

## Phase 7: User Story 5 — Model Hot-Reload (Priority: P2)

**Goal**: When a new model version is registered as active in `model_versions`, the scorer picks it up within 60 seconds without restart.

**Independent Test**: With scorer running, insert a new `model_versions` row with `status='active'`, wait ≤ 60s, verify subsequent `ScoreListing` responses report the new `model_version` string.

- [X] T030 [US5] Complete `ModelRegistry.poll_loop()` in `services/ml/estategap_ml/scorer/model_registry.py`:
  - Every `config.model_poll_interval_seconds` seconds: query `model_versions WHERE status='active'` per country
  - Compare `version_tag` against `self.bundles[country].version_tag`
  - On change: call `download_bundle()` for new version, atomically assign `self.bundles[country] = new_bundle`, call `shap_explainer.invalidate(old_version_tag)`, emit structlog info event with old/new version tags
  - No restart required; existing requests served by old bundle during download
- [X] T031 [US5] Add `ml.training.completed` NATS subscription in `services/ml/estategap_ml/scorer/model_registry.py`:
  - Non-durable `nc.subscribe("ml.training.completed", cb=_on_model_promoted)`
  - Callback extracts `country_code` and `model_version_tag` from event payload, triggers immediate `download_bundle()` + swap for that country (bypassing the 60s poll interval)
- [X] T032 [US5] Wire `ml.training.completed` subscription into `server.py` startup sequence (called after NATS client is connected)
- [X] T033 [US5] Write integration test `services/ml/tests/integration/test_scorer_grpc.py` (extend):
  - `test_hot_reload_within_60s` — insert new `model_versions` row with `status='active'` (with real artefacts in MinIO test bucket); wait up to 60s polling `ScoreListing`; assert `model_version` in response transitions to new tag
  - `test_serving_during_reload` — while reload in progress (mock slow download), fire `ScoreListing`; assert OK response using old model version

**Checkpoint**: Hot-reload integration test passes. `model_version` in `ScoreListing` response transitions to new tag within 60s without any process restart.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Prometheus instrumentation, Kubernetes/Helm integration, Dockerfile update, and final acceptance validation.

- [X] T034 [P] Add Prometheus metrics to `services/ml/estategap_ml/scorer/inference.py` and `nats_consumer.py`:
  - `scorer_inference_duration_seconds` Histogram (labels: `country`, `mode`)
  - `scorer_batch_size` Histogram (label: `country`)
  - Record around `score_listing()` and the NATS micro-batch flush
- [X] T035 [P] Add Prometheus metrics to `services/ml/estategap_ml/scorer/model_registry.py` and `shap_explainer.py`:
  - `scorer_active_model_version` Gauge (label: `country`) — set on load and on hot-reload
  - `scorer_shap_errors_total` Counter (label: `country`) — increment on SHAP timeout/failure
  - `scorer_model_reload_total` Counter (label: `country`) — increment on successful hot-reload
- [X] T036 [P] Add Prometheus metrics to `services/ml/estategap_ml/scorer/comparables.py`:
  - `scorer_comparables_cache_hit_ratio` Gauge — updated on each `get_comparables()` call
- [X] T037 [P] Start Prometheus HTTP server on `config.prometheus_port` in `services/ml/estategap_ml/scorer/__main__.py` using `prometheus_client.start_http_server()`
- [X] T038 Update `services/ml/Dockerfile`:
  - Add `ARG SERVICE_MODE=scorer` / `ENV SERVICE_MODE=${SERVICE_MODE}`
  - Change `CMD` to `["python", "-m", "estategap_ml", "--mode", "${SERVICE_MODE}"]`
  - Ensure proto stubs are copied into image (`COPY proto/ proto/`)
- [X] T039 Add `ml-scorer` Kubernetes `Deployment` to `helm/estategap/templates/ml-scorer-deployment.yaml`:
  - Image: `estategap/ml-scorer`, env from `ml-scorer-secrets` Sealed Secret
  - `initContainer`: `alembic upgrade head` (applies migration 017)
  - Resources: `requests: {memory: 2Gi, cpu: 500m}`, `limits: {memory: 4Gi, cpu: 2}`
  - Liveness probe: gRPC health check on port 50051
  - Readiness probe: waits until `ModelRegistry.bundles` non-empty (custom `/health` endpoint or gRPC health)
- [X] T040 [P] Add `ml-scorer` `Service` (ClusterIP, port 50051) to `helm/estategap/templates/ml-scorer-service.yaml` so `api-gateway` can reach the gRPC endpoint
- [X] T041 [P] Add `ml-scorer` values block to `helm/estategap/values.yaml` and `values-staging.yaml` (image, replicas, env overrides)
- [ ] T042 Run full acceptance test suite `pytest tests/acceptance/test_scoring_e2e.py -v -s` against staging environment with seeded test listings; assert all 6 parametrised deal-score values match expected ± 0.1%

**Checkpoint**: Helm lint passes. Scorer deploys to staging. All acceptance tests pass. Prometheus metrics visible in Grafana.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T003, T004, T005 in parallel after T001+T002
- **Foundational (Phase 2)**: Depends on Phase 1 complete — T007, T008, T009 in parallel after T006 applies migration
- **Phase 3 (US1)**: Depends on Phase 2 complete — T013, T014 after T012
- **Phase 4 (US2)**: Depends on Phase 2 complete — T015→T016→T017→T018; T019 and T020 in parallel after T015
- **Phase 5 (US3)**: Depends on Phase 4 complete — T021→T022→T023; T024 in parallel with T022
- **Phase 6 (US4)**: Depends on Phase 4 complete — T025→T026→T027; T028, T029 after T025
- **Phase 7 (US5)**: Depends on Phase 4 complete — T030→T031→T032; T033 after T031
- **Polish (Phase 8)**: Depends on all Phase 3–7 complete — T034–T037 in parallel; T038→T039→T040→T041→T042

### User Story Dependencies

- **US1 (P1)**: After Foundational — core batch scoring, no US dependency
- **US2 (P1)**: After Foundational — core gRPC, no US dependency; US1 and US2 can be developed in parallel
- **US3 (P2)**: After US2 (needs servicer.py to wire into)
- **US4 (P2)**: After US2 (needs servicer.py stub to replace)
- **US5 (P2)**: After US2 (needs server.py lifecycle to add subscription to); US3, US4, US5 can proceed in parallel after US2

### Parallel Opportunities Within Phases

**Phase 1**: T003, T004, T005 all parallel after T001–T002 complete.
**Phase 2**: T007, T008, T009 all parallel; T010 and T011 parallel after T009 complete.
**Phase 3**: T013 and T014 both start after T012; T014 can be run after staging seeded.
**Phase 4**: T019 and T020 parallel after T015; T016 and T018 parallel after T015.
**Phase 5**: T022 and T024 parallel after T021.
**Phase 6**: T028 parallel with T025; T029 after T026.
**Phase 8**: T034, T035, T036, T037, T040, T041 all parallel; T039 after T038.

---

## Parallel Example: Phase 2 (Foundational)

```text
After T006 (migration applied):

  Parallel group A:
    Task T007: Add ScoredListingEvent to estategap_common/models/scoring.py
    Task T008: Create feature_labels.py with all 36 templates
    Task T009: Implement ModelRegistry (ModelBundle + download_bundle + load_active_models)

  After A completes → Parallel group B:
    Task T010: Implement inference.py (score_listing + deal_tier logic)
    Task T011: Implement db_writer.py (executemany UPDATE listings)
```

## Parallel Example: US1 + US2 (both P1, concurrent teams)

```text
After Phase 2 complete:

  Team A (US1 — Batch Scoring):
    T012 → T013 → T014

  Team B (US2 — On-Demand gRPC):
    T015 → T016 → T017 → T018 (sequential)
    T019, T020 parallel after T015

  Teams merge in Phase 5 when SHAP is wired into both paths.
```

---

## Implementation Strategy

### MVP First (US1 + US2 only)

1. Complete Phase 1: Setup (proto, deps, scaffold, config)
2. Complete Phase 2: Foundational (migration, ModelBundle, inference, db_writer)
3. Complete Phase 3: US1 — batch scoring via NATS
4. Complete Phase 4: US2 — on-demand gRPC
5. **STOP and VALIDATE**: `pytest tests/unit/ tests/integration/` all pass; grpcurl returns correct `ScoreListingResponse` with deal tier; batch scoring writes to DB
6. Ship MVP — deal scores visible in the API and on the frontend

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 → Core scoring live (MVP)
3. US3 (SHAP) → Deal explanations for Tier 1–2 listings
4. US4 (Comparables) → Comparable properties in listing detail view
5. US5 (Hot-reload) → Zero-downtime model updates
6. Polish → Observability + Kubernetes production readiness

---

## Notes

- **[P]** tasks operate on different files and have no incomplete-task dependencies — safe to run concurrently
- **[USN]** label traces each task back to its user story for traceability
- Run `alembic upgrade head` (T006) before any scorer code that touches the `listings` table
- ONNX stubs required (T001–T002) before any import of `ml_scoring_pb2`
- Each user story has an explicit checkpoint — validate before advancing to the next phase
- SHAP (US3) intentionally comes after the gRPC layer (US2) is stable to avoid wiring complexity
- Comparables (US4) and Hot-reload (US5) are independent of each other post-US2 and can be parallelised
