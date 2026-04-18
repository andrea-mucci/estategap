# Data Model: Helm Chart External Infrastructure Refactor

This feature has no database schema changes. The "data model" here describes the Helm values schema and Kubernetes resource contracts.

## Helm Values Schema Changes

### New top-level keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `components.redis.deploy` | bool | `true` | Deploy Bitnami Redis sub-chart |
| `components.mlflow.deploy` | bool | `true` | Deploy MLflow StatefulSet |
| `components.kafka.deploy` | bool | `false` | Deploy Kafka (false = use external) |
| `components.postgresql.deploy` | bool | `false` | Deploy CloudNativePG (false = use external) |
| `components.prometheus.deploy` | bool | `false` | Deploy kube-prometheus-stack (false = use existing) |
| `components.grafana.deploy` | bool | `false` | Deploy Grafana (false = use existing) |

### `postgresql` restructured

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `postgresql.external.host` | string | `postgresql.databases.svc.cluster.local` | External PostgreSQL host |
| `postgresql.external.port` | int | `5432` | External PostgreSQL port |
| `postgresql.external.database` | string | `estategap` | Database name |
| `postgresql.external.sslmode` | string | `require` | SSL mode |
| `postgresql.external.credentialsSecret` | string | `estategap-db-credentials` | K8s Secret with PGUSER + PGPASSWORD |
| `postgresql.readReplica.enabled` | bool | `false` | Enable read replica routing |
| `postgresql.readReplica.host` | string | `postgresql-read.databases.svc.cluster.local` | Read replica host |
| `postgresql.readReplica.port` | int | `5432` | Read replica port |
| `postgresql.migrations.enabled` | bool | `true` | Run Alembic Job on install/upgrade |
| `postgresql.migrations.image` | string | `estategap/pipeline:latest` | Image containing Alembic |
| `postgresql.migrations.timeout` | int | `300` | Job activeDeadlineSeconds |

Removed keys: `postgresql.enabled`, `postgresql.imageName`, `postgresql.instances`, `postgresql.storage`, `postgresql.backup.*`, `postgresql.resources`, `postgresql.owner`

### `kafka` additions / changes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `kafka.sasl.credentialsSecret` | string | `""` | K8s Secret with KAFKA_SASL_USERNAME + KAFKA_SASL_PASSWORD |
| `kafka.topicInit.enabled` | bool | `true` | Run topic init Job |
| `kafka.topicInit.image` | string | `bitnami/kafka:3.7` | Image for init Job |
| `kafka.deadLetter.enabled` | bool | `true` | Create dead-letter topic |
| `kafka.deadLetter.retentionDays` | int | `30` | Retention for dead-letter topic |

Changed keys:
- `kafka.initJob.image` renamed to `kafka.topicInit.image`
- `kafka.initJob.replicationFactor` renamed to `kafka.topicInit.replicationFactor`
- `kafka.sasl.username` removed (moved into credentialsSecret)
- `kafka.sasl.secretName` renamed to `kafka.sasl.credentialsSecret`

### `s3` changes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `s3.credentialsSecret` | string | `estategap-s3-credentials` | K8s Secret with AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY |

Changed keys:
- `s3.credentials.secret` renamed to `s3.credentialsSecret`

### `prometheus` restructured

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `prometheus.serviceMonitor.enabled` | bool | `true` | Create ServiceMonitor resources |
| `prometheus.serviceMonitor.interval` | string | `15s` | Default scrape interval |
| `prometheus.serviceMonitor.labels` | map | `{release: prometheus}` | Labels matching Prometheus operator selector |
| `prometheus.rules.enabled` | bool | `true` | Create PrometheusRule resource |
| `prometheus.rules.labels` | map | `{release: prometheus}` | Labels matching Prometheus operator selector |

Removed keys: all existing `prometheus.*` sub-chart passthrough config (the sub-chart is removed)

### `grafana` restructured

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `grafana.dashboards.enabled` | bool | `true` | Create dashboard ConfigMaps |
| `grafana.dashboards.namespace` | string | `monitoring` | Namespace for dashboard ConfigMaps |
| `grafana.dashboards.labels` | map | `{grafana_dashboard: "1"}` | Labels for Grafana sidecar pickup |

Removed keys: all existing `grafana.*` sub-chart passthrough config

### Removed top-level sections

- `cnpg.*` — sub-chart removed
- `loki.*` — sub-chart removed
- `tempo.*` — sub-chart removed
- `prometheus.grafana.*` — sub-chart removed
- `prometheus.prometheus.prometheusSpec.*` — sub-chart removed
- `observability.*` — superseded by `prometheus.serviceMonitor.*` and `prometheus.rules.*`

## Kubernetes Resource Contracts

### New resources created

| Kind | Name | Namespace | Condition |
|------|------|-----------|-----------|
| `Job` | `estategap-db-migrate` | `estategap-system` | `postgresql.migrations.enabled: true` |
| `ServiceMonitor` | `estategap-{service-name}` | per service namespace | `prometheus.serviceMonitor.enabled: true` AND per-service `.serviceMonitor.enabled: true` |
| `PrometheusRule` | `estategap-rules` | `estategap-system` | `prometheus.rules.enabled: true` |
| `ConfigMap` | `estategap-dashboard-{name}` | `grafana.dashboards.namespace` | `grafana.dashboards.enabled: true` |

### Removed resources (no longer rendered)

| Kind | Name | Condition removed |
|------|------|-------------------|
| `Cluster` (CNPG) | `estategap-postgres` | Guarded by `components.postgresql.deploy` |
| `ScheduledBackup` (CNPG) | `estategap-postgres-daily` | Guarded by `components.postgresql.deploy` |
| kube-prometheus-stack resources | all | Sub-chart removed |
| Loki resources | all | Sub-chart removed |
| Tempo resources | all | Sub-chart removed |

### K8s Secret contracts

| Secret Name | Required Keys | Used By |
|-------------|--------------|---------|
| `estategap-db-credentials` | `PGUSER`, `PGPASSWORD` | Migration Job, application pods (via envFrom) |
| `estategap-s3-credentials` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | All ML/pipeline pods |
| `{kafka.sasl.credentialsSecret}` | `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD` | Kafka init Job, all pods (when SASL enabled) |
