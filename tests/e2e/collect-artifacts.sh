#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-reports/e2e/artifacts}"
mkdir -p "$OUTPUT_DIR"/{logs,describe,db,nats}

for namespace in estategap-gateway estategap-system monitoring; do
  if ! kubectl get namespace "$namespace" >/dev/null 2>&1; then
    continue
  fi

  mkdir -p "$OUTPUT_DIR/logs/$namespace"
  while read -r pod; do
    [ -n "$pod" ] || continue
    kubectl logs -n "$namespace" "$pod" --all-containers=true >"$OUTPUT_DIR/logs/$namespace/$pod.log" 2>&1 || true
    phase="$(kubectl get pod -n "$namespace" "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    if [ "$phase" != "Running" ] && [ "$phase" != "Succeeded" ]; then
      kubectl describe pod -n "$namespace" "$pod" >"$OUTPUT_DIR/describe/$namespace-$pod.txt" 2>&1 || true
    fi
  done < <(kubectl get pods -n "$namespace" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)
done

if command -v pg_dump >/dev/null 2>&1; then
  PGPASSWORD="${PGPASSWORD:-postgres}" \
    pg_dump --host="${PGHOST:-localhost}" --port="${PGPORT:-5432}" --username="${PGUSER:-postgres}" --dbname="${PGDATABASE:-estategap}" \
    >"$OUTPUT_DIR/db/dump.sql" 2>"$OUTPUT_DIR/db/dump.stderr" || true
fi

if command -v nats >/dev/null 2>&1; then
  {
    nats stream info raw-listings || true
    nats stream info normalized-listings || true
    nats stream info enriched-listings || true
    nats stream info scored-listings || true
    nats stream info alerts-notifications || true
  } >"$OUTPUT_DIR/nats/stream-info.txt" 2>&1
fi
