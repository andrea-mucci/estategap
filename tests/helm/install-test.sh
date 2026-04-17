#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_FILE="/tmp/estategap-install-test.log"
PORT_FORWARD_PIDS=()

cleanup() {
  for pid in "${PORT_FORWARD_PIDS[@]:-}"; do
    kill "${pid}" 2>/dev/null || true
  done
}

capture_logs() {
  {
    echo "=== kubectl get pods -A ==="
    kubectl get pods -A
    echo
    echo "=== kubectl logs -A --all-containers ==="
    kubectl logs -A --all-containers=true --prefix --tail=-1
  } >"${LOG_FILE}" 2>&1 || true
}

trap 'capture_logs; cleanup' ERR
trap cleanup EXIT

cd "${ROOT_DIR}"

helm upgrade --install estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-test.yaml \
  -n estategap-system \
  --create-namespace \
  --wait \
  --timeout 5m

for namespace in estategap-system estategap-gateway estategap-scraping estategap-pipeline estategap-intelligence estategap-notifications; do
  if kubectl get deployment -n "${namespace}" --no-headers >/dev/null 2>&1; then
    deployment_count="$(kubectl get deployment -n "${namespace}" --no-headers 2>/dev/null | wc -l | tr -d ' ')"
    if [[ "${deployment_count}" != "0" ]]; then
      kubectl wait --for=condition=available deployment --all -n "${namespace}" --timeout=3m
    fi
  fi
done

kubectl port-forward svc/api-gateway 8080:8080 -n estategap-gateway >/tmp/estategap-install-api.log 2>&1 &
PORT_FORWARD_PIDS+=("$!")
kubectl port-forward svc/websocket-server 8081:8081 -n estategap-gateway >/tmp/estategap-install-ws.log 2>&1 &
PORT_FORWARD_PIDS+=("$!")

sleep 2

for port in 8080 8081; do
  success=0
  for attempt in 1 2 3 4 5; do
    if curl -sf "http://localhost:${port}/readyz" >/dev/null; then
      success=1
      break
    fi
    sleep 5
  done
  if [[ "${success}" != "1" ]]; then
    echo "Health check failed for port ${port}" >&2
    exit 1
  fi
done
