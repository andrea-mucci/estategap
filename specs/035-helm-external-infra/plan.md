# Implementation Plan: Helm Chart External Infrastructure Refactor

**Branch**: `035-helm-external-infra` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/035-helm-external-infra/spec.md`

## Summary

Refactor `helm/estategap/` to stop self-deploying Kafka, PostgreSQL, Prometheus, Grafana, Loki, and Tempo. Instead, wire all EstateGap services to external shared cluster services via `values.yaml` config sections, Kubernetes Secret references, and a new `components.*` feature-flag system. Add ServiceMonitor CRDs, 7 Grafana dashboard ConfigMaps, an expanded PrometheusRule, and a pre-install/pre-upgrade Alembic migration Job.

## Technical Context

**Language/Version**: YAML (Helm 3.14+), Go templates (Helm templating)
**Primary Dependencies**: Helm 3.14+, Bitnami Redis 19.x (kept), KEDA 2.x (kept), Prometheus operator ≥ 0.63 (external, for ServiceMonitor CRD)
**Storage**: Redis 7 (self-deployed, Bitnami sub-chart unchanged); external PostgreSQL 16, Hetzner S3
**Testing**: `helm lint`, `helm unittest` plugin, `helm template` pipe assertions
**Target Platform**: Kubernetes 1.28+ (kind for CI, managed cluster for prod)
**Project Type**: Helm chart (infrastructure-as-code)
**Performance Goals**: `helm install` completes within 10 minutes on kind; migration Job within 5 minutes
**Constraints**: No secrets in values.yaml; all external creds via K8s Secret references; `helm lint` must pass on all four value profiles

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| II. Event-Driven Communication — Kafka is shared cluster service, MUST NOT deploy own | ✅ PASS | `components.kafka.deploy: false`; external brokers configured via `kafka.brokers` |
| III. Country-First Data Sovereignty — PostgreSQL is shared cluster service, MUST NOT deploy own | ✅ PASS | `components.postgresql.deploy: false`; external host via `postgresql.external.*` |
| III. Hetzner S3 — MUST NOT deploy MinIO | ✅ PASS | MinIO already removed in feature-034; `s3.*` points to Hetzner |
| VI. Secrets Management — No secrets in code, K8s Sealed Secrets for sensitive config | ✅ PASS | All credentials sourced from K8s Secrets referenced in values; never hardcoded |
| VII. Brownfield K8s — MUST NOT deploy Kafka, PostgreSQL, Prometheus, Grafana, Loki | ✅ PASS | All guarded by `components.*.deploy: false` flags; sub-chart deps removed |
| VII. Redis self-deployed | ✅ PASS | Bitnami Redis sub-chart unchanged |
| VII. MLflow self-deployed | ✅ PASS | Guarded by `components.mlflow.deploy: true` |
| VII. Every Helm value documented in HELM_VALUES.md | ⚠️ REQUIRED | Must update HELM_VALUES.md for all new values sections |

## Project Structure

### Documentation (this feature)

```text
specs/035-helm-external-infra/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code Changes

