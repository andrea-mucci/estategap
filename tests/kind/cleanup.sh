#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="${ROOT_DIR}/.kind-pids"
CLUSTER_NAME="${CLUSTER_NAME:-estategap}"

if [[ -f "${PID_FILE}" ]]; then
  while read -r pid; do
    [[ -n "${pid}" ]] || continue
    kill -9 "${pid}" 2>/dev/null || true
  done < "${PID_FILE}"
  rm -f "${PID_FILE}"
fi

kind delete cluster --name "${CLUSTER_NAME}" >/dev/null 2>&1 || true
