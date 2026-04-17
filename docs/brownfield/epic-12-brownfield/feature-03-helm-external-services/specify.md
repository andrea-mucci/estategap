# Feature: Helm Chart Refactoring for External Services

## /specify prompt

```
Refactor the Helm chart to stop deploying infrastructure services (Kafka, PostgreSQL, Prometheus, Grafana) and instead configure connections to existing cluster services. Add ServiceMonitor CRDs, Grafana dashboard ConfigMaps, PrometheusRule alerting, and a migration Job for database schema.

## What

1. **Remove self-deployed infrastructure** from Helm chart:
   - Delete NATS StatefulSet + Service templates
   - Delete CloudNativePG Cluster CR + backup CronJob templates
   - Delete MinIO StatefulSet + Service templates
   - Delete kube-prometheus-stack sub-chart dependency
   - Delete Grafana sub-chart dependency
   - Delete Loki + Promtail sub-chart dependency

2. **External PostgreSQL configuration:**
   - `values.yaml` section with: host, port, database, sslmode, credentials Secret reference
   - Optional read replica configuration
   - ConfigMap generates env vars: DATABASE_URL, DATABASE_READ_URL
   - Credentials injected from referenced K8s Secret (not in values.yaml)

3. **External Kafka configuration:**
   - `values.yaml` section with: brokers, SASL config, TLS config, topic prefix
   - ConfigMap generates env vars: KAFKA_BROKERS, KAFKA_TOPIC_PREFIX, KAFKA_SASL_*
   - Topic init Job creates topics on install/upgrade (idempotent)

4. **External S3 configuration:**
   - `values.yaml` section with: endpoint, region, bucket prefix, credentials Secret
   - ConfigMap generates env vars: S3_ENDPOINT, S3_REGION, S3_BUCKET_PREFIX
   - Credentials injected from referenced K8s Secret

5. **Prometheus integration:**
   - ServiceMonitor CRDs for each EstateGap service (one template with loop)
   - Label selector matching existing Prometheus operator (configurable via values)
   - Scrape interval, path, port configurable per service

6. **Grafana dashboard integration:**
   - Dashboard JSON files in `helm/estategap/dashboards/`
   - ConfigMap per dashboard with `grafana_dashboard: "1"` label
   - Dashboards: scraping-health, pipeline-throughput, ml-metrics, alert-latency, api-performance, websocket-connections, kafka-consumer-lag
   - Grafana namespace configurable (for cross-namespace sidecar pickup)

7. **PrometheusRule alerting:**
   - `helm/estategap/templates/prometheusrule.yaml` with rules for:
     - Scraper success rate < 80%
     - Pipeline processing lag > 5 minutes
     - ML scorer error rate > 5%
     - API p99 latency > 2 seconds
     - Kafka consumer lag > 10,000 messages
     - Pod restart count > 3 in 15 minutes
     - Disk usage > 80% on PVCs

8. **Database migration Job:**
   - Helm hook (pre-install, pre-upgrade) that runs Alembic migrations
   - Uses same PostgreSQL credentials as application
   - Timeout 5 minutes
   - On failure: Job stays for debugging, Helm upgrade halts

9. **Feature flags** in values.yaml:
   - `components.redis.deploy: true` — still needed (not in cluster)
   - `components.mlflow.deploy: true` — still needed
   - `components.kafka.deploy: false` — use external
   - `components.postgresql.deploy: false` — use external
   - `components.prometheus.deploy: false` — use external
   - `components.grafana.deploy: false` — use external
   - Each flag controls whether the corresponding template is rendered

10. **Redis** — UNCHANGED: still deployed by Helm chart (Bitnami Redis sub-chart or StatefulSet template).

## Acceptance Criteria

- `helm lint` passes on all values profiles
- `helm template` with `components.kafka.deploy=false` does NOT render any Kafka StatefulSet
- `helm template` with `components.postgresql.deploy=false` does NOT render any PostgreSQL resources
- Installation on kind (with Strimzi Kafka + Bitnami PostgreSQL pre-installed) succeeds
- All pods connect to external PostgreSQL successfully
- All services publish/consume via external Kafka
- ServiceMonitors visible in existing Prometheus targets
- Dashboards auto-imported into existing Grafana
- PrometheusRule alerts visible in Prometheus rules page
- Migration Job runs Alembic on install and upgrade
- Feature flags correctly toggle all conditional resources
```
