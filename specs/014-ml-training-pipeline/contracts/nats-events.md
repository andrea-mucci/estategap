# NATS Event Contracts: ML Training Pipeline

**Date**: 2026-04-17
**Feature**: 014-ml-training-pipeline
**Transport**: NATS JetStream — stream `ML_EVENTS`

---

## Stream Configuration

```
Stream name:    ML_EVENTS
Subjects:       ml.training.>
Retention:      WorkQueuePolicy (delete on ack) for .failed; LimitsPolicy for .completed
Max age:        30 days
Replicas:       3 (production), 1 (staging)
```

---

## Event: `ml.training.completed`

Published by the trainer after a successful training run (regardless of whether the challenger was promoted).

**Subject**: `ml.training.completed`

**Payload** (JSON):

```json
{
  "country_code":           "es",
  "model_version_tag":      "es_national_v12",
  "mape_national":          0.094,
  "promoted":               true,
  "previous_champion_tag":  "es_national_v11",
  "artifact_path":          "models/es_national_v12.onnx",
  "timestamp":              "2026-04-20T03:47:12Z"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `country_code` | string (CHAR 2) | yes | ISO 3166-1 alpha-2 |
| `model_version_tag` | string | yes | Unique tag, format `{cc}_{scope}_v{n}` |
| `mape_national` | float | yes | Test-set MAPE (national) |
| `promoted` | bool | yes | Whether challenger beat champion |
| `previous_champion_tag` | string or null | no | Previous active model tag; null on first run |
| `artifact_path` | string | yes | MinIO path to ONNX file |
| `timestamp` | RFC 3339 UTC | yes | Publish time |

**Consumers**:
- `ml-scorer`: subscribes to reload the active model into memory.

---

## Event: `ml.training.failed`

Published by the trainer when the job encounters an unrecoverable error. The previous champion remains active.

**Subject**: `ml.training.failed`

**Payload** (JSON):

```json
{
  "country_code":  "es",
  "error":         "asyncpg.PostgresError: connection timeout after 30s",
  "stage":         "data_export",
  "timestamp":     "2026-04-20T03:05:01Z"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `country_code` | string or null | no | Country being processed when failure occurred |
| `error` | string | yes | Error message (no stack trace — logs have details) |
| `stage` | string | yes | Pipeline stage: `data_export`, `feature_engineering`, `training`, `evaluation`, `onnx_export`, `promotion`, `mlflow_logging` |
| `timestamp` | RFC 3339 UTC | yes | Publish time |

**Consumers**:
- `alert-dispatcher`: subscribes to forward operator alert (Slack/email/PagerDuty).

---

## Versioning Policy

These event schemas follow semantic versioning embedded in the subject:
- Current version: `v1` (implicit, no version suffix yet)
- Breaking schema changes will use `ml.training.v2.completed` etc.
- Additive fields are non-breaking; existing consumers MUST ignore unknown fields.