```text
helm/estategap/
├── Chart.yaml                            # MODIFY: remove cnpg, prometheus, loki, tempo deps
├── HELM_VALUES.md                        # MODIFY: document all new value sections
├── values.yaml                           # MODIFY: restructure + add components, external sections
├── values-staging.yaml                   # MODIFY: set components.*.deploy flags
├── values-production.yaml                # MODIFY: set components.*.deploy flags
├── values-test.yaml                      # MODIFY: set components.*.deploy flags
├── dashboards/                           # ADD: 7 JSON dashboard files
│   ├── scraping-health.json
│   ├── pipeline-throughput.json
│   ├── ml-metrics.json
│   ├── alert-latency.json
│   ├── api-performance.json
│   ├── websocket-connections.json
│   └── kafka-consumer-lag.json
├── templates/
│   ├── _helpers.tpl                      # MODIFY: update commonEnv DATABASE_HOST/PORT to external
│   ├── configmap.yaml                    # MODIFY: add external DB/Kafka/S3 env vars
│   ├── kafka-configmap.yaml              # MODIFY: add SASL env from credentialsSecret
│   ├── kafka-topics-init-job.yaml        # MODIFY: update SASL to credentialsSecret pattern
│   ├── postgresql-cluster.yaml           # MODIFY: guard with components.postgresql.deploy
│   ├── postgresql-backup.yaml            # MODIFY: guard with components.postgresql.deploy
│   ├── prometheus-rules.yaml             # MODIFY: guard + expand to 7 rule groups
│   ├── grafana-datasources.yaml          # MODIFY: update guard to prometheus.serviceMonitor.enabled
│   ├── db-migration-job.yaml             # ADD: pre-install/pre-upgrade Alembic Job
│   ├── servicemonitor.yaml               # ADD: ServiceMonitor loop over services
│   └── grafana-dashboards.yaml           # ADD: ConfigMap per dashboard with Files.Get
└── tests/
    ├── feature-flags_test.yaml           # MODIFY: add tests for new component flags
    ├── postgres_test.yaml                # MODIFY: add tests for external DB config
    └── kafka_test.yaml                   # MODIFY: add tests for SASL credentialsSecret
```

## Complexity Tracking

No constitution violations — all changes align with Principle VII brownfield rules.

---

## Phase 0: Research

### Research Findings

#### Decision 1: Sub-chart dependency removal strategy

**Decision**: Remove `cloudnative-pg`, `kube-prometheus-stack`, `loki-stack`, and `tempo` from `Chart.yaml` dependencies entirely (not just disable them). Keep `redis` and `keda`.

**Rationale**: Disabled sub-charts still get downloaded by `helm dependency update`, adding weight and confusion. Removing them entirely is cleaner and enforces the brownfield constraint at the chart level. `redis` is kept because it's still self-deployed. `keda` is kept because KEDA is used for pod autoscaling, not as a shared infra service.

**Alternatives considered**:
- Keep deps with `condition: false` — rejected: still downloaded, confusing for operators, violates "MUST NOT deploy" intent.
- Keep as optional with feature flag — rejected: adds template noise; these are never needed on the brownfield cluster.

#### Decision 2: `components.*` flag structure vs existing `postgresql.enabled`

**Decision**: Add a `components` section with `deploy` sub-keys (`components.postgresql.deploy`, etc.). Update existing guards in `postgresql-cluster.yaml` and `postgresql-backup.yaml` from `postgresql.enabled` to `components.postgresql.deploy`. The old `postgresql.enabled` key is repurposed to control the CNPG sub-chart condition (which is removed anyway).

**Rationale**: The user input specifies `components.*.deploy` pattern explicitly. This creates a single, scannable location in `values.yaml` for "what is self-deployed vs external".

**Alternatives considered**:
- Reuse existing `postgresql.enabled` — rejected: semantically confusing (enabled=true but using external?), and the user input defines a different structure.
- Separate `enabled` and `deploy` flags — rejected: unnecessary indirection.

#### Decision 3: External PostgreSQL env var injection pattern

**Decision**: Update `estategap.commonEnv` in `_helpers.tpl` to derive `DATABASE_HOST`, `DATABASE_PORT`, and `DATABASE_NAME` from `postgresql.external.*` values. Add `DATABASE_URL` and `DATABASE_READ_URL` as fully constructed connection strings injected via ConfigMap, with password from `envFrom` secretRef.

**Rationale**: The existing `commonEnv` helper hardcodes `estategap-postgres-rw.estategap-system.svc.cluster.local`. This must point to the external host. Using a ConfigMap for the non-secret parts and secretRef for the password follows the existing S3/Redis pattern in the chart.

