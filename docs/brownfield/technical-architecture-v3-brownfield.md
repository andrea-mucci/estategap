# Technical Architecture v3 — EstateGap (Brownfield Adaptation)

**Project:** EstateGap — Multi-Country Real Estate Deal Tracker  
**Version:** 3.0 (brownfield adaptation of v2.0)  
**Date:** April 2026  
**Target:** Existing Kubernetes cluster with shared infrastructure  
**Companion docs:** `functional-requirements v2.0`, `addendum v2.1`, `addendum v2.2`, `technical-architecture v2.0`

---

## 1. Brownfield Context

This document describes adaptations to the v2.0 architecture required to deploy EstateGap on an **existing Kubernetes cluster** that already provides:

| Existing Service | Version | Namespace | Access |
|---|---|---|---|
| Apache Kafka | 3.7+ | `kafka` | `kafka-bootstrap.kafka.svc.cluster.local:9092` |
| PostgreSQL + PostGIS | 16 + 3.4 | `databases` | `postgresql.databases.svc.cluster.local:5432` |
| Prometheus | 2.53+ | `monitoring` | `prometheus.monitoring.svc.cluster.local:9090` |
| Grafana | 11+ | `monitoring` | `grafana.monitoring.svc.cluster.local:3000` |

Additionally, MinIO is replaced by **Hetzner Object Storage** (S3-compatible endpoint).

**All business logic, API contracts, database schema, and user-facing functionality remain IDENTICAL to v2.0.**

---

## 2. Infrastructure Changes Summary

```
REMOVED from Helm chart:              ADDED / CHANGED:
─────────────────────────              ─────────────────
✗ NATS JetStream StatefulSet          ✓ Kafka client libraries (Go: confluent-kafka-go / segmentio/kafka-go, Python: aiokafka)
✗ CloudNativePG Operator + CR         ✓ External PostgreSQL connection config (host, port, dbname, credentials via Secret)
✗ MinIO StatefulSet                   ✓ Hetzner S3 config (endpoint, region, access_key, secret_key via Secret)
✗ kube-prometheus-stack Helm dep      ✓ Prometheus ServiceMonitor CRs (for existing Prometheus to scrape)
✗ Grafana Helm dep                    ✓ Grafana Dashboard ConfigMaps (auto-imported by existing Grafana)
✗ Loki + Promtail                     ✓ (use cluster's existing logging solution)
                                      ✓ Redis still self-deployed (not in existing cluster)
                                      ✓ MLflow still self-deployed
```

---

## 3. Message Broker: NATS JetStream → Apache Kafka

### 3.1 Topic Mapping

Every NATS stream maps 1:1 to a Kafka topic:

| NATS Stream (v2) | Kafka Topic (v3) | Partitions | Retention |
|---|---|---|---|
| `raw-listings` | `estategap.raw-listings` | 10 (by country hash) | 7 days |
| `normalized-listings` | `estategap.normalized-listings` | 10 | 7 days |
| `enriched-listings` | `estategap.enriched-listings` | 10 | 7 days |
| `scored-listings` | `estategap.scored-listings` | 10 | 7 days |
| `alerts-triggers` | `estategap.alerts-triggers` | 5 | 3 days |
| `alerts-notifications` | `estategap.alerts-notifications` | 5 | 3 days |
| `scraper-commands` | `estategap.scraper-commands` | 5 | 1 day |
| `price-changes` | `estategap.price-changes` | 5 | 7 days |

**Prefix:** All topics use `estategap.` prefix to avoid collisions with other cluster tenants.

### 3.2 Consumer Groups

| Service | Consumer Group | Topics Consumed |
|---|---|---|
| pipeline-normalizer | `estategap-normalizer` | `estategap.raw-listings` |
| pipeline-deduplicator | `estategap-deduplicator` | `estategap.normalized-listings` |
| pipeline-enricher | `estategap-enricher` | `estategap.normalized-listings` |
| ml-scorer | `estategap-scorer` | `estategap.enriched-listings` |
| alert-engine | `estategap-alert-engine` | `estategap.scored-listings`, `estategap.price-changes` |
| alert-dispatcher | `estategap-dispatcher` | `estategap.alerts-notifications` |
| ws-server | `estategap-ws-notifications` | `estategap.alerts-notifications` |

### 3.3 Library Choices

