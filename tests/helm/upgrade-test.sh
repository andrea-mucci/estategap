#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
TMP_CHART_DIR="/tmp/estategap-v2"
PORT_FORWARD_PID=""

cleanup() {
  [[ -n "${PORT_FORWARD_PID}" ]] && kill "${PORT_FORWARD_PID}" 2>/dev/null || true
  helm uninstall estategap -n estategap-system >/dev/null 2>&1 || true
  rm -rf "${TMP_CHART_DIR}"
}

trap cleanup EXIT

cd "${ROOT_DIR}"
mkdir -p "${DIST_DIR}"
rm -rf "${TMP_CHART_DIR}"

helm package helm/estategap -d "${DIST_DIR}" --version 0.1.0 >/dev/null
cp -R helm/estategap "${TMP_CHART_DIR}"
sed -i 's/^version: .*/version: 0.2.0/' "${TMP_CHART_DIR}/Chart.yaml"
helm package "${TMP_CHART_DIR}" -d "${DIST_DIR}" --version 0.2.0 >/dev/null

helm install estategap "${DIST_DIR}/estategap-0.1.0.tgz" \
  -f helm/estategap/values-test.yaml \
  -n estategap-system \
  --create-namespace \
  --wait \
  --timeout 5m

uv run --project tests/fixtures python tests/fixtures/load.py

postgres_pod="$(kubectl get pods -n estategap-system -l cnpg.io/cluster=estategap-postgres -o jsonpath='{.items[0].metadata.name}')"
before_count="$(kubectl exec -n estategap-system "${postgres_pod}" -- psql -U app -d estategap -tAc "SELECT COUNT(*) FROM listings")"

helm upgrade estategap "${DIST_DIR}/estategap-0.2.0.tgz" \
  -f helm/estategap/values-test.yaml \
  -n estategap-system \
  --wait \
  --timeout 5m

after_count="$(kubectl exec -n estategap-system "${postgres_pod}" -- psql -U app -d estategap -tAc "SELECT COUNT(*) FROM listings")"
[[ "${before_count}" == "${after_count}" ]]

helm rollback estategap 1 -n estategap-system --wait --timeout 3m

kubectl port-forward -n estategap-gateway svc/api-gateway 8080:8080 >/tmp/estategap-upgrade-api.log 2>&1 &
PORT_FORWARD_PID="$!"
sleep 2
curl -sf http://localhost:8080/healthz >/dev/null