**Pattern**:
```yaml
# configmap.yaml adds:
DATABASE_HOST: {{ .Values.postgresql.external.host | quote }}
DATABASE_PORT: {{ .Values.postgresql.external.port | quote }}
DATABASE_NAME: {{ .Values.postgresql.external.database | quote }}
DATABASE_SSLMODE: {{ .Values.postgresql.external.sslmode | quote }}

# _helpers.tpl commonEnv updated to reference ConfigMap keys
# DATABASE_URL constructed as: postgresql://$(PGUSER):$(PGPASSWORD)@$(DATABASE_HOST):$(DATABASE_PORT)/$(DATABASE_NAME)?sslmode=$(DATABASE_SSLMODE)
# using envFrom secretRef: {{ .Values.postgresql.external.credentialsSecret }}
```

#### Decision 4: SASL credentials pattern for Kafka

**Decision**: Replace `kafka.sasl.username` + `kafka.sasl.secretName` with `kafka.sasl.credentialsSecret` (a K8s Secret name containing `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD`). Update `kafka-configmap.yaml` to add `KAFKA_SASL_MECHANISM`. Update `_helpers.tpl kafkaEnv` and `kafka-topics-init-job.yaml` to read from the new secret.

**Rationale**: Per Constitution Principle VI, no credentials in values.yaml. The `credentialsSecret` pattern matches what's used for S3 and PostgreSQL.

#### Decision 5: ServiceMonitor template structure

**Decision**: Single `templates/servicemonitor.yaml` file with a `range` over `.Values.services` that emits a ServiceMonitor for each service where `.serviceMonitor.enabled == true` AND `prometheus.serviceMonitor.enabled == true` globally.

**Rationale**: The existing values already have `serviceMonitor.enabled`, `path`, and `interval` per service. Reusing this structure means no values.yaml changes for per-service config—only add the global `prometheus.serviceMonitor.labels` for operator selector.

#### Decision 6: Grafana dashboard JSON content

**Decision**: Use minimal but functional Grafana 9.x compatible dashboard JSON with one panel per dashboard (row + time series). The JSON will be valid enough for Grafana to import, with sensible PromQL queries. Placeholder panels are acceptable for initial delivery—the dashboards establish the import mechanism and can be iterated.

**Rationale**: Full production dashboards are a separate concern. The spec requires the import mechanism to work; dashboard content is secondary.

#### Decision 7: Migration Job image and command

**Decision**: Use `postgresql.migrations.image` (default `estategap/pipeline:latest`) which contains Alembic. Command: `alembic -c /app/alembic.ini upgrade head`. The Job mounts the same credentials secret as the application.

**Rationale**: The `pipeline` service already contains Alembic (per CLAUDE.md: Python 3.12 + Alembic 1.13+). Using the same image avoids a separate migration image.

---

## Phase 1: Design & Contracts

### data-model.md (inline — Helm values schema)

The canonical external service configuration shape in `values.yaml`:

```yaml
# ─── Feature flags ───────────────────────────────────────────
components:
  redis:
    deploy: true        # Bitnami sub-chart; still required
  mlflow:
    deploy: true        # Self-deployed MLflow
  kafka:
    deploy: false       # false = use external Kafka
  postgresql:
    deploy: false       # false = use external PostgreSQL
  prometheus:
    deploy: false       # false = use existing Prometheus
  grafana:
    deploy: false       # false = use existing Grafana

# ─── External Kafka ──────────────────────────────────────────
kafka:
  brokers: "kafka-bootstrap.kafka.svc.cluster.local:9092"
  topicPrefix: "estategap."
  sasl:
    enabled: false
    mechanism: "PLAIN"
    credentialsSecret: ""     # Secret with KAFKA_SASL_USERNAME + KAFKA_SASL_PASSWORD
  tls:
    enabled: false
    caSecret: ""              # Secret with ca.crt
  topicInit:
    enabled: true
    image: "bitnami/kafka:3.7"
    replicationFactor: 3      # Override per environment
  deadLetter:
    enabled: true
    retentionDays: 30
  consumer:
    maxRetries: 3

# ─── External PostgreSQL ─────────────────────────────────────
postgresql:
  external:
    host: "postgresql.databases.svc.cluster.local"
    port: 5432
    database: "estategap"
    sslmode: "require"
    credentialsSecret: "estategap-db-credentials"  # PGUSER + PGPASSWORD
  readReplica:
    enabled: false
    host: "postgresql-read.databases.svc.cluster.local"
    port: 5432
  migrations:
    enabled: true
    image: "estategap/pipeline:latest"
    timeout: 300

# ─── External S3 (Hetzner) ───────────────────────────────────
s3:
  endpoint: "https://fsn1.your-objectstorage.com"
  region: "fsn1"
  bucketPrefix: "estategap"
  forcePathStyle: true
  credentialsSecret: "estategap-s3-credentials"    # AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
  # Note: s3.credentials.secret is renamed to s3.credentialsSecret for consistency
  buckets:
    mlModels: ml-models
    trainingData: training-data
    listingPhotos: listing-photos
    exports: exports
    backups: backups

# ─── Prometheus / ServiceMonitor ─────────────────────────────
prometheus:
  serviceMonitor:
    enabled: true
    interval: "15s"
    labels:                  # Must match Prometheus operator serviceMonitorSelector
      release: "prometheus"
  rules:
    enabled: true
    labels:
      release: "prometheus"

# ─── Grafana dashboards ──────────────────────────────────────
grafana:
  dashboards:
    enabled: true
    namespace: "monitoring"
    labels:
      grafana_dashboard: "1"
```