| Language | Library | Rationale |
|---|---|---|
| Go | `github.com/segmentio/kafka-go` | Pure Go, no CGO dependency, simpler than confluent-kafka-go |
| Python | `aiokafka` | Async-native, works with asyncio event loop already used in pipeline services |

### 3.4 Migration Pattern

Each service has an internal `broker` interface:

```go
// Go services
type EventBroker interface {
    Publish(ctx context.Context, topic string, key string, payload []byte) error
    Subscribe(ctx context.Context, topic string, group string, handler MessageHandler) error
}
```

```python
# Python services
class EventBroker(Protocol):
    async def publish(self, topic: str, key: str, payload: bytes) -> None: ...
    async def subscribe(self, topic: str, group: str, handler: MessageHandler) -> None: ...
```

The Kafka implementation replaces the NATS implementation behind this interface. No business logic changes.

---

## 4. Object Storage: MinIO → Hetzner S3

### 4.1 Configuration

```yaml
# values.yaml
s3:
  endpoint: "https://fsn1.your-objectstorage.com"   # Hetzner S3 endpoint
  region: "fsn1"                                       # Hetzner region
  bucket_prefix: "estategap"                           # Prefix for all buckets
  credentials_secret: "estategap-s3-credentials"       # K8s Secret name
  # Secret must contain keys: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

### 4.2 Bucket Mapping

| MinIO Bucket (v2) | S3 Bucket (v3) | Usage |
|---|---|---|
| `ml-models` | `estategap-ml-models` | ONNX model artifacts |
| `training-data` | `estategap-training-data` | ML training datasets |
| `listing-photos` | `estategap-listing-photos` | Cached listing images |
| `exports` | `estategap-exports` | User data exports (GDPR) |
| `backups` | `estategap-backups` | DB backups (pg_dump) |

### 4.3 Library Changes

Both Go and Python already use S3-compatible SDKs:

| Language | Library | Change Required |
|---|---|---|
| Go | `github.com/aws/aws-sdk-go-v2` | Change endpoint URL + region in config |
| Python | `boto3` / `aiobotocore` | Change endpoint_url + region in config |

The MinIO client libraries (`minio-go`, `minio` Python) are replaced with standard AWS SDK clients, which work with any S3-compatible endpoint including Hetzner.

---

## 5. Database: Self-Managed → External PostgreSQL

### 5.1 Configuration

```yaml
# values.yaml
postgresql:
  deploy: false                                  # Do NOT deploy — use external
  external:
    host: "postgresql.databases.svc.cluster.local"
    port: 5432
    database: "estategap"
    credentials_secret: "estategap-db-credentials"  # K8s Secret with: PGUSER, PGPASSWORD
    sslmode: "require"
    read_replica:
      enabled: true
      host: "postgresql-read.databases.svc.cluster.local"
      port: 5432
```

### 5.2 Schema Management

- Alembic migrations run as a **Kubernetes Job** (`helm/estategap/templates/migrations-job.yaml`) on every deploy
- The Job runs before service Deployments via Helm hook (`helm.sh/hook: pre-install,pre-upgrade`)
- PostGIS extension must be pre-enabled by the platform team (or the migration Job runs `CREATE EXTENSION IF NOT EXISTS postgis`)
- Connection pooling: application-level via pgx pool (Go) and asyncpg pool (Python) — no PgBouncer needed if the external PG supports enough connections

### 5.3 Backup Strategy Change

- v2: CronJob running `pg_dump` to MinIO
- v3: Assume platform team manages PostgreSQL backups. EstateGap only manages **application-level exports** to S3 (GDPR data export, ML training snapshots)

---

## 6. Observability: Self-Managed → Existing Cluster Stack

### 6.1 Prometheus Integration

- Each EstateGap service exposes `/metrics` (Prometheus format) — UNCHANGED
- **ServiceMonitor** CRDs deployed by Helm chart to tell existing Prometheus to scrape EstateGap pods:

```yaml
# helm/estategap/templates/servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: estategap-{{ .service }}
  namespace: estategap-gateway  # or whichever namespace
  labels:
    release: prometheus          # Must match existing Prometheus selector
spec:
  selector:
    matchLabels:
      app.kubernetes.io/part-of: estategap
  endpoints:
    - port: metrics
      interval: 15s
      path: /metrics
