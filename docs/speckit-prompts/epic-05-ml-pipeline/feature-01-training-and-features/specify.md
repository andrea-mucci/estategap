# Feature: Feature Engineering & Model Training

## /specify prompt

```
Build the ML training pipeline: feature engineering, model training with hyperparameter tuning, and model registry.

## What
1. Feature Engineering (Python): transforms a listing DB row into a numeric feature vector (~35 features). Categories: spatial (lat, lon, distance to metro/center/coast, zone median price, zone listing density, zone avg income), physical (area, rooms, bathrooms, floor, elevator, parking, terrace, orientation), condition (building age, energy cert, renovation state), contextual (building floors, community fees, property type), temporal (month sin/cos encoding), derived (usable/built ratio, price vs zone median, photo count, data completeness). Missing value handling: median for numerical, mode for categorical. Categorical encoding: ordinal for ordered (energy cert, condition), one-hot for nominal (property type, orientation).

2. Model Training Pipeline (Python): (a) export training dataset from PostgreSQL (listings with known prices, > 30 days on market or sold), (b) train/val/test split 70/15/15 stratified by city, (c) LightGBM with Optuna hyperparameter tuning (50 trials), (d) evaluate on test set: MAE, MAPE, R² globally and per major city, (e) if MAPE improves vs current champion: export to ONNX, register in MLflow, upload to MinIO, update model_versions table, (f) log all metrics and parameters to MLflow.

3. K8s CronJob: runs weekly (Sunday 3 AM UTC). On success: new model activated. On failure: alert sent, previous model stays active.

## Acceptance Criteria
- Feature vector generated for 10k+ Spanish listings with no NaN/Inf
- LightGBM MAPE < 12% nationally, < 10% for Madrid and Barcelona
- ONNX export loads successfully in ONNX Runtime
- MLflow experiment shows all runs with metrics and parameters
- CronJob executes weekly without manual intervention
- Champion/challenger promotion works correctly
```