### Key template contracts

#### `templates/servicemonitor.yaml`

```yaml
{{- if .Values.prometheus.serviceMonitor.enabled }}
{{- range $name, $svc := .Values.services }}
{{- if and $svc.enabled (and $svc.serviceMonitor $svc.serviceMonitor.enabled) }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: estategap-{{ $name }}
  namespace: {{ include "estategap.namespace" (dict "root" $ "name" $name) }}
  labels:
    {{- include "estategap.serviceLabels" (dict "root" $ "name" $name) | nindent 4 }}
    {{- toYaml $.Values.prometheus.serviceMonitor.labels | nindent 4 }}
spec:
  selector:
    matchLabels:
      {{- include "estategap.serviceSelectorLabels" (dict "root" $ "name" $name) | nindent 6 }}
  endpoints:
    - path: {{ $svc.serviceMonitor.path | default "/metrics" | quote }}
      port: http
      interval: {{ $svc.serviceMonitor.interval | default $.Values.prometheus.serviceMonitor.interval | quote }}
---
{{- end }}
{{- end }}
{{- end }}
```

#### `templates/db-migration-job.yaml`

```yaml
{{- if .Values.postgresql.migrations.enabled }}
apiVersion: batch/v1
kind: Job
metadata:
  name: estategap-db-migrate
  namespace: estategap-system
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": before-hook-creation
  labels:
    {{- include "estategap.labels" . | nindent 4 }}
    app.kubernetes.io/component: db-migration
spec:
  activeDeadlineSeconds: {{ .Values.postgresql.migrations.timeout }}
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: alembic-migrate
          image: {{ .Values.postgresql.migrations.image | quote }}
          command: ["alembic", "-c", "/app/alembic.ini", "upgrade", "head"]
          envFrom:
            - secretRef:
                name: {{ .Values.postgresql.external.credentialsSecret | quote }}
          env:
            - name: DATABASE_URL
              value: "postgresql://$(PGUSER):$(PGPASSWORD)@{{ .Values.postgresql.external.host }}:{{ .Values.postgresql.external.port }}/{{ .Values.postgresql.external.database }}?sslmode={{ .Values.postgresql.external.sslmode }}"
{{- end }}
```

#### `templates/grafana-dashboards.yaml`

```yaml
{{- if .Values.grafana.dashboards.enabled }}
{{- range $name := list "scraping-health" "pipeline-throughput" "ml-metrics" "alert-latency" "api-performance" "websocket-connections" "kafka-consumer-lag" }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: estategap-dashboard-{{ $name }}
  namespace: {{ $.Values.grafana.dashboards.namespace }}
  labels:
    {{- toYaml $.Values.grafana.dashboards.labels | nindent 4 }}
    {{- include "estategap.labels" $ | nindent 4 }}
data:
  {{ $name }}.json: |-
    {{ $.Files.Get (printf "dashboards/%s.json" $name) | nindent 4 }}
---
{{- end }}
{{- end }}
```