```

### 6.2 Grafana Dashboard Integration

- Dashboard JSON files stored in `helm/estategap/dashboards/`
- Deployed as ConfigMaps with the label `grafana_dashboard: "1"` (standard Grafana sidecar convention):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: estategap-dashboard-{{ .name }}
  labels:
    grafana_dashboard: "1"
data:
  {{ .name }}.json: |
    {{ .Files.Get (printf "dashboards/%s.json" .name) | nindent 4 }}
```

- Dashboards: scraping health, pipeline throughput, ML model metrics, alert latency, API performance, WebSocket connections

### 6.3 Logging

- Services output structured JSON to stdout — UNCHANGED
- Cluster's existing logging solution (Loki, EFK, or whatever is deployed) collects via DaemonSet
- No Loki/Promtail deployment in EstateGap Helm chart

### 6.4 Alerting

- PrometheusRule CRDs for alerting rules:
  - `scraper_success_rate < 0.8` — scraping degraded
  - `pipeline_lag_seconds > 300` — pipeline falling behind
  - `ml_scorer_error_rate > 0.05` — model inference errors
  - `api_p99_latency > 2` — API slow
  - `kafka_consumer_lag > 10000` — consumer falling behind

---

## 7. Helm Chart Restructure

### 7.1 Removed Templates

```
DELETED:
  templates/nats.yaml                  # Was: NATS StatefulSet + Service
  templates/nats-streams-init.yaml     # Was: Init container creating streams
  templates/postgresql.yaml            # Was: CloudNativePG Cluster CR
  templates/postgresql-backup.yaml     # Was: Backup CronJob to MinIO
  templates/minio.yaml                 # Was: MinIO StatefulSet + Service + Buckets
  templates/prometheus-stack.yaml      # Was: kube-prometheus-stack sub-chart reference
  templates/grafana.yaml               # Was: Grafana sub-chart reference
  templates/loki.yaml                  # Was: Loki + Promtail sub-chart reference
```

### 7.2 New Templates

```
ADDED:
  templates/kafka-topics-init.yaml     # Job: creates Kafka topics with estategap.* prefix
  templates/migrations-job.yaml        # Job: runs Alembic migrations (pre-install hook)
  templates/servicemonitor.yaml        # ServiceMonitor CRDs for existing Prometheus
  templates/prometheusrule.yaml        # PrometheusRule CRDs for alerting
  templates/grafana-dashboards.yaml    # ConfigMaps with Grafana dashboard JSONs
  templates/external-secrets.yaml      # ExternalSecret or SealedSecret references
  dashboards/*.json                    # Grafana dashboard JSON files
```

### 7.3 Conditional Components

```yaml
# values.yaml — feature flags
components:
  redis:
    deploy: true             # Still needed — not in cluster
  mlflow:
    deploy: true             # Still needed — not in cluster
  kafka:
    deploy: false            # Use existing cluster Kafka
  postgresql:
    deploy: false            # Use existing cluster PostgreSQL
  prometheus:
    deploy: false            # Use existing cluster Prometheus
  grafana:
    deploy: false            # Use existing cluster Grafana
```

---

## 8. Helm Values Documentation

Every value in `values.yaml` MUST be documented with:
- **Description** — what it controls
- **Type** — string, int, bool, object, list
- **Default** — production-safe default
- **Required** — whether the deploy fails without it
- **Example** — real-world example value
- **Secret reference** — if the value should come from a K8s Secret instead

Additionally, a standalone `HELM_VALUES.md` file at chart root provides:
- Grouped variable reference (infrastructure, services, features, security)
- Quick-start configuration for common scenarios
- Migration checklist from v2 → v3
- Troubleshooting common misconfigurations

---

## 9. What Remains Unchanged from v2.0

Everything not mentioned above stays identical:
- All Go and Python service business logic
- API Gateway (chi router, JWT auth, rate limiting, Stripe)
- WebSocket server (gorilla/websocket, chat protocol)
- AI chat service (LLM provider abstraction, criteria parsing)
- ML pipeline (LightGBM, ONNX, SHAP, MLflow)
- Spider framework (Scrapy, Playwright, proxy manager)
- Frontend (Next.js 15, all pages and components)
- Database schema (same tables, partitioning, indexes)
- Protobuf contracts (same .proto files)
- Testing strategy (kind, E2E, user journeys — adapted for Kafka)
- CI/CD pipelines (same GitHub Actions, ArgoCD)
