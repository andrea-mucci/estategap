# Contract: NATS Events — ML Scorer

**Date**: 2026-04-17
**Feature**: 015-ml-inference-scoring

---

## Consumed Subjects

### `enriched.listings`

**Producer**: enrichment pipeline (feature 013-enrichment-change-detection)
**Consumer**: scorer service — `nats_consumer.py`

The scorer subscribes as a durable JetStream consumer (`scorer-group`). Messages are processed in micro-batches of 50 (or flushed every 5 seconds). Each message payload is the JSON-serialised `EnrichedListing` model from `estategap_common`.

**Consumer config**:
```python
await js.subscribe(
    "enriched.listings",
    durable="scorer-group",
    config=nats.js.api.ConsumerConfig(
        ack_policy=nats.js.api.AckPolicy.EXPLICIT,
        max_ack_pending=200,
        deliver_policy=nats.js.api.DeliverPolicy.NEW,
    ),
)
```

**ACK/NAK semantics**:
- ACK after successful DB write + `scored.listings` publish.
- NAK with 30-second delay after transient DB/NATS failure (up to 3 retries).
- Term (permanent failure) for listings with no active model for their country.

---

## Published Subjects

### `scored.listings`

**Producer**: scorer service — `nats_consumer.py`
**Consumers**: alert-engine, websocket-server, analytics pipeline

Published once per successfully scored listing, immediately after the DB `UPDATE listings` commit.

**Pydantic model**: `ScoredListingEvent` in `estategap_common/models/scoring.py`

```python
class ScoredListingEvent(EstateGapModel):
    listing_id:           UUID
    country_code:         str
    estimated_price_eur:  Decimal
    deal_score:           Decimal
    deal_tier:            DealTier
    confidence_low_eur:   Decimal
    confidence_high_eur:  Decimal
    model_version:        str
    scored_at:            AwareDatetime
    shap_features:        list[ShapFeatureEvent]

class ShapFeatureEvent(EstateGapModel):
    feature:    str
    value:      float
    shap_value: float
    label:      str
```

**Example payload**:
```json
{
  "listing_id":           "550e8400-e29b-41d4-a716-446655440000",
  "country_code":         "es",
  "estimated_price_eur":  245000.00,
  "deal_score":           18.50,
  "deal_tier":            1,
  "confidence_low_eur":   210000.00,
  "confidence_high_eur":  280000.00,
  "model_version":        "es_national_v12",
  "scored_at":            "2026-04-17T14:32:10Z",
  "shap_features": [
    {
      "feature":    "zone_median_price_m2",
      "value":      4800.0,
      "shap_value": 15000.0,
      "label":      "Zone median price of 4,800€/m² pushes estimate up"
    },
    {
      "feature":    "built_area_m2",
      "value":      85.0,
      "shap_value": -8200.0,
      "label":      "85m² built area pulls estimate down"
    },
    {
      "feature":    "dist_metro_m",
      "value":      320.0,
      "shap_value": 6100.0,
      "label":      "320m to nearest metro pushes estimate up"
    },
    {
      "feature":    "floor_number",
      "value":      4.0,
      "shap_value": 3200.0,
      "label":      "Floor 4 pushes estimate up"
    },
    {
      "feature":    "building_age_years",
      "value":      12.0,
      "shap_value": -2100.0,
      "label":      "Building age of 12 years pulls estimate down"
    }
  ]
}
```

---

## Subscribed for Notifications (non-consuming)

### `ml.training.completed`

**Producer**: ml-trainer (feature 014)
**Consumer**: scorer — `model_registry.py`

The scorer subscribes to this subject to trigger an **immediate** hot-reload when a new model is promoted, in addition to the 60-second polling loop. This reduces the latency between model promotion and model activation from up to 60 seconds to a few seconds.

```python
# Non-durable subscription (fire-and-forget notification)
await nc.subscribe("ml.training.completed", cb=on_model_promoted)
```

The callback calls `model_registry.trigger_reload(country_code)`, which initiates the download-and-swap sequence described in research Decision 4.