#### `templates/prometheus-rules.yaml` (expanded)

Guard changes from `{{- if .Values.prometheus.enabled }}` to `{{- if .Values.prometheus.rules.enabled }}`.

Alert groups added (on top of existing KafkaConsumerLagHigh):
1. `estategap.scraping` — ScraperSuccessRateLow (< 80% over 10m)
2. `estategap.pipeline` — PipelineLagHigh (lag > 5m for 5m)
3. `estategap.ml` — MLScorerErrorRateHigh (> 5% over 5m)
4. `estategap.api` — APILatencyP99High (> 2s for 5m)
5. `estategap.kafka` — KafkaConsumerLagHigh (> 10,000 for 2m)
6. `estategap.pods` — PodRestartCountHigh (> 3 in 15m)
7. `estategap.storage` — PVCDiskUsageHigh (> 80%)

PrometheusRule labels taken from `prometheus.rules.labels` to match operator selector.

### `_helpers.tpl` updates

Replace hardcoded `DATABASE_HOST` / `DATABASE_RO_HOST` in `estategap.commonEnv`:

```yaml
{{- define "estategap.commonEnv" -}}
- name: CLUSTER_ENVIRONMENT
  value: {{ .Values.cluster.environment | quote }}
- name: DATABASE_HOST
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_HOST
- name: DATABASE_PORT
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_PORT
- name: DATABASE_NAME
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_NAME
- name: DATABASE_SSLMODE
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_SSLMODE
{{- if .Values.postgresql.readReplica.enabled }}
- name: DATABASE_RO_HOST
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_RO_HOST
{{- end }}
{{ include "estategap.kafkaEnv" . }}
{{ include "estategap.s3Env" . }}
{{ include "estategap.s3CredentialEnv" . }}
...
{{- end -}}
```

Also update `estategap.s3CredentialEnv` to use `s3.credentialsSecret` instead of `s3.credentials.secret`.

Also update `estategap.kafkaEnv` to use `kafka.sasl.credentialsSecret` instead of `kafka.sasl.secretName`.

### `configmap.yaml` additions

Add to the ConfigMap data:

```yaml
DATABASE_HOST: {{ .Values.postgresql.external.host | quote }}
DATABASE_PORT: {{ .Values.postgresql.external.port | quote }}
DATABASE_NAME: {{ .Values.postgresql.external.database | quote }}
DATABASE_SSLMODE: {{ .Values.postgresql.external.sslmode | quote }}
{{- if .Values.postgresql.readReplica.enabled }}
DATABASE_RO_HOST: {{ .Values.postgresql.readReplica.host | quote }}
DATABASE_RO_PORT: {{ .Values.postgresql.readReplica.port | quote }}
{{- end }}
```

### GDPR CronJob update

