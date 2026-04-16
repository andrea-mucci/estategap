# Feature: ML Scoring Service & Explainability

## /specify prompt

```
Build the ML inference service that scores listings in real-time and provides deal explanations.

## What
1. ML Scorer Service (Python): gRPC service implementing MLScoringService. Loads latest active ONNX model per country from MinIO. Two modes: (a) batch mode — NATS consumer on enriched.listings, scores each listing, writes results to DB, publishes to scored.listings; (b) on-demand mode — gRPC ScoreListing RPC for real-time single-listing scoring (used by API for manual valuation). Computes: estimated_price, deal_score = (estimated - asking) / estimated * 100, deal_tier (1-4), confidence interval (90% via quantile regression or bootstrap).

2. SHAP Explainability: for Tier 1 and Tier 2 deals, compute SHAP values using TreeExplainer. Extract top 5 features with human-readable descriptions (e.g., "Zone median price €4,800/m² pushes estimate up"). Store as JSONB in listing row. Cache results per model version.

3. Comparable Properties Finder: KNN on feature space to find 5 most similar listings in the same zone. Uses scikit-learn NearestNeighbors with precomputed feature matrix per zone (refreshed hourly).

## Acceptance Criteria
- Single listing scored in < 100ms. Batch of 100 in < 3s.
- Model hot-reload when new version registered (no restart needed)
- SHAP top 5 features returned with human-readable labels
- Comparables are in same city, similar area/rooms/type
- gRPC endpoint works from api-gateway
- Deal score and tier match expected values for known test listings
```
