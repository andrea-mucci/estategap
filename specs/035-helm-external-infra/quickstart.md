# Quickstart: Helm Chart External Infrastructure Refactor

## Prerequisites

```bash
# Add required repos (only redis and keda now)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# Resolve dependencies (cnpg/prometheus/loki/tempo are removed)
helm dependency update helm/estategap
```

## Deploy on Staging (External Infra)

### 1. Create required K8s Secrets

```bash
# PostgreSQL credentials (must contain PGUSER + PGPASSWORD)
kubectl create secret generic estategap-db-credentials \
  --from-literal=PGUSER=estategap \
  --from-literal=PGPASSWORD=<db-password> \
  -n estategap-system

# S3 / Hetzner credentials
kubectl create secret generic estategap-s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID=<access-key> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<secret-key> \
  -n estategap-system

# Kafka SASL credentials (only if kafka.sasl.enabled: true)
kubectl create secret generic estategap-kafka-sasl \
  --from-literal=KAFKA_SASL_USERNAME=estategap \
  --from-literal=KAFKA_SASL_PASSWORD=<sasl-password> \
  -n estategap-system
```

### 2. Install / Upgrade

```bash
helm upgrade --install estategap helm/estategap \
  --namespace estategap-system --create-namespace \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  --wait --timeout 10m
```

### 3. Verify wiring

```bash
# External DB host in ConfigMap
kubectl get configmap estategap-config -n estategap-system \
  -o jsonpath='{.data.DATABASE_HOST}'

# Migration Job completed
kubectl get job estategap-db-migrate -n estategap-system
kubectl logs job/estategap-db-migrate -n estategap-system

# ServiceMonitors registered
kubectl get servicemonitor -A -l app.kubernetes.io/part-of=estategap

# Prometheus rules active
kubectl get prometheusrule -n estategap-system

# Dashboard ConfigMaps in monitoring namespace
kubectl get configmap -n monitoring -l grafana_dashboard=1
```

## Kind Development Cluster

### Full local stack

```bash
# 1. Create cluster
kind create cluster --config tests/kind/kind-config.yaml

# 2. Install pre-requisite infrastructure
#    (simulates what the platform team provides)

# Strimzi Kafka
helm repo add strimzi https://strimzi.io/charts
helm install strimzi-operator strimzi/strimzi-kafka-operator \
  -n kafka --create-namespace
kubectl apply -f tests/kind/kafka-cluster.yaml
kubectl wait kafka/estategap-kafka -n kafka \
  --for=condition=Ready --timeout=5m

# Bitnami PostgreSQL + PostGIS
helm install postgresql bitnami/postgresql -n databases --create-namespace \
  --set auth.postgresPassword=testpassword --set image.tag=16
kubectl wait pod/postgresql-0 -n databases \
  --for=condition=Ready --timeout=3m
kubectl exec -n databases postgresql-0 -- \
  psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Prometheus operator (for ServiceMonitor CRD + dashboard import)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set grafana.sidecar.dashboards.enabled=true \
  --set grafana.sidecar.dashboards.label=grafana_dashboard \
  --set grafana.sidecar.dashboards.labelValue="1"

# 3. Create secrets
kubectl create ns estategap-system
kubectl create secret generic estategap-db-credentials \
  --from-literal=PGUSER=postgres \
  --from-literal=PGPASSWORD=testpassword \
  -n estategap-system
kubectl create secret generic estategap-s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID=minioadmin \
  --from-literal=AWS_SECRET_ACCESS_KEY=minioadmin \
  -n estategap-system

# 4. Install EstateGap
helm dependency update helm/estategap
helm install estategap helm/estategap \
  --namespace estategap-system \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml

# 5. Run chart tests
helm test estategap -n estategap-system
```

## Lint All Profiles

```bash
for profile in values-staging values-production values-test; do
  echo "=== Linting $profile ==="
  helm lint helm/estategap \
    -f helm/estategap/values.yaml \
    -f helm/estategap/${profile}.yaml
done
```

## Template Spot-Checks

```bash
# Verify no CNPG resources with postgresql disabled
helm template estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  | grep "kind:" | sort | uniq

# Verify no Cluster (CNPG) in output
helm template estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  | grep "kind: Cluster" | wc -l   # Should be 0

# Verify ServiceMonitors present
helm template estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  | grep "kind: ServiceMonitor" | wc -l   # Should be >= 7

# Verify PrometheusRule present
helm template estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  | grep "kind: PrometheusRule" | wc -l   # Should be 1

# Verify 7 dashboard ConfigMaps
helm template estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  | grep "estategap-dashboard-" | wc -l   # Should be 7
```
