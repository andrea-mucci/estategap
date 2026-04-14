# Feature: Feature Engineering & Model Training

## /plan prompt

```
Implement with these technical decisions:

## Feature Engineering (services/ml/features/)
- FeatureEngineer class with fit(df) and transform(df) methods (sklearn Pipeline compatible)
- Spatial features: precompute zone-level stats (median_price_m2, listing_density, avg_income) as lookup table refreshed before training. Distance features via Haversine formula.
- Encoding: sklearn OrdinalEncoder for energy_cert (A=7..G=1), condition (new=4, good=3, renovate=2, to_renovate=1). OneHotEncoder for property_type. Cyclical encoding: month_sin = sin(2π*month/12), month_cos = cos(2π*month/12).
- Missing values: sklearn SimpleImputer (median/mode). Track missingness as binary feature (e.g., has_energy_cert).
- Output: numpy array + feature name list. Serializable via joblib.

## Training (services/ml/trainer/)
- Data export: SQL query joining listings + zone_statistics. Filter: status IN ('sold', 'delisted') OR days_on_market > 30.
- Target variable: asking_price (EUR normalized). For sold listings use final price if available.
- Optuna objective: minimize MAPE on validation set. Search space: num_leaves [31-255], learning_rate [0.01-0.3], n_estimators [100-1000], min_child_samples [5-100], subsample [0.6-1.0], colsample_bytree [0.6-1.0].
- ONNX export: skl2onnx or lightgbm built-in ONNX converter.
- MLflow: log params, metrics, model artifact, feature importance plot.
- Champion/challenger: compare new model MAPE vs model_versions WHERE is_active = true. If new < current * 0.98 (2% improvement threshold) → promote.

## Per-Country Models
- Train separate model per country when > 5,000 listings available
- For countries with < 5,000: transfer learning approach — use Spain model as base, fine-tune on local data with reduced learning rate (0.01)
- Model naming: "{country}_{city_or_national}_v{version}" e.g., "es_national_v12"
```
