# Helm Values

## Components

| Field | Type | Default | Description |
|---|---|---|---|
| `components.redis.deploy` | `bool` | `true` | Deploy the bundled Bitnami Redis sub-chart. |
| `components.mlflow.deploy` | `bool` | `true` | Reserved toggle for self-managed MLflow resources. |
| `components.kafka.deploy` | `bool` | `false` | Do not deploy Kafka from this chart; connect to a shared cluster instead. |
| `components.postgresql.deploy` | `bool` | `false` | Do not deploy CloudNativePG from this chart; connect to a shared cluster instead. |
| `components.prometheus.deploy` | `bool` | `false` | Do not deploy Prometheus from this chart. |
| `components.grafana.deploy` | `bool` | `false` | Do not deploy Grafana from this chart. |

## PostgreSQL

| Field | Type | Default | Description |
|---|---|---|---|
| `postgresql.external.host` | `string` | `postgresql.databases.svc.cluster.local` | Shared PostgreSQL writer endpoint. |
| `postgresql.external.port` | `int` | `5432` | Shared PostgreSQL port. |
| `postgresql.external.database` | `string` | `estategap` | Application database name. |
| `postgresql.external.sslmode` | `string` | `require` | SSL mode used by migrations and config consumers. |
| `postgresql.external.credentialsSecret` | `string` | `estategap-db-credentials` | Secret containing `PGUSER` and `PGPASSWORD`. |
| `postgresql.readReplica.enabled` | `bool` | `false` | Expose read-replica host and port config to workloads. |
| `postgresql.readReplica.host` | `string` | `postgresql-read.databases.svc.cluster.local` | Shared PostgreSQL reader endpoint. |
| `postgresql.readReplica.port` | `int` | `5432` | Shared PostgreSQL reader port. |
| `postgresql.migrations.enabled` | `bool` | `true` | Run the Alembic hook Job on install and upgrade. |
| `postgresql.migrations.image` | `string` | `ghcr.io/andrea-mucci/estategap/pipeline:latest` | Image used for the migration hook Job. |
| `postgresql.migrations.timeout` | `int` | `300` | `activeDeadlineSeconds` for the migration hook Job. |

## Kafka

| Field | Type | Default | Description |
|---|---|---|---|
| `kafka.brokers` | `string` | `kafka-bootstrap.kafka.svc.cluster.local:9092` | Bootstrap brokers for the shared Kafka cluster. |
| `kafka.topicPrefix` | `string` | `estategap.` | Prefix applied to managed topic names. |
| `kafka.tls.enabled` | `bool` | `false` | Enable TLS for Kafka clients. |
| `kafka.tls.caSecret` | `string` | `""` | Optional secret that stores the Kafka CA certificate. |
| `kafka.sasl.enabled` | `bool` | `false` | Enable SASL for Kafka clients. |
| `kafka.sasl.mechanism` | `string` | `PLAIN` | SASL mechanism passed to jobs and workloads. |
| `kafka.sasl.credentialsSecret` | `string` | `""` | Secret containing `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD`. |
| `kafka.consumer.maxRetries` | `int` | `3` | Maximum retry count exposed in the Kafka config map. |
| `kafka.topicInit.enabled` | `bool` | `true` | Render the Kafka topic initialization hook Job. |
| `kafka.topicInit.replicationFactor` | `int` | `3` | Replication factor used when creating managed topics. |
| `kafka.topicInit.image.repository` | `string` | `bitnami/kafka` | Repository for the topic initialization image. |
| `kafka.topicInit.image.tag` | `string` | `3.7` | Tag for the topic initialization image. |
| `kafka.deadLetter.enabled` | `bool` | `true` | Create the dead-letter topic in the initialization hook. |
| `kafka.deadLetter.retentionDays` | `int` | `30` | Retention window for the dead-letter topic. |

## S3

| Field | Type | Default | Description |
|---|---|---|---|
| `s3.endpoint` | `string` | `https://fsn1.your-objectstorage.com` | S3-compatible object storage endpoint. |
| `s3.region` | `string` | `fsn1` | Object storage region identifier. |
| `s3.bucketPrefix` | `string` | `estategap` | Prefix applied to every logical bucket name. |
| `s3.forcePathStyle` | `bool` | `true` | Enables path-style S3 addressing for Hetzner Object Storage. |
| `s3.credentialsSecret` | `string` | `estategap-s3-credentials` | Namespace-local secret name containing S3 credentials. |
| `s3.buckets.mlModels` | `string` | `ml-models` | Logical suffix for model artifact storage. |
| `s3.buckets.trainingData` | `string` | `training-data` | Logical suffix for training dataset storage. |
| `s3.buckets.listingPhotos` | `string` | `listing-photos` | Logical suffix for listing photo storage. |
| `s3.buckets.exports` | `string` | `exports` | Logical suffix for GDPR export archive storage. |
| `s3.buckets.backups` | `string` | `backups` | Logical suffix for PostgreSQL backup storage. |

## Prometheus

| Field | Type | Default | Description |
|---|---|---|---|
| `prometheus.serviceMonitor.enabled` | `bool` | `true` | Render ServiceMonitor resources for enabled EstateGap services. |
| `prometheus.serviceMonitor.interval` | `string` | `15s` | Default scrape interval used when a service does not override it. |
| `prometheus.serviceMonitor.labels.release` | `string` | `prometheus` | Label set used to match the shared Prometheus operator selector. |
| `prometheus.rules.enabled` | `bool` | `true` | Render the PrometheusRule resource. |
| `prometheus.rules.labels.release` | `string` | `prometheus` | Labels applied to the PrometheusRule for selector matching. |

## Grafana

| Field | Type | Default | Description |
|---|---|---|---|
| `grafana.dashboards.enabled` | `bool` | `true` | Render dashboard ConfigMaps for shared Grafana sidecar pickup. |
| `grafana.dashboards.namespace` | `string` | `monitoring` | Namespace where dashboard ConfigMaps are created. |
| `grafana.dashboards.labels.grafana_dashboard` | `string` | `"1"` | Label used by the Grafana sidecar to import dashboards. |

## Removed Sections

- `cnpg.*`
- `observability.*`
- `prometheus.*` sub-chart passthrough values
- `grafana.*` sub-chart passthrough values
- `loki.*`
- `tempo.*`
- `kafka.sasl.username`
- `kafka.sasl.secretName`
- `kafka.initJob.*`
- `s3.credentials.secret`

## Secret Contracts

| Secret | Required Keys | Used By |
|---|---|---|
| `postgresql.external.credentialsSecret` | `PGUSER`, `PGPASSWORD` | Migration hook Job and workloads that compose PostgreSQL URLs from shared config. |
| `kafka.sasl.credentialsSecret` | `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD` | Kafka hook Job and workloads when SASL is enabled. |
| `s3.credentialsSecret` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | S3 client env injection and CNPG backup credentials when self-managed PostgreSQL is enabled. |
