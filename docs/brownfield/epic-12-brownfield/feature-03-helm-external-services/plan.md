# Feature: Helm Chart Refactoring for External Services

## /plan prompt

```
Implement the Helm chart refactoring with these technical decisions:

## values.yaml Structure (External Services)

```yaml
# ─── External Kafka ──────────────────────────────────────────
kafka:
  # Connection
  brokers: "kafka-bootstrap.kafka.svc.cluster.local:9092"
  topicPrefix: "estategap."
  
  # Authentication (optional)
  sasl:
    enabled: false
    mechanism: "PLAIN"
    credentialsSecret: ""      # K8s Secret with KAFKA_SASL_USERNAME, KAFKA_SASL_PASSWORD
  
  # TLS (optional)
  tls:
    enabled: false
    caSecret: ""               # K8s Secret with ca.crt
  
  # Topic init
  topicInit:
    enabled: true
    image: "bitnami/kafka:3.7"
  
  # Dead letter
  deadLetter:
    enabled: true
    retentionDays: 30

# ─── External PostgreSQL ─────────────────────────────────────
postgresql:
  external:
    host: "postgresql.databases.svc.cluster.local"
    port: 5432
    database: "estategap"
    sslmode: "require"
    credentialsSecret: "estategap-db-credentials"   # Must contain PGUSER, PGPASSWORD
  readReplica:
    enabled: false
    host: "postgresql-read.databases.svc.cluster.local"
    port: 5432
  migrations:
    enabled: true
    image: "estategap/pipeline:latest"              # Image containing Alembic
    timeout: 300

# ─── External S3 (Hetzner) ──────────────────────────────────
s3:
  endpoint: "https://fsn1.your-objectstorage.com"
  region: "fsn1"
  bucketPrefix: "estategap"
  forcePathStyle: true
  credentialsSecret: "estategap-s3-credentials"     # Must contain AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# ─── Observability (existing cluster) ────────────────────────
prometheus:
  serviceMonitor:
    enabled: true
    interval: "15s"
    labels:                      # Must match existing Prometheus operator selector
      release: "prometheus"
  rules:
    enabled: true
    labels:
      release: "prometheus"

grafana:
  dashboards:
    enabled: true
    namespace: "monitoring"      # Namespace where Grafana sidecar looks for ConfigMaps
    labels:
      grafana_dashboard: "1"

# ─── Components to deploy ────────────────────────────────────
components:
  redis:
    deploy: true
    # ... redis config (unchanged from v2)
  mlflow:
    deploy: true
    # ... mlflow config
  kafka:
    deploy: false               # false = use external
  postgresql:
    deploy: false               # false = use external
  prometheus:
    deploy: false               # false = use existing
  grafana:
    deploy: false               # false = use existing
```

## ConfigMap Template (External Service Env Vars)

```yaml
# templates/configmap-external.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: estategap-external-config
data:
  # PostgreSQL
  DATABASE_HOST: {{ .Values.postgresql.external.host | quote }}
  DATABASE_PORT: {{ .Values.postgresql.external.port | quote }}
  DATABASE_NAME: {{ .Values.postgresql.external.database | quote }}
  DATABASE_SSLMODE: {{ .Values.postgresql.external.sslmode | quote }}
  {{- if .Values.postgresql.readReplica.enabled }}
  DATABASE_READ_HOST: {{ .Values.postgresql.readReplica.host | quote }}
  DATABASE_READ_PORT: {{ .Values.postgresql.readReplica.port | quote }}
  {{- end }}
  
  # Kafka
  KAFKA_BROKERS: {{ .Values.kafka.brokers | quote }}
  KAFKA_TOPIC_PREFIX: {{ .Values.kafka.topicPrefix | quote }}
  KAFKA_SASL_ENABLED: {{ .Values.kafka.sasl.enabled | quote }}
  KAFKA_TLS_ENABLED: {{ .Values.kafka.tls.enabled | quote }}
  
  # S3
  S3_ENDPOINT: {{ .Values.s3.endpoint | quote }}
  S3_REGION: {{ .Values.s3.region | quote }}
  S3_BUCKET_PREFIX: {{ .Values.s3.bucketPrefix | quote }}
  S3_FORCE_PATH_STYLE: {{ .Values.s3.forcePathStyle | quote }}
