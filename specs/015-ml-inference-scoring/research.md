# Research: ML Inference & Scoring

**Phase**: 0 — Research & Decisions
**Date**: 2026-04-17
**Feature**: specs/015-ml-inference-scoring

---

## Decision 1: Three-ONNX-Session Strategy for Confidence Intervals

**Decision**: Train three LightGBM models per country — point estimate (`objective=regression`), lower bound (`objective=quantile, alpha=0.05`), upper bound (`objective=quantile, alpha=0.95`) — and export each to a separate ONNX file. At inference time, load three `onnxruntime.InferenceSession` objects per country. A single feature vector is run through all three sessions simultaneously.

**Rationale**:
- Quantile regression is natively supported by LightGBM (`objective=quantile`) and produces statistically valid prediction intervals without bootstrapping overhead (no need to run N resampling iterations per request).
- Exporting each quantile model as a separate ONNX file keeps the per-session memory footprint small (< 50 MB each) and allows independent hot-swapping if one quantile model needs retraining.
- At < 100ms latency budget, running three ONNX sessions sequentially is well within budget: ONNX Runtime CPU inference on a single float32 vector of 36 features takes ~0.3–0.8ms per session. Three sessions = ~2ms worst-case.
- Alternative (bootstrap CI): requires 100+ predictions per listing → ~80–200ms, violates the < 100ms budget.
- Alternative (single ONNX with multiple outputs): LightGBM ONNX export via `onnxmltools` does not support multi-objective output in one graph.

**MinIO artefact convention** (per version tag):
```
models/{version_tag}.onnx           # point estimate
models/{version_tag}_q05.onnx       # lower bound (α=0.05)
models/{version_tag}_q95.onnx       # upper bound (α=0.95)
models/{version_tag}.lgb            # LightGBM text model (SHAP only)
models/{version_tag}_feature_engineer.joblib
```

**Impact on trainer** (feature 014): Trainer must additionally call `lgb.train()` twice with `objective='quantile'` for alpha=0.05 and alpha=0.95, then export two more ONNX files. The `artifact_path` in `model_versions` stays pointing to the main ONNX; the scorer derives q05/q95 paths by convention.

---

## Decision 2: LightGBM Text Model for SHAP (Not ONNX)

**Decision**: Keep a LightGBM `.txt` model file (saved via `booster.save_model()`) alongside the ONNX artefacts in MinIO. The SHAP `TreeExplainer` is instantiated from the loaded `lgb.Booster` (not from ONNX), and is cached per model version in a `dict[str, shap.TreeExplainer]`.

**Rationale**:
- SHAP `TreeExplainer` does not support ONNX models. It requires the native LightGBM booster object with its internal tree structure.
- Loading a LightGBM `.txt` model is fast (< 200ms) and memory-efficient (same booster representation in memory as training, ~20–60 MB for a 500-tree model).
- The LGB model produces identical predictions to the ONNX model on the same feature matrix (verified by the ONNX self-test in the trainer). SHAP values computed from the LGB model are therefore consistent with the ONNX point estimate.
- Caching one `TreeExplainer` per model version avoids re-instantiation (which takes ~500ms) on every SHAP call.

**Cache structure**:
```python
_shap_cache: dict[str, shap.TreeExplainer] = {}  # key: version_tag
```
Cache is invalidated when the `ModelBundle` for a country is replaced during hot-reload.

---

## Decision 3: gRPC Server — asyncio-native (`grpc.aio`)

**Decision**: Use `grpc.aio` (asyncio gRPC) for the server. The servicer methods are `async def`. The NATS consumer runs as a separate `asyncio.Task` in the same event loop.

**Rationale**:
- `grpc.aio` allows all I/O (NATS, PostgreSQL via asyncpg, ONNX inference) to share one event loop without threads. This is the recommended approach for Python 3.12.
- ONNX Runtime `InferenceSession.run()` is a blocking C++ call. For the < 100ms latency budget, a single 36-feature inference takes < 1ms, so calling it synchronously in an `async` method has no practical impact. If a future benchmark shows contention, it can be offloaded to a `ThreadPoolExecutor`.
- Alternative (synchronous gRPC server with threading): complicates sharing of asyncpg connection pool and NATS client.

