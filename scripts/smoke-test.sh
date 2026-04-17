#!/usr/bin/env bash
set -euo pipefail

RELEASE_NAME="${RELEASE_NAME:-estategap}"
SYSTEM_NAMESPACE="${SYSTEM_NAMESPACE:-estategap-system}"
GATEWAY_NAMESPACE="${GATEWAY_NAMESPACE:-estategap-gateway}"
DOMAIN="${DOMAIN:-estategap.com}"
KAFKA_BROKERS="${KAFKA_BROKERS:-kafka-bootstrap.${SYSTEM_NAMESPACE}.svc.cluster.local:9092}"
KAFKA_TOPIC_PREFIX="${KAFKA_TOPIC_PREFIX:-estategap.}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://minio.${SYSTEM_NAMESPACE}.svc.cluster.local:9000}"

required_topics=(
  raw-listings
  normalized-listings
  enriched-listings
  scored-listings
  alerts-triggers
  alerts-notifications
  scraper-commands
  scraper-cycle
  price-changes
  dead-letter
)

echo "Checking Kafka topics..."
for topic in "${required_topics[@]}"; do
  kubectl run kafka-verify --rm -i --restart=Never -n "${SYSTEM_NAMESPACE}" \
    --image=bitnami/kafka:latest \
    --command -- /bin/sh -ec "/opt/bitnami/kafka/bin/kafka-topics.sh --bootstrap-server ${KAFKA_BROKERS} --describe --topic ${KAFKA_TOPIC_PREFIX}${topic} >/dev/null"
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
