# Research: Helm Chart External Infrastructure Refactor

## D-01: Sub-chart Dependency Removal

**Decision**: Remove `cloudnative-pg`, `kube-prometheus-stack`, `loki-stack`, and `tempo` from `Chart.yaml` dependencies entirely.

**Rationale**: Constitution Principle VII explicitly lists these as "MUST NOT DEPLOY". Disabled sub-charts still get downloaded by `helm dependency update`. Complete removal enforces the brownfield constraint at the chart level and eliminates accidental re-enablement.

**Alternatives considered**:
- Keep with `condition: false` — rejected: still downloaded, misleads operators, violates "MUST NOT deploy" letter.

---

## D-02: `components.*` Feature Flag Structure

**Decision**: New top-level `components` key with `deploy` sub-key per component.

**Rationale**: Single scannable location in `values.yaml` for the "self-deployed vs external" decision. User input specifies this exact structure. Consistent with how Bitnami charts use `enabled` sub-keys.

**Alternatives considered**:
- Reuse existing `postgresql.enabled` — rejected: semantically ambiguous (does enabled=false mean "disabled" or "using external"?).
- Inline `deploy` flag per section (e.g. `postgresql.deploy`) — viable, but separating into `components.*` is cleaner and matches the user's spec.

---

## D-03: External PostgreSQL Env Var Injection

**Decision**: Update `estategap.commonEnv` in `_helpers.tpl` to derive `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, and `DATABASE_SSLMODE` from `postgresql.external.*` via ConfigMap. Password injected via `envFrom.secretRef` from `postgresql.external.credentialsSecret`.

**Rationale**: Existing `commonEnv` hardcodes the CloudNativePG service DNS. This must point to the external host. ConfigMap for non-secret parts + secretRef for credentials follows the existing S3 pattern in the chart.

**Alternatives considered**:
- Direct `value:` inline in commonEnv — rejected: DB host changes don't require template re-render; ConfigMap is more operator-friendly.
- Full `DATABASE_URL` as one env var — viable, but harder to override individual components and breaks existing `DATABASE_HOST` references.

---

## D-04: Kafka SASL Credentials Pattern

**Decision**: Replace `kafka.sasl.username` + `kafka.sasl.secretName` with `kafka.sasl.credentialsSecret` (K8s Secret containing `KAFKA_SASL_USERNAME` + `KAFKA_SASL_PASSWORD`).

**Rationale**: Constitution Principle VI: no credentials in values.yaml. `credentialsSecret` pattern is consistent with `postgresql.external.credentialsSecret` and `s3.credentialsSecret`. Removes the username leak from values.yaml.

**Alternatives considered**:
- Keep username in values, password in secret — rejected: Constitution principle VI prohibits credentials in values.yaml; username alone can be considered sensitive for SASL.

---

## D-05: ServiceMonitor Template Structure

**Decision**: Single `templates/servicemonitor.yaml` with `range` over `.Values.services`, emitting one ServiceMonitor per service where `.serviceMonitor.enabled` is true.

**Rationale**: Existing per-service values already have `serviceMonitor.enabled`, `path`, and `interval`. No new per-service values needed—only global `prometheus.serviceMonitor.labels` added. Consistent with existing HPA and KEDA ScaledObject pattern of one template file per cross-cutting concern.

**Alternatives considered**:
- One ServiceMonitor per service template file — rejected: 10+ template files for one concern, harder to maintain.
- PodMonitor instead of ServiceMonitor — rejected: the existing chart already uses ServiceMonitor pattern and all services have Kubernetes Services.

---

## D-06: Grafana Dashboard JSON Content

**Decision**: Minimal but valid Grafana 9.x dashboard JSON with functional PromQL panels per dashboard. Content is illustrative—the import mechanism is the deliverable.

**Rationale**: Full production dashboards are out of scope for this infrastructure refactor. The spec requires the ConfigMap import pattern to work.

**Dashboard PromQL queries**:
- `scraping-health`: `rate(estategap_scraper_requests_total{status="success"}[5m]) / rate(estategap_scraper_requests_total[5m])`
- `pipeline-throughput`: `rate(estategap_pipeline_messages_processed_total[5m])`
- `ml-metrics`: `rate(estategap_ml_scorer_predictions_total[5m])`, `rate(estategap_ml_scorer_errors_total[5m])`
- `alert-latency`: `histogram_quantile(0.99, rate(estategap_alert_processing_duration_seconds_bucket[5m]))`
- `api-performance`: `histogram_quantile(0.99, rate(estategap_http_request_duration_seconds_bucket[5m]))`
- `websocket-connections`: `estategap_websocket_active_connections`
- `kafka-consumer-lag`: `estategap_kafka_consumer_lag`

---

## D-07: Migration Job Image and Command

**Decision**: Use `postgresql.migrations.image` (default: pipeline service image) which already contains Alembic. Command: `["alembic", "-c", "/app/alembic.ini", "upgrade", "head"]`. Timeout: 300s. `backoffLimit: 0` + `restartPolicy: Never` so failure is immediate and pod is retained.

**Rationale**: The `pipeline` service already uses Alembic 1.13+ per CLAUDE.md. No separate image needed. `backoffLimit: 0` + `helm.sh/hook-delete-policy: before-hook-creation` (not `hook-succeeded`) means the pod stays on failure for debugging, and the next run cleans up before creating a new one.

**Note**: `helm.sh/hook-delete-policy` must be `before-hook-creation` (not `hook-succeeded` or `hook-failed`) to allow debugging while still cleaning up before next deploy.

---

## D-08: `s3.credentials.secret` → `s3.credentialsSecret` rename

**Decision**: Rename `s3.credentials.secret` to `s3.credentialsSecret` for consistency with `postgresql.external.credentialsSecret` and `kafka.sasl.credentialsSecret`.

**Impact**: Update `_helpers.tpl estategap.s3CredentialEnv`, `postgresql-cluster.yaml` (references old key), and `sealed-secrets.yaml`. Update `values.yaml` and all value override files.

---

## D-09: `gdpr-hard-delete-cronjob.yaml` database host

**Decision**: Update `values.yaml` default for `gdpr.hardDeleteCron.database.host` from the hardcoded CNPG service DNS to `postgresql.databases.svc.cluster.local` (matching `postgresql.external.host` default). The template uses `.Values.gdpr.hardDeleteCron.database.host` — no template change needed, only values update.

**Rationale**: The GDPR job must also reach the external PostgreSQL. Updating the values default is sufficient; each environment overrides this in their values file.