**Server lifecycle**:
```python
async def serve():
    server = grpc.aio.server()
    add_MLScoringServicer_to_server(MLScoringServicer(...), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    asyncio.create_task(model_registry.poll_loop())   # hot-reload every 60s
    asyncio.create_task(nats_consumer.consume_loop()) # batch scoring
    asyncio.create_task(comparables.refresh_loop())   # KNN hourly
    await server.wait_for_termination()
```

---

## Decision 4: Model Hot-Reload Without Restart

**Decision**: A background `asyncio.Task` polls `model_versions WHERE status = 'active'` every 60 seconds. If `version_tag` has changed for any country, it downloads the new ONNX/LGB/joblib artefacts from MinIO into a temp path, constructs a new `ModelBundle`, and atomically replaces the entry in `dict[country_code] → ModelBundle` using a lock-free assignment (Python GIL guarantees atomic dict item assignment).

**Rationale**:
- Python's GIL ensures that `dict[key] = new_value` is atomic; no explicit lock is needed for the hot-swap of the model bundle reference.
- During download (which may take 2–10 seconds for large ONNX files), the old model bundle continues serving requests without interruption.
- The NATS `ml.training.completed` event (published by the trainer on promotion) could also trigger an immediate reload, but the 60-second poll is the primary mechanism because NATS events may be missed if the scorer restarts.
- Alternative (Kubernetes rolling restart): requires manual intervention; violates the hot-reload acceptance criterion.

**Hot-reload sequence**:
```
1. Poll DB → detect new version_tag for country "es"
2. Download artefacts to /tmp/{new_version_tag}/
3. Load ONNX sessions + LGB booster + FeatureEngineer
4. Construct ModelBundle(new_version)
5. Atomically: _bundles["es"] = new_bundle
6. Invalidate SHAP cache for old version
7. Log: "Hot-reloaded model es → {new_version_tag}"
```

---

## Decision 5: KNN Comparable Finder — Per-Zone In-Memory Index

**Decision**: Use `sklearn.neighbors.NearestNeighbors(n_neighbors=5, metric='euclidean', algorithm='ball_tree')` per zone. Feature matrix is normalised with `sklearn.preprocessing.StandardScaler` fitted on zone listings. A background task refreshes all zone indices hourly by re-fetching active listings from PostgreSQL.

**Rationale**:
- `ball_tree` is efficient for Euclidean distance on dense float matrices of dimension ~36. For zones with up to 10,000 listings, query time is < 5ms.
- In-memory indices avoid a round-trip to a vector database. With ~1,000 zones × 10,000 listings × 36 features × 4 bytes = ~1.4 GB worst-case per country — acceptable for a dedicated pod with 4 GB RAM.
- Hourly refresh is sufficient; new listings typically take minutes to be enriched and scored before a user would query comparables.
- Alternative (faiss): overkill for this scale; adds a C++ dependency.
- Alternative (PostgreSQL KNN with vector extension): adds infrastructure dependency (pgvector) not in the current stack.

**Feature subset for KNN**: The same 36-feature vector produced by `FeatureEngineer.transform()`. Using the same feature space as the price model ensures "similar in feature space" correlates with "similar in price model input" — the most relevant definition of comparable for valuation purposes.

**Zone index refresh**:
```python
# Pseudo-code for hourly refresh
async def refresh_zone_indices():
    rows = await db.fetch("SELECT id, zone_id, <features> FROM listings WHERE status='active' AND zone_id IS NOT NULL")
    by_zone = group_by(rows, key='zone_id')
    for zone_id, zone_rows in by_zone.items():
        matrix = feature_engineer.transform(to_dataframe(zone_rows))
        scaler = StandardScaler().fit(matrix)
        norm_matrix = scaler.transform(matrix)
        nn = NearestNeighbors(n_neighbors=5, metric='euclidean', algorithm='ball_tree')
        nn.fit(norm_matrix)
        _zone_indices[zone_id] = ZoneIndex(nn=nn, scaler=scaler, listing_ids=[r['id'] for r in zone_rows])
```

---

## Decision 6: Deal Tier Thresholds

**Decision**: Four tiers based on `deal_score = (estimated - asking) / estimated × 100`:

| Tier | Name | Condition |
|------|------|-----------|
| 1 | Great Deal | `deal_score >= 15` |
| 2 | Good Deal | `5 <= deal_score < 15` |
| 3 | Fair | `-5 <= deal_score < 5` |
| 4 | Overpriced | `deal_score < -5` |