```

## Conditional Rendering Pattern

Each infrastructure template uses `if`:

```yaml
# templates/redis.yaml
{{- if .Values.components.redis.deploy }}
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: estategap-redis
...
{{- end }}
```

## ServiceMonitor Template

```yaml
# templates/servicemonitor.yaml
{{- if .Values.prometheus.serviceMonitor.enabled }}
{{- range $name, $svc := .Values.services }}
{{- if $svc.metrics.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: estategap-{{ $name }}
  namespace: {{ $svc.namespace }}
  labels:
    {{- toYaml $.Values.prometheus.serviceMonitor.labels | nindent 4 }}
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ $name }}
      app.kubernetes.io/part-of: estategap
  endpoints:
    - port: metrics
      interval: {{ $.Values.prometheus.serviceMonitor.interval }}
      path: /metrics
{{- end }}
{{- end }}
{{- end }}
```

## Grafana Dashboard ConfigMaps

```yaml
# templates/grafana-dashboards.yaml
{{- if .Values.grafana.dashboards.enabled }}
{{- range $name := list "scraping-health" "pipeline-throughput" "ml-metrics" "alert-latency" "api-performance" "websocket-connections" "kafka-consumer-lag" }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: estategap-dashboard-{{ $name }}
  namespace: {{ $.Values.grafana.dashboards.namespace }}
  labels:
    {{- toYaml $.Values.grafana.dashboards.labels | nindent 4 }}
data:
  {{ $name }}.json: |-
    {{ $.Files.Get (printf "dashboards/%s.json" $name) | nindent 4 }}
---
{{- end }}
{{- end }}
```

## Migration Job

```yaml
# templates/migrations-job.yaml
{{- if .Values.postgresql.migrations.enabled }}
apiVersion: batch/v1
kind: Job
metadata:
  name: estategap-migrations-{{ .Release.Revision }}
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-10"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  activeDeadlineSeconds: {{ .Values.postgresql.migrations.timeout }}
  template:
    spec:
      containers:
        - name: migrations
          image: {{ .Values.postgresql.migrations.image }}
          command: ["alembic", "upgrade", "head"]
          envFrom:
            - configMapRef:
                name: estategap-external-config
            - secretRef:
                name: {{ .Values.postgresql.external.credentialsSecret }}
      restartPolicy: Never
  backoffLimit: 1
{{- end }}
```

## Files to Delete

```
helm/estategap/templates/nats.yaml
helm/estategap/templates/nats-streams-init.yaml
helm/estategap/templates/postgresql.yaml (CloudNativePG CR)
helm/estategap/templates/postgresql-backup.yaml
helm/estategap/templates/minio.yaml
Chart.yaml dependencies: nats, cloudnativepg, kube-prometheus-stack, grafana, loki-stack
```

## Files to Add

```
helm/estategap/templates/configmap-external.yaml
helm/estategap/templates/kafka-topics-init.yaml
helm/estategap/templates/migrations-job.yaml
helm/estategap/templates/servicemonitor.yaml
helm/estategap/templates/prometheusrule.yaml
helm/estategap/templates/grafana-dashboards.yaml
helm/estategap/dashboards/*.json (7 dashboard files)
```

## Testing on Kind

For kind-based tests, deploy minimal infrastructure:
- Strimzi Kafka operator + KafkaCluster CR (single-node)
- Bitnami PostgreSQL Helm chart (single instance + PostGIS)
- Prometheus operator (for ServiceMonitor CRD support)
- Grafana with sidecar (for dashboard import testing)

```makefile
kind-infra:
  helm install kafka strimzi/strimzi-kafka-operator -n kafka --create-namespace
  kubectl apply -f tests/kind/kafka-cluster.yaml
  helm install postgresql bitnami/postgresql -n databases --create-namespace \
    --set auth.postgresPassword=test --set image.tag=16
  kubectl exec -n databases postgresql-0 -- psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS postgis"
```
```
