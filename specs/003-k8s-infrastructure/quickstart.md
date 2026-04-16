# Quickstart: Kubernetes Infrastructure

**Feature**: 003-k8s-infrastructure
**Date**: 2026-04-16

---

## Prerequisites

Ensure these are already installed and configured on the cluster before proceeding:

```bash
# Verify required cluster components
kubectl get clusterissuer letsencrypt-prod  # cert-manager
kubectl get crd ingressroutes.traefik.io   # Traefik CRDs
kubectl get crd sealedsecrets.bitnami.com  # Sealed Secrets controller
kubectl get deployment argocd-server -n argocd  # ArgoCD
kubectl get crd clusters.postgresql.cnpg.io     # CloudNativePG operator
```

---

## 1. Create Sealed Secrets

Before running `helm install`, replace the scaffold resources in `helm/estategap/templates/sealed-secrets.yaml` with real `kubeseal` output. Use the `kubeseal` CLI with your cluster's public key:

```bash
# Fetch the cluster public key once
kubeseal --fetch-cert --controller-namespace kube-system > pub-cert.pem

# Create the main application secrets
kubectl create secret generic estategap-app-secrets \
  --namespace estategap-system \
  --from-literal=POSTGRES_PASSWORD='<strong-password>' \
  --from-literal=POSTGRES_REPLICATION_PASSWORD='<strong-password>' \
  --from-literal=REDIS_PASSWORD='<strong-password>' \
  --from-literal=MINIO_ROOT_USER='<minio-admin>' \
  --from-literal=MINIO_ROOT_PASSWORD='<strong-password>' \
  --from-literal=STRIPE_SECRET_KEY='sk_...' \
  --from-literal=STRIPE_WEBHOOK_SECRET='whsec_...' \
  --from-literal=LLM_API_KEY_ANTHROPIC='sk-ant-...' \
  --from-literal=LLM_API_KEY_OPENAI='sk-...' \
  --from-literal=JWT_SECRET='<random-256-bit-hex>' \
  --dry-run=client -o yaml | \
  kubeseal --cert pub-cert.pem --format yaml > /tmp/estategap-app-secrets.yaml

# Create PostgreSQL backup credentials
kubectl create secret generic postgresql-backup-credentials \
  --namespace estategap-system \
  --from-literal=ACCESS_KEY_ID='<minio-access-key>' \
  --from-literal=SECRET_ACCESS_KEY='<minio-secret-key>' \
  --dry-run=client -o yaml | \
  kubeseal --cert pub-cert.pem --format yaml > /tmp/postgresql-backup-credentials.yaml

# Create Redis credentials
kubectl create secret generic redis-credentials \
  --namespace estategap-system \
  --from-literal=redis-password='<strong-password>' \
  --dry-run=client -o yaml | \
  kubeseal --cert pub-cert.pem --format yaml > /tmp/redis-credentials.yaml

# Create MinIO credentials
kubectl create secret generic minio-credentials \
  --namespace estategap-system \
  --from-literal=root-user='<minio-admin>' \
  --from-literal=root-password='<strong-password>' \
  --dry-run=client -o yaml | \
  kubeseal --cert pub-cert.pem --format yaml > /tmp/minio-credentials.yaml

# Create Grafana credentials
kubectl create secret generic grafana-credentials \
  --namespace monitoring \
  --from-literal=admin-user='admin' \
  --from-literal=admin-password='<strong-password>' \
  --dry-run=client -o yaml | \
  kubeseal --cert pub-cert.pem --format yaml > /tmp/grafana-credentials.yaml
```

Copy the `spec.encryptedData` values from those generated files into the placeholder entries in `helm/estategap/templates/sealed-secrets.yaml`, or replace the scaffold manifests entirely with the generated YAML.

---

## 2. Configure Environment Values

Edit `helm/estategap/values-staging.yaml` and set:

```yaml
argocd:
  repoURL: "https://github.com/<your-org>/estategap"
```

---

## 3. Add Helm Repositories

```bash
helm repo add nats https://nats-io.github.io/k8s/helm/charts
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

---

## 4. Install / Upgrade Dependencies

```bash
cd helm/estategap
helm dependency update
```

---

## 5. Deploy to Staging

```bash
helm install estategap . \
  --namespace estategap-system \
  --create-namespace \
  --values values.yaml \
  --values values-staging.yaml \
  --wait \
  --timeout 10m
```

### 5.1 Bootstrap ArgoCD Once

```bash
helm template estategap . \
  --values values.yaml \
  --values values-staging.yaml \
  --show-only templates/argocd-application.yaml | \
  kubectl apply -f -

argocd app get estategap-staging
```

---

## 6. Verify Deployment

### NATS Streams
```bash
kubectl run nats-verify --rm -it --restart=Never \
  --image=natsio/nats-box:latest \
  -- nats stream ls \
     --server nats://nats.estategap-system.svc.cluster.local:4222
# Expected: 8 streams listed
```

### PostgreSQL + PostGIS
```bash
kubectl exec -it estategap-postgres-1 -n estategap-system \
  -- psql -U app -d estategap \
  -c "SELECT PostGIS_Version();"
# Expected: 3.4.x
```

### Redis
```bash
kubectl exec -it redis-master-0 -n estategap-system \
  -- redis-cli -a "$REDIS_PASSWORD" ping
# Expected: PONG
```

### MinIO Buckets
```bash
kubectl exec -it minio-0 -n estategap-system \
  -- mc ls local/
# Expected: 5 buckets
```

### Grafana
```bash
# Open in browser
echo "https://grafana.$(kubectl get ingressroute grafana-route -n estategap-gateway \
  -o jsonpath='{.spec.routes[0].match}' | grep -o 'Host.*' | cut -d'`' -f2)"
# Or simply: https://grafana.estategap.com
```

---

## 7. Production Deployment

```bash
helm upgrade estategap . \
  --namespace estategap-system \
  --values values.yaml \
  --values values-production.yaml \
  --wait \
  --timeout 15m
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| NATS pods in `CrashLoopBackOff` | JetStream requires at least 1Gi storage per pod | Check PVC provisioning |
| PostgreSQL primary never Ready | CloudNativePG operator not installed | Run prerequisite check |
| MinIO bucket setup Job fails | MinIO pod not yet Ready when Job starts | Re-run: `kubectl delete job minio-bucket-setup -n estategap-system` |
| Grafana shows "Data source error" | Prometheus/Loki/Tempo not Ready yet | Wait for observability stack to stabilize (2–3 min) |
| Sealed Secrets not decrypting | Wrong cluster public key used when sealing | Re-seal secrets with current cluster cert |
| ArgoCD not syncing | `repoURL` not set in values-staging.yaml | Edit values file and run `helm upgrade` |

---

## Clean Up

```bash
helm uninstall estategap --namespace estategap-system
# Note: PVCs are NOT deleted by Helm uninstall to protect data
# To fully clean up:
kubectl delete pvc --all -n estategap-system
kubectl delete namespace estategap-system estategap-gateway \
  estategap-scraping estategap-pipeline estategap-intelligence \
  estategap-notifications monitoring
```
