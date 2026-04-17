# ML Country Models Contract

**Feature**: 026-us-spiders-country-ml  
**Date**: 2026-04-17

---

## Model Artefact Storage (MinIO)

### Path Convention

```
ml-models/
└── {country_lower}/
    ├── champion/
    │   ├── model.onnx              # ONNX runtime model (inference)
    │   ├── model.txt               # LightGBM text dump (transfer learning source)
    │   ├── feature_engineer.joblib # Fitted FeatureEngineer (scaler + encoders)
    │   └── metadata.json           # Version tag, MAPE, confidence, trained_at
    └── {version_tag}/
        └── ... (same structure as champion/)
```

**`metadata.json` schema**:
```json
{
  "version_tag": "us_202604_v1",
  "country": "US",
  "trained_at": "2026-04-17T10:00:00Z",
  "listing_count": 4200,
  "mape": 0.089,
  "confidence": "transfer",
  "transfer_learned": true,
  "base_country": "ES",
  "major_metro_mape": {
    "new_york_city": 0.094,
    "los_angeles": 0.103
  }
}
```

---

## Training Pipeline Contract

### Trigger

The trainer is invoked by the scrape orchestrator via NATS subject:

```
ml.training.requested   →  payload: { "country": "US", "triggered_by": "scheduler" }
```

Or manually:
```bash
python -m estategap_ml.trainer --country us
python -m estategap_ml.trainer --countries-all
```

### Training Decision Logic

```
get_listing_count(country) → count
  count < 1000   → skip (publish TrainingSkippedEvent, no model artefact)
  count < 5000   → transfer_train(country, base_country="ES", lr=0.01, n_iter=100)
                   → if MAPE > 0.20: confidence = "insufficient_data"
                   → else:           confidence = "transfer"
  count >= 5000  → full_train(country)
                   → confidence = "full"
```

### Output Events (NATS)

```
ml.training.completed  →  { country, version_tag, mape, confidence, promoted: bool }
ml.training.failed     →  { country, error, traceback }
ml.training.skipped    →  { country, reason: "insufficient_data", count }
```

---

## Scorer Dispatch Contract

### gRPC Method (existing, extended)

```protobuf
// Existing method in proto/ml/scorer.proto
rpc ScoreListings(ScoreListingsRequest) returns (ScoreListingsResponse);

// ScoreListingsRequest.listing.country drives model selection
// No proto change needed — country field already present
```

### Model Selection Logic (scorer-side)

```python
def get_model_for_listing(listing: Listing) -> LoadedModel | HeuristicFallback:
    champion = db.get_champion_model(country=listing.country)
    if champion is None or champion.confidence == "insufficient_data":
        return HeuristicFallback(listing.zone.median_price_eur_m2)
    return load_model_from_minio(champion.country, champion.version_tag)
```

### ScoredListing Response Extension

```python
class ScoredListing(BaseModel):
    # ... existing fields ...
    scoring_method: Literal["ml", "heuristic"]   # NEW
    model_confidence: Literal["full", "transfer", "insufficient_data", "none"]  # NEW
```

---

## Feature Config Contract

### File Location

`services/ml/estategap_ml/config/features_{country_lower}.yaml`

### FeatureEngineer Lookup

```python
class FeatureEngineer:
    def __init__(self, country: str):
        config = CountryFeatureConfig.from_yaml(
            Path(f"config/features_{country.lower()}.yaml")
        )
        self.features = config.all_features
        self.encoding_rules = config.encoding_rules
```

If no YAML file exists for a country, the engineer falls back to `features_base.yaml` (base features only) and logs a warning.

---

## Normalisation Mapping Contract

Three new YAML mappings in `services/pipeline/config/mappings/`:

| File | Portal | Country |
|------|--------|---------|
| `us_zillow.yaml` | zillow | US |
| `us_redfin.yaml` | redfin | US |
| `us_realtor.yaml` | realtor_com | US |

All three must map:
- `area_sqft` → `built_area_sqft` (raw) + `built_area_m2` (computed)
- `price_usd_cents` → `asking_price` (USD cents) + `asking_price_eur` (EUR cents via exchange service)
- US-specific fields → corresponding `listings` columns (see data-model.md §1)