**Rationale**:
- These thresholds are consistent with the `DealTier` IntEnum already defined in `estategap_common/models/scoring.py`.
- A 15% underpricing threshold for Tier 1 is common in automated valuation: it's large enough to signal genuine market mispricing (not model noise) while still being achievable.
- Thresholds are not configurable at runtime to keep the tier definition stable for alert rules and frontend display; changes require a code release.

---

## Decision 7: SHAP Feature Label Templates

**Decision**: A static `dict[str, str]` in `feature_labels.py` maps feature names to template strings. Formatting uses Python `.format(**ctx)` where `ctx` contains the feature value and a computed `direction` ("pushes estimate up" / "pulls estimate down").

**Sample mappings**:
```python
FEATURE_LABELS = {
    "zone_median_price_m2": "Zone median price of {value:,.0f}€/m² {direction} the estimate",
    "built_area_m2":        "{value:.0f}m² built area {direction} the estimate",
    "bedrooms":             "{value:.0f} bedrooms {direction} the estimate",
    "building_age_years":   "Building age of {value:.0f} years {direction} the estimate",
    "dist_metro_m":         "{value:,.0f}m to nearest metro {direction} the estimate",
    "dist_beach_m":         "{value:,.0f}m to nearest beach {direction} the estimate",
    "energy_cert_encoded":  "Energy certificate grade {direction} the estimate",
    "condition_encoded":    "Property condition {direction} the estimate",
    "floor_number":         "Floor {value:.0f} {direction} the estimate",
    "data_completeness":    "Listing data quality {direction} the estimate",
    # ... 36 total entries, one per feature name
}
```

`direction` = `"pushes estimate up"` if `shap_value > 0`, else `"pulls estimate down"`.

For features without a matching template, the label falls back to `f"{feature_name.replace('_', ' ').title()} {direction} the estimate"`.

---

## Decision 8: DB Schema — New Scoring Columns on `listings`

**Decision**: Add an Alembic migration (`017_listings_scoring_columns.py`) to the `services/pipeline/alembic/` directory (which owns all schema migrations). New columns added to the `listings` table:

```sql
ALTER TABLE listings ADD COLUMN IF NOT EXISTS estimated_price_eur  NUMERIC(14,2);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS deal_score            NUMERIC(6,2);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS deal_tier             SMALLINT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS confidence_low_eur    NUMERIC(14,2);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS confidence_high_eur   NUMERIC(14,2);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS model_version         VARCHAR(100);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS scored_at             TIMESTAMPTZ;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS shap_features         JSONB         NOT NULL DEFAULT '[]';
ALTER TABLE listings ADD COLUMN IF NOT EXISTS comparable_ids        UUID[];

CREATE INDEX listings_deal_tier_idx ON listings (deal_tier) WHERE deal_tier IS NOT NULL;
CREATE INDEX listings_scored_at_idx ON listings (scored_at) WHERE scored_at IS NOT NULL;
```

**Rationale**: Co-locating all scoring results on the `listings` row avoids a join in the API Gateway's listing detail query. JSONB for `shap_features` is flexible and queryable. `comparable_ids` is a simple UUID array (not a FK array) for performance; the API resolves them with a separate `IN` query.

---

## Decision 9: Alembic Migration Ownership

**Decision**: Migration `017_listings_scoring_columns.py` is added to `services/pipeline/alembic/versions/`. The pipeline service owns all schema migrations per the precedent established in feature 014. The scorer service reads and writes scoring columns but does not own the migration.

**Rationale**: Single migration source of truth in `services/pipeline/`. The scorer's Kubernetes Deployment has an `initContainer` that runs `alembic upgrade head` before the scorer starts, ensuring migrations are applied.

---

## Decision 10: Proto Contract — Extend Existing `ml_scoring.proto`

**Decision**: The existing `proto/estategap/v1/ml_scoring.proto` is extended to add fields for confidence interval and SHAP human-readable labels. The `ScoreListingResponse` gains `confidence_low`, `confidence_high`, and a richer `ShapValue` with `label`. See `contracts/grpc-ml-scoring.md` for the full diff.

**Rationale**: The existing proto is already defined with `ScoreListing`, `ScoreBatch`, and `GetComparables` RPCs. Adding fields follows Protobuf backward-compatibility rules (new fields are optional by default in proto3). The API Gateway already imports this proto.