`templates/gdpr-hard-delete-cronjob.yaml` references `estategap-postgres-rw.estategap-system.svc.cluster.local`. Update `gdpr.hardDeleteCron.database.host` default in `values.yaml` to `{{ .Values.postgresql.external.host }}` (documented, not templated inline since it's a values-driven field).

### values-staging.yaml key overrides

```yaml
components:
  kafka:
    deploy: false
  postgresql:
    deploy: false
  prometheus:
    deploy: false
  grafana:
    deploy: false
  redis:
    deploy: true
  mlflow:
    deploy: true

kafka:
  topicInit:
    replicationFactor: 1

postgresql:
  external:
    host: "postgresql.databases.svc.cluster.local"
    credentialsSecret: "estategap-db-credentials"
  migrations:
    enabled: true
```

### Chart.yaml after changes

Remove: `cloudnative-pg`, `kube-prometheus-stack` (alias: prometheus), `loki-stack` (alias: loki), `tempo`
Keep: `redis` (Bitnami), `keda`

```yaml
dependencies:
  - name: redis
    repository: https://charts.bitnami.com/bitnami
    version: ">=19.0.0 <20.0.0"
    condition: components.redis.deploy
  - name: keda
    repository: https://kedacore.github.io/charts
    version: ">=2.0.0 <3.0.0"
    condition: keda.enabled
```

Note: `redis.enabled` is the Bitnami sub-chart's own condition key; we set `condition: components.redis.deploy` to tie it to our feature flag. The Bitnami chart's internal `redis.enabled` also needs to be set (values passthrough).

### Helm test updates

**`tests/feature-flags_test.yaml`** — add:
- `components.postgresql.deploy: false` → `postgresql-cluster.yaml` has 0 documents
- `components.postgresql.deploy: false` → `postgresql-backup.yaml` has 0 documents
- `prometheus.rules.enabled: false` → `prometheus-rules.yaml` has 0 documents
- `grafana.dashboards.enabled: false` → `grafana-dashboards.yaml` has 0 documents
- `prometheus.serviceMonitor.enabled: false` → `servicemonitor.yaml` has 0 documents

**`tests/postgres_test.yaml`** — add:
- External host value flows into ConfigMap `DATABASE_HOST` key
- External port value flows into ConfigMap `DATABASE_PORT` key

**`tests/kafka_test.yaml`** — add:
- `kafka.sasl.credentialsSecret` reference appears in init Job env when SASL enabled

### quickstart.md

See inline below.

---

## Quickstart

### Prerequisites

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm dependency update helm/estategap
```

### Install with external infrastructure

```bash
# 1. Create credential secrets (platform team provides values)
kubectl create secret generic estategap-db-credentials \
  --from-literal=PGUSER=estategap \
  --from-literal=PGPASSWORD=<password> \
  -n estategap-system

kubectl create secret generic estategap-s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID=<key-id> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<secret-key> \
  -n estategap-system

# 2. Install
helm install estategap helm/estategap \
  --namespace estategap-system --create-namespace \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  --wait --timeout 10m
```

### Kind development setup

```bash
# 1. Start kind cluster
kind create cluster --config tests/kind/kind-config.yaml

# 2. Install minimal external infra
helm install strimzi-operator strimzi/strimzi-kafka-operator -n kafka --create-namespace
kubectl apply -f tests/kind/kafka-cluster.yaml

helm install postgresql bitnami/postgresql -n databases --create-namespace \
  --set auth.postgresPassword=test --set image.tag=16
kubectl exec -n databases postgresql-0 -- psql -U postgres \
  -c "CREATE EXTENSION IF NOT EXISTS postgis"

# Install Prometheus operator (for ServiceMonitor CRD)
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set grafana.sidecar.dashboards.enabled=true

# 3. Install EstateGap
helm install estategap helm/estategap \
  --namespace estategap-system --create-namespace \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml

# 4. Verify
helm test estategap -n estategap-system
```

### Verify external connection wiring

```bash
# Check DATABASE_HOST in any pod
kubectl exec -n estategap-pipeline \
  deploy/pipeline -c pipeline -- env | grep DATABASE_

# Check ServiceMonitors
kubectl get servicemonitor -A -l app.kubernetes.io/part-of=estategap

# Check dashboards imported
kubectl get configmap -n monitoring -l grafana_dashboard=1

# Check migration Job outcome
kubectl get job estategap-db-migrate -n estategap-system
kubectl logs job/estategap-db-migrate -n estategap-system
```

---

## Agent Context

Technologies added in this feature (Helm-specific):
- `monitoring.coreos.com/v1 ServiceMonitor` CRD
- `monitoring.coreos.com/v1 PrometheusRule` CRD
- Grafana dashboard sidecar ConfigMap pattern (label: `grafana_dashboard: "1"`)
- Helm hook annotations: `helm.sh/hook: pre-install,pre-upgrade`
- Helm `Files.Get` for bundling dashboard JSON
