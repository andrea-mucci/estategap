# Feature: ML Scoring Service & Explainability

## /plan prompt

```
Implement with these technical decisions:

## Scorer (services/ml/scorer/)
- gRPC server on port 50051
- Model loading: on startup, query model_versions WHERE is_active = true per country. Download ONNX artifacts from MinIO. Load into ONNX Runtime InferenceSession. Store in dict[country] → session.
- Hot reload: background task polls model_versions every 60s. If new active version detected → download + swap.
- Batch mode: NATS consumer on enriched.listings. Process in micro-batches of 50 for efficiency. Score → write to DB (UPDATE listings SET estimated_price, deal_score, deal_tier, confidence_low, confidence_high, model_version, scored_at) → publish to scored.listings.
- On-demand: gRPC ScoreListing → apply feature engineering → ONNX inference → return ScoringResult.
- Confidence interval: train separate quantile regression models (alpha=0.05 and alpha=0.95) alongside the main model. Export both to ONNX. Inference returns: point estimate (main model), lower bound (q05), upper bound (q95).

## SHAP
- SHAP TreeExplainer with LightGBM model (not ONNX, keep LightGBM .txt format for SHAP compatibility)
- Compute for Tier 1-2 only (performance optimization)
- Human-readable labels: mapping dict from feature name → template string. E.g., "zone_median_price_m2" → "Zone median price of {value}€/m² {direction} the estimate"
- Store in listings.shap_features JSONB: [{"feature": "zone_median_price_m2", "value": 4800, "shap_value": 15000, "label": "Zone median price..."}]

## Comparables
- NearestNeighbors with n_neighbors=5, metric='euclidean' on normalized feature matrix
- Precompute per zone: load all active listings in zone, compute feature matrix, fit KNN. Cache in memory. Refresh every hour via background task.
- Query: transform target listing → kneighbors() → return listing IDs + distances
```
