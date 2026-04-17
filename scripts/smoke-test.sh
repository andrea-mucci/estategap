#!/usr/bin/env bash
set -euo pipefail

RELEASE_NAME="${RELEASE_NAME:-estategap}"
SYSTEM_NAMESPACE="${SYSTEM_NAMESPACE:-estategap-system}"
GATEWAY_NAMESPACE="${GATEWAY_NAMESPACE:-estategap-gateway}"
DOMAIN="${DOMAIN:-estategap.com}"
KAFKA_BROKERS="${KAFKA_BROKERS:-kafka-bootstrap.${SYSTEM_NAMESPACE}.svc.cluster.local:9092}"
KAFKA_TOPIC_PREFIX="${KAFKA_TOPIC_PREFIX:-estategap.}"
S3_ENDPOINT="${S3_ENDPOINT:-http://localstack.${SYSTEM_NAMESPACE}.svc.cluster.local:4566}"
S3_REGION="${S3_REGION:-us-east-1}"
S3_BUCKET_PREFIX="${S3_BUCKET_PREFIX:-estategap}"

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

echo "Checking S3 buckets..."
S3_ACCESS_KEY_ID="$(kubectl get secret estategap-s3-credentials -n "${SYSTEM_NAMESPACE}" -o jsonpath='{.data.AWS_ACCESS_KEY_ID}' | base64 -d)"
S3_SECRET_ACCESS_KEY="$(kubectl get secret estategap-s3-credentials -n "${SYSTEM_NAMESPACE}" -o jsonpath='{.data.AWS_SECRET_ACCESS_KEY}' | base64 -d)"
kubectl run s3-verify --rm -i --restart=Never -n "${SYSTEM_NAMESPACE}" \
  --image=amazon/aws-cli:2.17.51 \
  --env="AWS_ACCESS_KEY_ID=${S3_ACCESS_KEY_ID}" \
  --env="AWS_SECRET_ACCESS_KEY=${S3_SECRET_ACCESS_KEY}" \
  --env="AWS_DEFAULT_REGION=${S3_REGION}" \
  --command -- /bin/sh -ec "aws s3 ls --endpoint-url ${S3_ENDPOINT} s3://${S3_BUCKET_PREFIX}-ml-models >/dev/null"

echo "Checking Grafana ingress..."
curl -fsS "https://grafana.${DOMAIN}/login" >/dev/null

echo "Smoke tests passed for release ${RELEASE_NAME}."
