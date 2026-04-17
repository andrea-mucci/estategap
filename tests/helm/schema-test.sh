#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "${ROOT_DIR}"

if helm install estategap-schema-test helm/estategap --dry-run --set global.imageRegistry=123invalid >/dev/null 2>&1; then
  echo "FAIL: schema should have rejected invalid global.imageRegistry" >&2
  exit 1
fi

if helm install estategap-schema-test helm/estategap --dry-run --set postgresql.instances=-1 >/dev/null 2>&1; then
  echo "FAIL: schema should have rejected invalid postgresql.instances" >&2
  exit 1
fi

echo "Schema validation: PASSED"
