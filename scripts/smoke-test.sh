#!/usr/bin/env bash
set -euo pipefail

RELEASE_NAME="${RELEASE_NAME:-estategap}"
SYSTEM_NAMESPACE="${SYSTEM_NAMESPACE:-estategap-system}"
GATEWAY_NAMESPACE="${GATEWAY_NAMESPACE:-estategap-gateway}"
DOMAIN="${DOMAIN:-estategap.com}"
NATS_SERVER="${NATS_SERVER:-nats://nats.${SYSTEM_NAMESPACE}.svc.cluster.local:4222}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://minio.${SYSTEM_NAMESPACE}.svc.cluster.local:9000}"

required_streams=(
  raw-listings
  normalized-listings
  enriched-listings
  scored-listings
  alerts-triggers
  alerts-notifications
  scraper-commands
  price-changes
)

echo "Checking NATS streams..."
for stream in "${required_streams[@]}"; do
  kubectl run nats-verify --rm -i --restart=Never \
    --image=natsio/nats-box:latest \
    --command -- /bin/sh -ec "nats stream info ${stream} --server ${NATS_SERVER} >/dev/null"
done

echo "Checking PostGIS version..."
kubectl exec -n "${SYSTEM_NAMESPACE}" estategap-postgres-1 -- \
  psql -U app -d estategap -tAc "SELECT PostGIS_Version();" | grep -Eq '^3\.4'

echo "Checking Redis..."
REDIS_PASSWORD="$(kubectl get secret redis-credentials -n "${SYSTEM_NAMESPACE}" -o jsonpath='{.data.redis-password}' | base64 -d)"
kubectl exec -n "${SYSTEM_NAMESPACE}" redis-master-0 -- \
  redis-cli -a "${REDIS_PASSWORD}" ping | grep -qx 'PONG'

echo "Checking MinIO buckets..."
MINIO_ROOT_USER="$(kubectl get secret minio-credentials -n "${SYSTEM_NAMESPACE}" -o jsonpath='{.data.root-user}' | base64 -d)"
MINIO_ROOT_PASSWORD="$(kubectl get secret minio-credentials -n "${SYSTEM_NAMESPACE}" -o jsonpath='{.data.root-password}' | base64 -d)"
bucket_count="$(
  kubectl run minio-verify --rm -i --restart=Never \
    --image=minio/mc:latest \
    --command -- /bin/sh -ec "mc alias set local ${MINIO_ENDPOINT} ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} >/dev/null && mc ls local | wc -l"
)"
test "${bucket_count}" -eq 5

echo "Checking Grafana ingress..."
curl -fsS "https://grafana.${DOMAIN}/login" >/dev/null

echo "Smoke tests passed for release ${RELEASE_NAME}."
