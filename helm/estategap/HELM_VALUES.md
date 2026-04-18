# EstateGap Helm Values Reference

This guide is the operator-facing companion to `values.yaml`. Use it for first-time installs, secret creation, scaling changes, schema expectations, and failure analysis without reading the templates.

## Table of Contents

- [1. Quick Start](#1-quick-start)
- [2. External Services](#2-external-services)
- [3. Application Services](#3-application-services)
- [4. Security](#4-security)
- [5. Observability](#5-observability)
- [6. Feature Flags](#6-feature-flags)
- [7. Scaling Guide](#7-scaling-guide)
- [8. Migration Guide v2 to v3](#8-migration-guide-v2-to-v3)
- [9. Troubleshooting](#9-troubleshooting)

## 1. Quick Start

The chart defaults enable every EstateGap workload, so a first deployment needs namespaces, shared infrastructure endpoints, and the application Secrets listed below.

### Prerequisites checklist

- Kubernetes `1.28+`
- Helm `3.14+`
- cert-manager with a working issuer referenced by `cluster.certIssuer`
- Prometheus Operator `0.63+`
- KEDA `2.x`
- External Kafka reachable from the cluster
- External PostgreSQL 16 + PostGIS reachable from the cluster
- S3-compatible object storage with five buckets (or a shared prefix)

```bash
kubectl create namespace estategap-system --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace estategap-gateway --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace estategap-notifications --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace estategap-intelligence --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace estategap-scraping --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace estategap-pipeline --dry-run=client -o yaml | kubectl apply -f -
```

### Step 1: Create required Secrets

`estategap-system`

```bash
kubectl create secret generic estategap-db-credentials   --namespace estategap-system   --from-literal=PGUSER=estategap   --from-literal=PGPASSWORD='<db-password>'

kubectl create secret generic estategap-s3-credentials   --namespace estategap-system   --from-literal=AWS_ACCESS_KEY_ID='<access-key>'   --from-literal=AWS_SECRET_ACCESS_KEY='<secret-key>'

kubectl create secret generic redis-credentials   --namespace estategap-system   --from-literal=redis-password='<redis-password>'

kubectl create secret generic ml-trainer-secrets   --namespace estategap-system   --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require'   --from-literal=MLFLOW_TRACKING_URI='http://mlflow.estategap-system.svc.cluster.local:5000'

kubectl create secret generic estategap-app-secrets   --namespace estategap-system   --from-literal=username='estategap'   --from-literal=POSTGRES_PASSWORD='<db-password>'   --from-literal=dbname='estategap'   --from-literal=IDEALISTA_API_TOKEN='<idealista-token>'
```

`estategap-gateway`

```bash
kubectl create secret generic api-gateway-secrets   --namespace estategap-gateway   --from-literal=DB_PRIMARY_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require'   --from-literal=DB_REPLICA_URL='postgresql://estategap:<password>@<read-host>:5432/estategap?sslmode=require'   --from-literal=REDIS_URL='redis://:<redis-password>@redis.estategap-system.svc.cluster.local:6379'   --from-literal=JWT_SECRET='<random-256-bit-hex>'   --from-literal=GOOGLE_CLIENT_ID='<google-oauth-client-id>'   --from-literal=GOOGLE_CLIENT_SECRET='<google-oauth-client-secret>'   --from-literal=GOOGLE_REDIRECT_URL='https://api.<your-domain>/v1/auth/google/callback'   --from-literal=STRIPE_SECRET_KEY='sk_live_...'   --from-literal=STRIPE_WEBHOOK_SECRET='whsec_...'
```

`estategap-notifications`

```bash
kubectl create secret generic alert-engine-secrets   --namespace estategap-notifications   --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require'   --from-literal=DATABASE_REPLICA_URL='postgresql://estategap:<password>@<read-host>:5432/estategap?sslmode=require'   --from-literal=REDIS_URL='redis://:<redis-password>@redis.estategap-system.svc.cluster.local:6379'

kubectl create secret generic alert-dispatcher-secrets   --namespace estategap-notifications   --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require'   --from-literal=DATABASE_REPLICA_URL='postgresql://estategap:<password>@<read-host>:5432/estategap?sslmode=require'   --from-literal=REDIS_URL='redis://:<redis-password>@redis.estategap-system.svc.cluster.local:6379'   --from-literal=TELEGRAM_BOT_TOKEN='...'   --from-literal=TWILIO_ACCOUNT_SID='...'   --from-literal=TWILIO_AUTH_TOKEN='...'   --from-literal=TWILIO_WHATSAPP_FROM='...'   --from-literal=TWILIO_WHATSAPP_TEMPLATE_SID='...'   --from-literal=FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'   --from-literal=AWS_ACCESS_KEY_ID='...'   --from-literal=AWS_SECRET_ACCESS_KEY='...'   --from-literal=AWS_SESSION_TOKEN=''
```

`estategap-intelligence`

```bash
kubectl create secret generic ai-chat-secrets   --namespace estategap-intelligence   --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require'   --from-literal=REDIS_URL='redis://:<redis-password>@redis.estategap-system.svc.cluster.local:6379'   --from-literal=ANTHROPIC_API_KEY='sk-ant-...'   --from-literal=OPENAI_API_KEY='sk-...'

kubectl create secret generic ml-scorer-secrets   --namespace estategap-intelligence   --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require'
```

### Step 2: Create a minimal override file

```yaml
cluster:
  environment: production
  domain: yourdomain.com
  certIssuer: letsencrypt-prod

kafka:
  brokers: "kafka-bootstrap.kafka.svc.cluster.local:9092"
  topicPrefix: "estategap."

postgresql:
  external:
    host: "postgresql.databases.svc.cluster.local"
    port: 5432
    database: "estategap"
    sslmode: "require"
    credentialsSecret: "estategap-db-credentials"

s3:
  endpoint: "https://fsn1.your-objectstorage.com"
  region: "fsn1"
  bucketPrefix: "estategap"
  credentialsSecret: "estategap-s3-credentials"

prometheus:
  serviceMonitor:
    labels:
      release: prometheus

grafana:
  dashboards:
    namespace: monitoring

argocd:
  repoURL: "https://github.com/your-org/estategap.git"

stripe:
  successUrl: "https://app.yourdomain.com/dashboard?checkout=success"
  cancelUrl: "https://app.yourdomain.com/pricing?checkout=cancelled"
  portalReturnUrl: "https://app.yourdomain.com/dashboard"
  priceBasicMonthly: "price_..."
  priceBasicAnnual: "price_..."
  priceProMonthly: "price_..."
  priceProAnnual: "price_..."
  priceGlobalMonthly: "price_..."
  priceGlobalAnnual: "price_..."
  priceApiMonthly: "price_..."
  priceApiAnnual: "price_..."
```

### Step 3: Install the chart

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

helm dependency update helm/estategap

helm install estategap helm/estategap   --namespace estategap-system   --create-namespace   -f helm/estategap/values.yaml   -f values-override.yaml   --wait   --timeout 10m
```

### Step 4: Verify the deployment

```bash
kubectl get pods -A -l app.kubernetes.io/part-of=estategap
helm status estategap -n estategap-system
kubectl get jobs -n estategap-system
kubectl get servicemonitor -A -l app.kubernetes.io/part-of=estategap
kubectl get ingressroute,certificate -A -l app.kubernetes.io/part-of=estategap
```

## 2. External Services

These values wire EstateGap to shared infrastructure instead of deploying Kafka, PostgreSQL, Prometheus, or Grafana as sub-charts.

### Kafka

| Value Path | Description | Type | Default | Required |
|---|---|---|---|---|
| `kafka.brokers` | Bootstrap broker list used by the topic-init Job and shared config map. | `string` | `kafka-bootstrap.kafka.svc.cluster.local:9092` | Yes |
| `kafka.topicPrefix` | Prefix for managed topic names. | `string` | `estategap.` | Yes |
| `kafka.tls.enabled` | Enable TLS for Kafka clients. | `bool` | `false` | No |
| `kafka.tls.caSecret` | Secret that stores the Kafka CA bundle. | `string` | `""` | When TLS enabled |
| `kafka.sasl.enabled` | Enable SASL auth for Kafka clients. | `bool` | `false` | No |
| `kafka.sasl.mechanism` | SASL mechanism. | `string` | `PLAIN` | When SASL enabled |
| `kafka.sasl.credentialsSecret` | Secret with `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD`. | `string` | `""` | When SASL enabled |
| `kafka.consumer.maxRetries` | Retry count exposed via `estategap-kafka-config`. | `int` | `3` | No |
| `kafka.topicInit.enabled` | Render the Kafka topic-init Job. | `bool` | `true` | No |
| `kafka.topicInit.replicationFactor` | Replication factor for managed topics. | `int` | `3` | No |
| `kafka.topicInit.image.repository` | Topic-init image repository. | `string` | `bitnami/kafka` | No |
| `kafka.topicInit.image.tag` | Topic-init image tag. | `string` | `3.7` | No |
| `kafka.deadLetter.enabled` | Create the dead-letter topic. | `bool` | `true` | No |
| `kafka.deadLetter.retentionDays` | Dead-letter retention period. | `int` | `30` | No |

Authentication secret format:

```bash
kubectl create secret generic kafka-sasl   --namespace estategap-system   --from-literal=KAFKA_SASL_USERNAME='<username>'   --from-literal=KAFKA_SASL_PASSWORD='<password>'
```

Connection verification:

```bash
kubectl exec -n kafka deploy/kafka-client --   kafka-topics.sh --bootstrap-server kafka-bootstrap.kafka.svc.cluster.local:9092 --list
```

| Symptom | Root cause | Fix |
|---|---|---|
| TLS handshake failures | `kafka.tls.enabled` is `true` but `kafka.tls.caSecret` is empty or wrong. | Mount the correct CA Secret and confirm the broker certificate chain. |
| `SASL authentication failed` | Wrong mechanism or wrong Secret keys. | Set `kafka.sasl.mechanism` to `PLAIN`, `SCRAM-SHA-256`, or `SCRAM-SHA-512` and recreate the Secret. |
| Consumers see no messages | Broker list or topic prefix is wrong. | Verify `kafka.brokers`, `kafka.topicPrefix`, and the topic-init Job logs. |

### PostgreSQL

| Value Path | Description | Type | Default | Required |
|---|---|---|---|---|
| `postgresql.external.host` | Primary writer endpoint. | `string` | `postgresql.databases.svc.cluster.local` | Yes |
| `postgresql.external.port` | PostgreSQL port. | `int` | `5432` | No |
| `postgresql.external.database` | Application database name. | `string` | `estategap` | Yes |
| `postgresql.external.sslmode` | SSL mode passed to clients. | `string` | `require` | No |
| `postgresql.external.credentialsSecret` | Secret with `PGUSER` and `PGPASSWORD`. | `string` | `estategap-db-credentials` | Yes |
| `postgresql.readReplica.enabled` | Publish reader endpoint values. | `bool` | `false` | No |
| `postgresql.readReplica.host` | Reader endpoint. | `string` | `postgresql-read.databases.svc.cluster.local` | When read replica enabled |
| `postgresql.readReplica.port` | Reader port. | `int` | `5432` | When read replica enabled |
| `postgresql.migrations.enabled` | Run the migration Job on install/upgrade. | `bool` | `true` | No |
| `postgresql.migrations.image` | Image used by the migration Job. | `string` | `ghcr.io/andrea-mucci/estategap/pipeline:latest` | No |
| `postgresql.migrations.timeout` | Active deadline for migrations. | `int` | `300` | No |

Authentication secret format:

```bash
kubectl create secret generic estategap-db-credentials   --namespace estategap-system   --from-literal=PGUSER=estategap   --from-literal=PGPASSWORD='<db-password>'
```

Connection verification:

```bash
kubectl run psql-check --rm -it --restart=Never --image=postgres:16   --env="PGPASSWORD=<db-password>" --   psql "host=postgresql.databases.svc.cluster.local port=5432 dbname=estategap user=estategap sslmode=require" -c 'select 1'
```

| Symptom | Root cause | Fix |
|---|---|---|
| `connection refused` | Wrong host, port, or network policy. | Verify DNS, open the target port, and compare against `postgresql.external.*`. |
| SSL mode errors | `sslmode` does not match the server policy. | Set `disable`, `require`, `verify-ca`, or `verify-full` correctly. |
| Migration Job loops | Migration image lacks Alembic or credentials are wrong. | Rebuild the migration image or recreate `estategap-db-credentials`. |

### S3 Object Storage

| Value Path | Description | Type | Default | Required |
|---|---|---|---|---|
| `s3.endpoint` | S3-compatible endpoint URL. | `string` | `https://fsn1.your-objectstorage.com` | Yes |
| `s3.region` | Region string. | `string` | `fsn1` | Yes |
| `s3.bucketPrefix` | Prefix prepended to all buckets. | `string` | `estategap` | Yes |
| `s3.forcePathStyle` | Enable path-style addressing. | `bool` | `true` | Yes |
| `s3.credentialsSecret` | Secret with `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. | `string` | `estategap-s3-credentials` | Yes |
| `s3.buckets.mlModels` | Model artifact bucket suffix. | `string` | `ml-models` | No |
| `s3.buckets.trainingData` | Training-data bucket suffix. | `string` | `training-data` | No |
| `s3.buckets.listingPhotos` | Listing-photo bucket suffix. | `string` | `listing-photos` | No |
| `s3.buckets.exports` | GDPR export bucket suffix. | `string` | `exports` | No |
| `s3.buckets.backups` | Backup bucket suffix. | `string` | `backups` | No |

Authentication secret format:

```bash
kubectl create secret generic estategap-s3-credentials   --namespace estategap-system   --from-literal=AWS_ACCESS_KEY_ID='<access-key>'   --from-literal=AWS_SECRET_ACCESS_KEY='<secret-key>'
```

Connection verification:

```bash
AWS_ACCESS_KEY_ID='<access-key>' AWS_SECRET_ACCESS_KEY='<secret-key>' aws --endpoint-url https://fsn1.your-objectstorage.com s3 ls
```

| Symptom | Root cause | Fix |
|---|---|---|
| `AccessDenied` | Wrong Secret values or wrong bucket prefix. | Recreate the Secret and confirm the prefixed buckets exist. |
| `301 moved permanently` or signature errors | Path-style flag or region is wrong. | Set `s3.forcePathStyle: true` for Hetzner/MinIO-compatible backends and confirm `s3.region`. |
| App cannot resolve the endpoint | Non-HTTPS endpoint or DNS issue. | Use a valid `https://` endpoint or `http://localstack:4566` for tests only. |

### Prometheus

| Value Path | Description | Type | Default | Required |
|---|---|---|---|---|
| `prometheus.serviceMonitor.enabled` | Render ServiceMonitors for enabled workloads. | `bool` | `true` | No |
| `prometheus.serviceMonitor.interval` | Default scrape interval. | `string` | `15s` | No |
| `prometheus.serviceMonitor.labels.release` | Label matched by the Prometheus operator selector. | `string` | `prometheus` | Yes |
| `prometheus.rules.enabled` | Render the PrometheusRule. | `bool` | `true` | No |
| `prometheus.rules.labels.release` | Label matched by the rule selector. | `string` | `prometheus` | Yes |

Verification:

```bash
kubectl get prometheus -A -o jsonpath='{.items[*].spec.serviceMonitorSelector}'
kubectl get servicemonitor -A -l app.kubernetes.io/part-of=estategap
```

| Symptom | Root cause | Fix |
|---|---|---|
| Targets never appear | `release` label does not match the Prometheus selector. | Set `prometheus.serviceMonitor.labels.release` to the selector value. |
| Rules exist but never load | PrometheusRule labels do not match the operator selector. | Align `prometheus.rules.labels` with the cluster selector. |

### Grafana

| Value Path | Description | Type | Default | Required |
|---|---|---|---|---|
| `grafana.dashboards.enabled` | Render dashboard ConfigMaps. | `bool` | `true` | No |
| `grafana.dashboards.namespace` | Namespace watched by the Grafana sidecar. | `string` | `monitoring` | Yes |
| `grafana.dashboards.labels.grafana_dashboard` | Dashboard discovery label. | `string` | `"1"` | Yes |

Verification:

```bash
kubectl get configmap -n monitoring -l grafana_dashboard=1
kubectl logs -n monitoring deploy/grafana | rg 'dashboard'
```

| Symptom | Root cause | Fix |
|---|---|---|
| Dashboards never import | Wrong namespace or wrong sidecar label. | Match `grafana.dashboards.namespace` and `grafana.dashboards.labels.grafana_dashboard` to the sidecar settings. |
| Dashboard ConfigMaps exist but are stale | Sidecar lacks RBAC or label scope. | Expand Grafana sidecar permissions or correct the watched label/namespace. |

## 3. Application Services

### Service overview

| Service | Namespace | Port | Metrics Port | Liveness | Readiness | HPA | KEDA |
|---|---|---:|---:|---|---|---|---|
| `api-gateway` | `estategap-gateway` | `8080` | `8080` | `/healthz` | `/readyz` | Yes | No |
| `websocket-server` | `estategap-gateway` | `8081` | `8081` | n/a | n/a | No | No |
| `alert-engine` | `estategap-notifications` | `8080` | `8080` | `/health/live` | `/health/ready` | No | No |
| `alert-dispatcher` | `estategap-notifications` | `8081` | `8081` | `/healthz` | `/readyz` | No | No |
| `scrape-orchestrator` | `estategap-scraping` | `8082` | `8082` | `/health` | `/health` | No | No |
| `proxy-manager` | `estategap-scraping` | `50052` | `9090` | n/a | n/a | No | No |
| `spider-workers` | `estategap-scraping` | `9102` | `9102` | n/a | n/a | No | Yes |
| `pipeline` | `estategap-pipeline` | `8080` | `8080` | n/a | n/a | No | No |
| `pipeline-enricher` | `estategap-pipeline` | `9103` | `9103` | n/a | n/a | No | No |
| `pipeline-change-detector` | `estategap-pipeline` | `9104` | `9104` | n/a | n/a | No | No |
| `ml-scorer` | `estategap-intelligence` | `50051` | `9091` | TCP `grpc` | TCP `grpc` | Yes | No |
| `ai-chat` | `estategap-intelligence` | `50053` | `9090` | `/metrics` | TCP `grpc` | Yes | No |
| `frontend` | `estategap-gateway` | `3000` | `3000` | n/a | n/a | No | No |

### Common environment variables

The `estategap.commonEnv` helper injects these shared variables into every service that uses the generic deployment helper:

| Variable | Source | Notes |
|---|---|---|
| `CLUSTER_ENVIRONMENT` | Inline from `cluster.environment` | Always present. |
| `DATABASE_HOST` | `estategap-config` ConfigMap | Writer endpoint. |
| `DATABASE_PORT` | `estategap-config` ConfigMap | Writer port. |
| `DATABASE_NAME` | `estategap-config` ConfigMap | Database name. |
| `DATABASE_SSLMODE` | `estategap-config` ConfigMap | SSL mode. |
| `DATABASE_RO_HOST` | `estategap-config` ConfigMap | Present only when `postgresql.readReplica.enabled` is true. |
| `DATABASE_RO_PORT` | `estategap-config` ConfigMap | Present only when `postgresql.readReplica.enabled` is true. |
| `REDIS_HOST` | Inline | `redis.estategap-system.svc.cluster.local` |
| `REDIS_PORT` | Inline | `6379` |
| `REDIS_SENTINEL_HOST` | Inline | `redis.estategap-system.svc.cluster.local` |
| `REDIS_SENTINEL_PORT` | Inline | `26379` |
| `KAFKA_BROKERS` | `estategap-kafka-config` ConfigMap | Always present. |
| `KAFKA_TOPIC_PREFIX` | `estategap-kafka-config` ConfigMap | Always present. |
| `KAFKA_TLS_ENABLED` | `estategap-kafka-config` ConfigMap | Always present. |
| `KAFKA_MAX_RETRIES` | `estategap-kafka-config` ConfigMap | Always present. |
| `KAFKA_SASL_MECHANISM` | `estategap-kafka-config` ConfigMap | Only when SASL is enabled. |
| `KAFKA_SASL_USERNAME` | Secret | Only when SASL is enabled. |
| `KAFKA_SASL_PASSWORD` | Secret | Only when SASL is enabled. |
| `S3_ENDPOINT` | Inline from `s3.endpoint` | Always present. |
| `S3_REGION` | Inline from `s3.region` | Always present. |
| `S3_BUCKET_PREFIX` | Inline from `s3.bucketPrefix` | Always present. |
| `S3_ACCESS_KEY_ID` | Secret from `s3.credentialsSecret` | Always present. |
| `S3_SECRET_ACCESS_KEY` | Secret from `s3.credentialsSecret` | Always present. |

Inspect the rendered environment for any service with:

```bash
kubectl get deploy api-gateway -n estategap-gateway -o jsonpath='{.spec.template.spec.containers[0].env}' | jq
```

### Service-specific environment variables

#### `api-gateway`

| Variable | Source | Purpose |
|---|---|---|
| `PORT` | Inline | HTTP listener port. |
| `LOG_LEVEL` | Inline | Structured logging level. |
| `ALLOWED_ORIGINS` | Inline | Browser origins allowed by CORS. |
| `CSP_REPORT_ONLY` | Inline | Toggle report-only CSP mode. |
| `CSP_REPORT_URI` | Inline | Optional CSP report endpoint. |
| `DB_PRIMARY_URL` | Secret `api-gateway-secrets` | Primary PostgreSQL DSN. |
| `DB_REPLICA_URL` | Secret `api-gateway-secrets` | Read replica DSN. |
| `REDIS_URL` | Secret `api-gateway-secrets` | Redis connection URL. |
| `JWT_SECRET` | Secret `api-gateway-secrets` | JWT signing secret. |
| `GOOGLE_CLIENT_ID` | Secret `api-gateway-secrets` | Google OAuth client ID. |
| `GOOGLE_CLIENT_SECRET` | Secret `api-gateway-secrets` | Google OAuth secret. |
| `GOOGLE_REDIRECT_URL` | Secret `api-gateway-secrets` | Google OAuth callback URL. |
| `STRIPE_SECRET_KEY` | Secret `api-gateway-secrets` | Stripe API key. |
| `STRIPE_WEBHOOK_SECRET` | Secret `api-gateway-secrets` | Stripe webhook signing secret. |
| `STRIPE_*` price and return URLs | `estategap-config` ConfigMap | Checkout and catalog settings. |

#### `alert-engine`

| Variable | Source | Purpose |
|---|---|---|
| `DATABASE_URL` | Secret `alert-engine-secrets` | Primary PostgreSQL DSN. |
| `DATABASE_REPLICA_URL` | Secret `alert-engine-secrets` | Read replica DSN. |
| `REDIS_URL` | Secret `alert-engine-secrets` | Redis connection URL. |
| `RULE_CACHE_REFRESH_INTERVAL` | Inline | Rule reload interval. |
| `WORKER_POOL_SIZE` | Inline | Worker pool override (`0` means auto/default). |
| `BATCH_SIZE` | Inline | Batch size for rule evaluation. |
| `HEALTH_PORT` | Inline | Health endpoint port. |
| `LOG_LEVEL` | Inline | Structured logging level. |

#### `alert-dispatcher`

| Variable | Source | Purpose |
|---|---|---|
| `DATABASE_URL` | Secret `alert-dispatcher-secrets` | Primary PostgreSQL DSN. |
| `DATABASE_REPLICA_URL` | Secret `alert-dispatcher-secrets` | Read replica DSN. |
| `REDIS_URL` | Secret `alert-dispatcher-secrets` | Redis connection URL. |
| `TELEGRAM_BOT_TOKEN` | Secret `alert-dispatcher-secrets` | Telegram delivery credentials. |
| `TWILIO_ACCOUNT_SID` | Secret `alert-dispatcher-secrets` | Twilio account SID. |
| `TWILIO_AUTH_TOKEN` | Secret `alert-dispatcher-secrets` | Twilio auth token. |
| `TWILIO_WHATSAPP_FROM` | Secret `alert-dispatcher-secrets` | WhatsApp sender. |
| `TWILIO_WHATSAPP_TEMPLATE_SID` | Secret `alert-dispatcher-secrets` | WhatsApp template. |
| `FIREBASE_CREDENTIALS_JSON` | Secret `alert-dispatcher-secrets` | Push delivery credentials. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` | Secret `alert-dispatcher-secrets` | SES delivery credentials. |
| `config.logLevel` | Inline | Dispatcher log level. |
| `config.healthPort` | Inline | Health endpoint port. |
| `config.baseUrl` | Inline | Public API base URL used in notifications. |
| `config.workerPoolSize` | Inline | Delivery worker pool size. |
| `config.batchSize` | Inline | Delivery batch size. |
| `config.awsRegion` | Inline | AWS region for SES. |
| `config.awsSesFromAddress` | Inline | SES sender address. |
| `config.awsSesFromName` | Inline | SES sender name. |

#### `ai-chat`

| Variable | Source | Purpose |
|---|---|---|
| `GRPC_PORT` | Inline | gRPC listener port. |
| `METRICS_PORT` | Inline | Metrics listener port. |
| `LLM_PROVIDER` | Inline | Primary LLM provider. |
| `FALLBACK_LLM_PROVIDER` | Inline | Fallback LLM provider. |
| `LITELLM_MODEL` | Inline | LiteLLM routing target. |
| `API_GATEWAY_GRPC_ADDR` | Inline | Upstream API gateway address. |
| `LOG_LEVEL` | Inline | Structured logging level. |
| `DATABASE_URL` | Secret `ai-chat-secrets` | PostgreSQL DSN. |
| `REDIS_URL` | Secret `ai-chat-secrets` | Redis URL. |
| `ANTHROPIC_API_KEY` | Secret `ai-chat-secrets` | Anthropic API key. |
| `OPENAI_API_KEY` | Secret `ai-chat-secrets` | OpenAI API key. |

#### `spider-workers`

| Variable | Source | Purpose |
|---|---|---|
| `LOG_LEVEL` | Inline | Structured logging level. |
| `REDIS_URL` | Inline | Redis queue/cache URL. |
| `PROXY_MANAGER_ADDR` | Inline | gRPC address of proxy-manager. |
| `METRICS_PORT` | Inline | Metrics listener port. |
| `REQUEST_MIN_DELAY` | Inline | Minimum crawl delay. |
| `REQUEST_MAX_DELAY` | Inline | Maximum crawl delay. |
| `MAX_CONCURRENT_PER_PORTAL` | Inline | Concurrency per portal. |
| `SESSION_ROTATION_EVERY` | Inline | Requests before rotating a session. |
| `QUARANTINE_TTL_DAYS` | Inline | Days to quarantine a bad source. |
| `IDEALISTA_API_TOKEN` | Secret `estategap-app-secrets` | Idealista API token. |
| `keda.stream` / `keda.consumer` / `keda.lagThreshold` | Values | Kafka lag trigger for autoscaling. |

#### `proxy-manager`

| Variable | Source | Purpose |
|---|---|---|
| `LOG_LEVEL` | Inline | Structured logging level. |
| `REDIS_URL` | Inline | Redis URL for proxy state. |
| `GRPC_PORT` | Inline | gRPC listener port. |
| `METRICS_PORT` | Inline | Metrics listener port. |
| `BLACKLIST_TTL` | Inline | Seconds a failing proxy remains blacklisted. |
| `STICKY_TTL` | Inline | Seconds sticky sessions are preserved. |
| `HEALTH_THRESHOLD` | Inline | Proxy health score threshold. |
| `PROXY_COUNTRIES` | Inline | Country codes enabled in the pool. |
| `PROXY_IT_*` / `PROXY_ES_*` | Inline | Provider name, endpoint, username, and password for the country-specific proxy pools. Replace all `replace-me` values before production use. |

## 4. Security

### Secret inventory

With the chart defaults, these Secrets must exist before a clean install succeeds:

| Secret Name | Namespace | Required Keys | Used By |
|---|---|---|---|
| `estategap-db-credentials` | `estategap-system` | `PGUSER`, `PGPASSWORD` | Migration Job and any workload composing PostgreSQL URLs from shared config. |
| `estategap-s3-credentials` | `estategap-system` plus replicated namespaces | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Shared S3 credential env injection. |
| `redis-credentials` | `estategap-system` | `redis-password` | Bitnami Redis auth and GDPR CronJob. |
| `api-gateway-secrets` | `estategap-gateway` | `DB_PRIMARY_URL`, `DB_REPLICA_URL`, `REDIS_URL`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URL`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | API Gateway. |
| `alert-engine-secrets` | `estategap-notifications` | `DATABASE_URL`, `DATABASE_REPLICA_URL`, `REDIS_URL` | Alert Engine. |
| `alert-dispatcher-secrets` | `estategap-notifications` | `DATABASE_URL`, `DATABASE_REPLICA_URL`, `REDIS_URL`, `TELEGRAM_BOT_TOKEN`, `TWILIO_*`, `FIREBASE_CREDENTIALS_JSON`, `AWS_*` | Alert Dispatcher. |
| `ai-chat-secrets` | `estategap-intelligence` | `DATABASE_URL`, `REDIS_URL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | AI Chat. |
| `ml-scorer-secrets` | `estategap-intelligence` | `DATABASE_URL` | ML Scorer. |
| `ml-trainer-secrets` | `estategap-system` | `DATABASE_URL`, `MLFLOW_TRACKING_URI` | ML Trainer CronJob. |
| `estategap-app-secrets` | `estategap-system` | `username`, `POSTGRES_PASSWORD`, `dbname`, `IDEALISTA_API_TOKEN` | GDPR CronJob and spider-workers. |

### `kubectl create secret generic` commands

These commands mirror the Quick Start so platform and security teams can manage secrets independently of the install workflow.

```bash
kubectl create secret generic estategap-db-credentials --namespace estategap-system --from-literal=PGUSER=estategap --from-literal=PGPASSWORD='<db-password>'
kubectl create secret generic estategap-s3-credentials --namespace estategap-system --from-literal=AWS_ACCESS_KEY_ID='<access-key>' --from-literal=AWS_SECRET_ACCESS_KEY='<secret-key>'
kubectl create secret generic redis-credentials --namespace estategap-system --from-literal=redis-password='<redis-password>'
kubectl create secret generic api-gateway-secrets --namespace estategap-gateway --from-literal=DB_PRIMARY_URL='postgresql://...' --from-literal=DB_REPLICA_URL='postgresql://...' --from-literal=REDIS_URL='redis://...' --from-literal=JWT_SECRET='...' --from-literal=GOOGLE_CLIENT_ID='...' --from-literal=GOOGLE_CLIENT_SECRET='...' --from-literal=GOOGLE_REDIRECT_URL='https://api.<domain>/v1/auth/google/callback' --from-literal=STRIPE_SECRET_KEY='sk_live_...' --from-literal=STRIPE_WEBHOOK_SECRET='whsec_...'
kubectl create secret generic alert-engine-secrets --namespace estategap-notifications --from-literal=DATABASE_URL='postgresql://...' --from-literal=DATABASE_REPLICA_URL='postgresql://...' --from-literal=REDIS_URL='redis://...'
kubectl create secret generic alert-dispatcher-secrets --namespace estategap-notifications --from-literal=DATABASE_URL='postgresql://...' --from-literal=DATABASE_REPLICA_URL='postgresql://...' --from-literal=REDIS_URL='redis://...' --from-literal=TELEGRAM_BOT_TOKEN='...' --from-literal=TWILIO_ACCOUNT_SID='...' --from-literal=TWILIO_AUTH_TOKEN='...' --from-literal=TWILIO_WHATSAPP_FROM='...' --from-literal=TWILIO_WHATSAPP_TEMPLATE_SID='...' --from-literal=FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}' --from-literal=AWS_ACCESS_KEY_ID='...' --from-literal=AWS_SECRET_ACCESS_KEY='...' --from-literal=AWS_SESSION_TOKEN=''
kubectl create secret generic ai-chat-secrets --namespace estategap-intelligence --from-literal=DATABASE_URL='postgresql://...' --from-literal=REDIS_URL='redis://...' --from-literal=ANTHROPIC_API_KEY='sk-ant-...' --from-literal=OPENAI_API_KEY='sk-...'
kubectl create secret generic ml-scorer-secrets --namespace estategap-intelligence --from-literal=DATABASE_URL='postgresql://...'
kubectl create secret generic ml-trainer-secrets --namespace estategap-system --from-literal=DATABASE_URL='postgresql://...' --from-literal=MLFLOW_TRACKING_URI='http://mlflow.estategap-system.svc.cluster.local:5000'
kubectl create secret generic estategap-app-secrets --namespace estategap-system --from-literal=username='estategap' --from-literal=POSTGRES_PASSWORD='<db-password>' --from-literal=dbname='estategap' --from-literal=IDEALISTA_API_TOKEN='<idealista-token>'
```

### Sealed Secrets integration

If you use GitOps, replace the raw secret-creation step with Sealed Secrets. Every leaf value under `sealedSecrets.*` is a placeholder that must be replaced with `kubeseal --raw` output.

```bash
kubeseal --fetch-cert --controller-namespace kube-system > pub-cert.pem

echo -n '<db-password>' | kubeseal --raw --from-file=/dev/stdin --scope strict --cert pub-cert.pem
```

Workflow:

- Create a normal Secret manifest with `kubectl create secret generic ... --dry-run=client -o yaml`.
- Pipe the manifest through `kubeseal --format yaml`.
- Copy the encrypted data values into `sealedSecrets.*`.
- Apply the chart; the Sealed Secrets controller writes the real Secret into the target namespace.

### TLS and ingress

- `cluster.domain` is the base domain for the Traefik `IngressRoute` objects.
- `cluster.certIssuer` is passed to the certificate templates and must match an existing cert-manager `Issuer` or `ClusterIssuer`.
- Use a staging issuer first to avoid ACME rate limits while testing DNS and ingress.

```bash
kubectl get issuer,clusterissuer
kubectl get certificate -A -l app.kubernetes.io/part-of=estategap
kubectl describe ingressroute -n estategap-gateway api-gateway
```

### Network policies

The chart renders five namespace-wide egress policies:

| Policy | Namespace | Allowed egress |
|---|---|---|
| `allow-gateway-egress` | `estategap-gateway` | Unrestricted |
| `restrict-scraping-egress` | `estategap-scraping` | `estategap-system` plus DNS |
| `restrict-pipeline-egress` | `estategap-pipeline` | `estategap-system` plus DNS |
| `restrict-intelligence-egress` | `estategap-intelligence` | `estategap-system` plus DNS |
| `restrict-notifications-egress` | `estategap-notifications` | `estategap-system`, `estategap-gateway`, plus DNS |

If a service needs a new external destination, extend the matching policy before rollout.

## 5. Observability

### ServiceMonitor setup

The most common monitoring issue is a selector mismatch. `prometheus.serviceMonitor.labels.release` must match the Prometheus operator's `serviceMonitorSelector`.

```bash
kubectl get prometheus -A -o jsonpath='{.items[*].spec.serviceMonitorSelector}'
kubectl get servicemonitor -A -l app.kubernetes.io/part-of=estategap
```

### Grafana dashboards

The chart renders ConfigMaps with the label defined by `grafana.dashboards.labels`. The Grafana sidecar must watch the same namespace and label.

```bash
kubectl get configmap -n monitoring -l grafana_dashboard=1
kubectl logs -n monitoring deploy/grafana | rg 'dashboard|sidecar'
```

### Alert reference

| Alert Name | Group | Condition | Threshold | For |
|---|---|---|---|---|
| `ScraperSuccessRateLow` | `estategap.scraping` | Scraper success rate | `< 80%` | `5m` |
| `PipelineLagHigh` | `estategap.pipeline` | Pipeline lag seconds | `> 300` | `5m` |
| `MLScorerErrorRateHigh` | `estategap.ml` | Error rate / prediction rate | `> 5%` | `5m` |
| `APILatencyP99High` | `estategap.api` | HTTP p99 latency | `> 2s` | `5m` |
| `KafkaConsumerLagHigh` | `estategap.kafka` | Consumer lag | `> 10000` messages | `2m` |
| `PodRestartCountHigh` | `estategap.pods` | Pod restarts in `15m` | `> 3` | `0m` |
| `PVCDiskUsageHigh` | `estategap.storage` | PVC usage ratio | `> 80%` | `5m` |

### Log format

Go services emit `slog` JSON, and Python services emit structured JSON through `structlog`. Expect these keys consistently in log streams:

- `time`
- `level`
- `msg`
- `service`
- `trace_id`

```json
{"time":"2026-04-18T12:00:00Z","level":"INFO","msg":"request complete","service":"api-gateway","trace_id":"01HV..."}
```

## 6. Feature Flags

### Infrastructure toggles

| Flag | Default | What it deploys | Implication of `false` |
|---|---|---|---|
| `components.redis.deploy` | `true` | Bitnami Redis with Sentinel | EstateGap expects an external Redis and the hard-coded service DNS no longer works. |
| `components.mlflow.deploy` | `true` | Reserved MLflow resources | Leave enabled unless you intentionally remove MLflow-related resources. |
| `components.kafka.deploy` | `false` | Reserved placeholder only | Kafka remains an external shared-cluster service. |
| `components.postgresql.deploy` | `false` | Reserved placeholder only | PostgreSQL remains external. |
| `components.prometheus.deploy` | `false` | Reserved placeholder only | Prometheus remains external. |
| `components.grafana.deploy` | `false` | Reserved placeholder only | Grafana remains external. |

Template rendering uses standard Helm `if` guards. This is how the chart suppresses optional manifests:

```gotemplate
{{- if .Values.components.redis.deploy }}
# render Bitnami Redis resources
{{- end }}
```

### Service toggles

Every workload has its own `services.<name>.enabled` flag. Disable a service only if you are also removing the traffic and data dependencies that feed it.

```yaml
services:
  alert-dispatcher:
    enabled: false
```

### Dependency matrix

The table below describes the primary dependencies the chart wires into each workload.

| Service | Needs PostgreSQL | Needs Kafka | Needs Redis | Needs S3 | Needs MLflow |
|---|---|---|---|---|---|
| `api-gateway` | Yes | No | Yes | No | No |
| `websocket-server` | No | No | Yes | No | No |
| `alert-engine` | Yes | No | Yes | No | No |
| `alert-dispatcher` | Yes | No | Yes | No | No |
| `scrape-orchestrator` | Yes | No | Yes | No | No |
| `proxy-manager` | No | No | Yes | No | No |
| `spider-workers` | No | Yes | Yes | No | No |
| `pipeline` | Yes | Yes | Yes | Yes | No |
| `pipeline-enricher` | Yes | Yes | Yes | No | No |
| `pipeline-change-detector` | Yes | Yes | Yes | No | No |
| `ml-scorer` | Yes | Yes | No | Yes | No |
| `ai-chat` | Yes | No | Yes | No | No |
| `frontend` | No | No | No | No | No |

## 7. Scaling Guide

Choose a profile based on concurrent listings volume, crawl rate, and model refresh frequency. All examples below are valid override fragments for `values-override.yaml`.

### Profile summary

| Profile | Listings | Countries | `api-gateway` | `spider-workers` | `ml-scorer` | `pipeline` | Redis |
|---|---|---|---|---|---|---|---|
| Small | Up to `100k` | `1` | `1` replica / `256Mi` | `1` replica / `512Mi` | `1` replica / `512Mi` | `1` replica / `512Mi` | `maxmemory 512mb` |
| Medium | Up to `1M` | `2-3` | `2` replicas / `512Mi` | `3` replicas / `1Gi` | `2` replicas / `1Gi` | `2` replicas / `1Gi` | `maxmemory 1gb` |
| Large | `1M+` | `4+` | HPA `3-12` / `1Gi+` | KEDA `5-50` / `2Gi+` | HPA `3-10` / `4Gi+` | HPA `3-8` / `2Gi+` | `maxmemory 4gb` |

### Small profile

```yaml
services:
  api-gateway:
    replicaCount: 1
    hpa:
      enabled: false
    resources:
      requests:
        memory: 256Mi
  spider-workers:
    replicaCount: 1
    keda:
      enabled: false
    resources:
      requests:
        memory: 512Mi
  ml-scorer:
    hpa:
      enabled: false
    resources:
      requests:
        memory: 512Mi
  pipeline:
    resources:
      requests:
        memory: 512Mi
redis:
  commonConfiguration: |
    maxmemory 512mb
    maxmemory-policy allkeys-lru
```

### Medium profile

```yaml
services:
  api-gateway:
    replicaCount: 2
    hpa:
      enabled: true
      minReplicas: 2
      maxReplicas: 6
  spider-workers:
    replicaCount: 3
    keda:
      enabled: true
      minReplicas: 3
      maxReplicas: 20
      lagThreshold: "100"
  ml-scorer:
    hpa:
      enabled: true
      minReplicas: 2
      maxReplicas: 6
    resources:
      requests:
        memory: 1Gi
  pipeline:
    replicaCount: 2
    resources:
      requests:
        memory: 1Gi
redis:
  commonConfiguration: |
    maxmemory 1gb
    maxmemory-policy allkeys-lru
```

### Large profile

```yaml
services:
  api-gateway:
    hpa:
      enabled: true
      minReplicas: 3
      maxReplicas: 12
      cpuTarget: 60
  spider-workers:
    keda:
      enabled: true
      minReplicas: 5
      maxReplicas: 50
      lagThreshold: "50"
    resources:
      requests:
        memory: 2Gi
  ml-scorer:
    hpa:
      enabled: true
      minReplicas: 3
      maxReplicas: 10
      cpuTarget: 70
    resources:
      requests:
        memory: 4Gi
  pipeline:
    replicaCount: 3
    resources:
      requests:
        memory: 2Gi
redis:
  commonConfiguration: |
    maxmemory 4gb
    maxmemory-policy allkeys-lru
```

Validate any profile before rollout:

```bash
helm lint helm/estategap -f helm/estategap/values.yaml -f values-override.yaml
```

## 8. Migration Guide v2 to v3

Version 3 removes the old self-managed infrastructure sub-charts and assumes a brownfield cluster with shared services.

### Pre-migration checklist

- cert-manager is installed and `cluster.certIssuer` exists
- Prometheus Operator `0.63+` is installed
- KEDA `2.x` is installed
- All required Secrets exist in the target namespaces
- S3 buckets exist and use the expected EstateGap prefix
- Kafka topics already exist or `kafka.topicInit.enabled` remains `true`

### Values diff

| Key | v2 (removed) | v3 replacement |
|---|---|---|
| Messaging | `nats.*` | `kafka.brokers`, `kafka.topicPrefix`, `kafka.sasl.*`, `kafka.tls.*` |
| PostgreSQL | `cnpg.*` / sub-chart defaults | `postgresql.external.*` |
| Object storage | `minio.*` | `s3.endpoint`, `s3.region`, `s3.bucketPrefix`, `s3.credentialsSecret` |
| Monitoring | `kube-prometheus-stack.*` | `prometheus.serviceMonitor.*`, `prometheus.rules.*` |
| Dashboards | bundled Grafana sub-chart values | `grafana.dashboards.namespace`, `grafana.dashboards.labels.*` |
| Secrets | raw Secret manifests | `sealedSecrets.*` or pre-created Secrets |

### Data migration

No data migration is required for the v2-to-v3 chart transition. Features `033` through `035` moved infrastructure ownership out of the chart without changing the application schema or object layout.

### Rollback

```bash
helm rollback estategap -n estategap-system
```

If you roll back all the way to a v2 chart, recreate any legacy sub-chart PVCs and credentials that no longer exist in v3.

## 9. Troubleshooting

Each scenario below includes a symptom, a copy-paste diagnostic command, the most likely root causes, and the fix sequence.

### 1. CrashLoopBackOff: `estategap-db-credentials` missing

- **Symptom**: the migration Job or application pods fail immediately with missing `PGUSER` / `PGPASSWORD`.
- **Diagnose**:

```bash
kubectl get secret estategap-db-credentials -n estategap-system
kubectl logs job/estategap-estategap-db-migration -n estategap-system --tail=100
```

- **Root causes**:
  - Secret was never created.
  - Secret exists in the wrong namespace.
  - Required keys are missing or misspelled.
- **Fix**:
  - Recreate the Secret in `estategap-system` with `PGUSER` and `PGPASSWORD`.
  - Re-run the release with `helm upgrade --install`.

### 2. CrashLoopBackOff: `api-gateway-secrets` missing

- **Symptom**: `api-gateway` pods never become Ready and log missing secret-key errors.
- **Diagnose**:

```bash
kubectl get secret api-gateway-secrets -n estategap-gateway
kubectl describe pod -n estategap-gateway -l app.kubernetes.io/component=api-gateway
```

- **Root causes**:
  - Secret not created in `estategap-gateway`.
  - One or more required keys are absent.
  - SealedSecret has not been decrypted yet.
- **Fix**:
  - Recreate `api-gateway-secrets` with all OAuth, Stripe, DB, and Redis keys.
  - If using Sealed Secrets, confirm the controller has written the backing Secret.

### 3. Database connection refused

- **Symptom**: workloads start but fail health checks with PostgreSQL connection errors.
- **Diagnose**:

```bash
kubectl get configmap estategap-config -n estategap-system -o yaml | rg 'DATABASE_'
kubectl run psql-check --rm -it --restart=Never --image=postgres:16 --   psql "host=<host> port=5432 dbname=estategap user=estategap sslmode=require" -c 'select 1'
```

- **Root causes**:
  - Wrong `postgresql.external.host` or port.
  - Wrong `sslmode`.
  - Notification, pipeline, or intelligence namespaces are blocked by network policy.
  - Credentials in the Secret are stale.
- **Fix**:
  - Correct `postgresql.external.*` values.
  - Match `sslmode` to the server policy.
  - Extend the matching `NetworkPolicy` if the database lives outside `estategap-system`.
  - Recreate `estategap-db-credentials`.

### 4. Kafka consumer not receiving data

- **Symptom**: workers are healthy but consumer lag never changes or topics stay empty.
- **Diagnose**:

```bash
kubectl logs job/estategap-estategap-kafka-topics-init -n estategap-system --tail=100
kubectl exec -n kafka deploy/kafka-client -- kafka-topics.sh --bootstrap-server <broker> --list
```

- **Root causes**:
  - Wrong `kafka.brokers`.
  - SASL or TLS settings do not match the cluster.
  - Topics were never created because `kafka.topicInit.enabled` is off or the Job failed.
  - Consumer group name does not match the expected lag metric.
- **Fix**:
  - Correct the broker list.
  - Recreate the SASL or CA Secret and verify the mechanism.
  - Re-run the topic-init Job or create topics manually.

### 5. S3 access denied

- **Symptom**: ML, export, or backup flows fail with `AccessDenied` or signature mismatch errors.
- **Diagnose**:

```bash
kubectl get secret estategap-s3-credentials -n estategap-system
kubectl logs -n estategap-intelligence deploy/ml-scorer --tail=100 | rg 'S3|AccessDenied|signature'
```

- **Root causes**:
  - Wrong access key or secret key.
  - Buckets do not exist with the configured prefix.
  - Wrong endpoint or region.
  - `s3.forcePathStyle` is wrong for the target provider.
- **Fix**:
  - Recreate the Secret with valid keys.
  - Create the prefixed buckets.
  - Confirm endpoint, region, and path-style settings.

### 6. ServiceMonitor targets not appearing in Prometheus

- **Symptom**: ServiceMonitors exist, but Prometheus shows no EstateGap targets.
- **Diagnose**:

```bash
kubectl get servicemonitor -A -l app.kubernetes.io/part-of=estategap
kubectl get prometheus -A -o jsonpath='{.items[*].spec.serviceMonitorSelector}'
```

- **Root causes**:
  - `prometheus.serviceMonitor.labels.release` does not match the operator selector.
  - Namespace selector in the Prometheus CR excludes EstateGap namespaces.
- **Fix**:
  - Align the `release` label.
  - Expand the Prometheus namespace selector if needed.

### 7. Grafana dashboards missing

- **Symptom**: Dashboard ConfigMaps exist, but nothing appears in Grafana.
- **Diagnose**:

```bash
kubectl get configmap -n monitoring -l grafana_dashboard=1
kubectl logs -n monitoring deploy/grafana | rg 'dashboard|sidecar'
```

- **Root causes**:
  - `grafana.dashboards.namespace` is wrong.
  - The sidecar watches a different label than `grafana_dashboard=1`.
  - Grafana lacks RBAC to read the namespace.
- **Fix**:
  - Match the namespace and label to the sidecar configuration.
  - Update RBAC if the sidecar cannot list ConfigMaps.

### 8. Migration Job `backoffLimit exceeded`

- **Symptom**: the install or upgrade blocks on the migration hook Job.
- **Diagnose**:

```bash
kubectl describe job -n estategap-system -l app.kubernetes.io/component=db-migration
kubectl logs -n estategap-system job/estategap-estategap-db-migration --tail=200
```

- **Root causes**:
  - Database is unreachable.
  - Credentials are wrong.
  - The migration image does not include Alembic or the migrations.
  - Schema is already at head but the job entrypoint exits non-zero.
- **Fix**:
  - Validate the DSN and Secret values.
  - Rebuild the migration image if Alembic is missing.
  - Fix the migration scripts or mark the failed revision before rerunning.

### 9. Spider-workers not scaling via KEDA

- **Symptom**: `spider-workers` stays at one replica even with a growing command stream.
- **Diagnose**:

```bash
kubectl get scaledobject -n estategap-scraping
kubectl describe scaledobject spider-workers -n estategap-scraping
kubectl logs -n keda deploy/keda-operator --tail=100
```

- **Root causes**:
  - KEDA is not installed.
  - `keda.enabled` or `services.spider-workers.keda.enabled` is false.
  - `stream`, `consumer`, or `lagThreshold` does not match the Kafka metrics.
- **Fix**:
  - Install KEDA.
  - Enable the ScaledObject.
  - Correct the stream and consumer names.

### 10. TLS certificate not issued

- **Symptom**: IngressRoute exists but HTTPS never comes up and the Certificate remains Pending or Failed.
- **Diagnose**:

```bash
kubectl get certificate -A -l app.kubernetes.io/part-of=estategap
kubectl describe certificate -n estategap-gateway api-gateway
kubectl get issuer,clusterissuer
```

- **Root causes**:
  - `cluster.certIssuer` does not match a real issuer.
  - DNS is not pointing at the ingress controller.
  - ACME rate limits or HTTP-01 validation failures.
- **Fix**:
  - Correct `cluster.certIssuer`.
  - Fix DNS and ingress reachability.
  - Retry with a staging issuer if Let's Encrypt rate limits were hit.
