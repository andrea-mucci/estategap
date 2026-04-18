# Quick Start: Deploy EstateGap on an Existing Cluster

> **Prerequisites** before running `helm install`:
> - Kubernetes 1.28+ with Helm 3.14+ installed
> - cert-manager installed (any issuer configured)
> - Prometheus operator ≥ 0.63 installed
> - KEDA 2.x installed
> - External Kafka cluster accessible from your namespace
> - External PostgreSQL 16 with PostGIS 3.4 accessible
> - Hetzner S3 (or S3-compatible) bucket created
> - `helm repo add bitnami https://charts.bitnami.com/bitnami && helm repo update`

---

## Step 1: Create Required Kubernetes Secrets

Run all commands below before installing the chart.

### Database credentials (used by migration job and all services)
```bash
kubectl create secret generic estategap-db-credentials \
  --namespace estategap-system \
  --from-literal=PGUSER=estategap \
  --from-literal=PGPASSWORD='<your-db-password>'
```

### S3 / Hetzner Object Storage credentials
```bash
kubectl create secret generic estategap-s3-credentials \
  --namespace estategap-system \
  --from-literal=AWS_ACCESS_KEY_ID='<your-access-key>' \
  --from-literal=AWS_SECRET_ACCESS_KEY='<your-secret-key>'
```

### Redis password (for Bitnami Redis sub-chart)
```bash
kubectl create secret generic redis-credentials \
  --namespace estategap-system \
  --from-literal=redis-password='<your-redis-password>'
```

### API Gateway secrets
```bash
kubectl create secret generic api-gateway-secrets \
  --namespace estategap-gateway \
  --from-literal=DB_PRIMARY_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require' \
  --from-literal=DB_REPLICA_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require' \
  --from-literal=REDIS_URL='redis://:<redis-password>@redis.estategap-system.svc.cluster.local:6379' \
  --from-literal=JWT_SECRET='<random-256-bit-hex>' \
  --from-literal=GOOGLE_CLIENT_ID='<google-oauth-client-id>' \
  --from-literal=GOOGLE_CLIENT_SECRET='<google-oauth-client-secret>' \
  --from-literal=GOOGLE_REDIRECT_URL='https://api.<your-domain>/v1/auth/google/callback' \
  --from-literal=STRIPE_SECRET_KEY='sk_live_...' \
  --from-literal=STRIPE_WEBHOOK_SECRET='whsec_...'
```

### Alert Engine secrets
```bash
kubectl create secret generic alert-engine-secrets \
  --namespace estategap-notifications \
  --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require' \
  --from-literal=DATABASE_REPLICA_URL='postgresql://estategap:<password>@<read-host>:5432/estategap?sslmode=require' \
  --from-literal=REDIS_URL='redis://:<redis-password>@redis.estategap-system.svc.cluster.local:6379'
```

### Alert Dispatcher secrets
```bash
kubectl create secret generic alert-dispatcher-secrets \
  --namespace estategap-notifications \
  --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require' \
  --from-literal=DATABASE_REPLICA_URL='...' \
  --from-literal=REDIS_URL='...' \
  --from-literal=TELEGRAM_BOT_TOKEN='...' \
  --from-literal=TWILIO_ACCOUNT_SID='...' \
  --from-literal=TWILIO_AUTH_TOKEN='...' \
  --from-literal=TWILIO_WHATSAPP_FROM='...' \
  --from-literal=TWILIO_WHATSAPP_TEMPLATE_SID='...' \
  --from-literal=FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}' \
  --from-literal=AWS_ACCESS_KEY_ID='...' \
  --from-literal=AWS_SECRET_ACCESS_KEY='...' \
  --from-literal=AWS_SESSION_TOKEN=''
```

### AI Chat secrets
```bash
kubectl create secret generic ai-chat-secrets \
  --namespace estategap-intelligence \
  --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require' \
  --from-literal=REDIS_URL='redis://:<redis-password>@redis.estategap-system.svc.cluster.local:6379' \
  --from-literal=ANTHROPIC_API_KEY='sk-ant-...' \
  --from-literal=OPENAI_API_KEY='sk-...'
```

### ML Scorer secrets
```bash
kubectl create secret generic ml-scorer-secrets \
  --namespace estategap-intelligence \
  --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require'
```

### ML Trainer secrets
```bash
kubectl create secret generic ml-trainer-secrets \
  --namespace estategap-system \
  --from-literal=DATABASE_URL='postgresql://estategap:<password>@<host>:5432/estategap?sslmode=require' \
  --from-literal=MLFLOW_TRACKING_URI='http://mlflow.estategap-system.svc.cluster.local:5000'
```

### App secrets (GDPR cron + spider-workers)
```bash
kubectl create secret generic estategap-app-secrets \
  --namespace estategap-system \
  --from-literal=username='estategap' \
  --from-literal=POSTGRES_PASSWORD='<your-db-password>' \
  --from-literal=dbname='estategap' \
  --from-literal=IDEALISTA_API_TOKEN='<your-idealista-token>'
```

---

## Step 2: Create a Minimal values-override.yaml

```yaml
# values-override.yaml — minimum required configuration
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
      release: prometheus  # MUST match your Prometheus operator's serviceMonitorSelector

grafana:
  dashboards:
    namespace: monitoring  # MUST match the namespace Grafana sidecar watches

argocd:
  repoURL: "https://github.com/your-org/estategap.git"

stripe:
  successUrl: "https://app.yourdomain.com/dashboard?checkout=success"
  cancelUrl: "https://app.yourdomain.com/pricing?checkout=cancelled"
  portalReturnUrl: "https://app.yourdomain.com/dashboard"
  priceBasicMonthly: "price_..."    # from Stripe Dashboard
  priceBasicAnnual: "price_..."
  priceProMonthly: "price_..."
  priceProAnnual: "price_..."
  priceGlobalMonthly: "price_..."
  priceGlobalAnnual: "price_..."
  priceApiMonthly: "price_..."
  priceApiAnnual: "price_..."
```

---

## Step 3: Install

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

helm dependency update helm/estategap

helm install estategap helm/estategap \
  --namespace estategap-system \
  --create-namespace \
  -f helm/estategap/values.yaml \
  -f values-override.yaml \
  --wait \
  --timeout 10m
```

---

## Step 4: Verify

```bash
# Check all pods are running
kubectl get pods -A -l app.kubernetes.io/part-of=estategap

# Check Helm release status
helm status estategap -n estategap-system

# Verify database migration completed
kubectl get jobs -n estategap-system

# Verify ServiceMonitors created
kubectl get servicemonitor -A -l app.kubernetes.io/part-of=estategap

# Verify Grafana dashboard ConfigMaps
kubectl get configmap -n monitoring -l grafana_dashboard=1
```
