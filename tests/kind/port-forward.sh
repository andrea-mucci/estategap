#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="${ROOT_DIR}/.kind-pids"

cleanup() {
  if [[ -f "${PID_FILE}" ]]; then
    while read -r pid; do
      [[ -n "${pid}" ]] || continue
      kill "${pid}" 2>/dev/null || true
    done < "${PID_FILE}"
    rm -f "${PID_FILE}"
  fi
}

trap cleanup SIGINT SIGTERM ERR

: > "${PID_FILE}"

specs=(
  "estategap-gateway api-gateway 8080:8080"
  "estategap-gateway websocket-server 8081:8081"
  "estategap-gateway frontend 3000:3000"
  "monitoring grafana 3001:80"
  "monitoring prometheus-kube-prometheus-prometheus 9090:9090"
  "estategap-system estategap-postgres-rw 5432:5432"
)

for spec in "${specs[@]}"; do
  read -r namespace service mapping <<<"${spec}"
  if ! kubectl get svc "${service}" -n "${namespace}" >/dev/null 2>&1; then
    continue
  fi

  log_file="/tmp/estategap-port-forward-${service}.log"
  kubectl port-forward -n "${namespace}" "svc/${service}" "${mapping}" >"${log_file}" 2>&1 &
  echo "$!" >> "${PID_FILE}"
done

trap - SIGINT SIGTERM ERR
