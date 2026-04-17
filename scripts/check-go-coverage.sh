#!/usr/bin/env bash
set -euo pipefail

coverage_file="${1:-coverage.out}"
threshold="${COVERAGE_THRESHOLD:-80}"

if [[ ! -f "${coverage_file}" ]]; then
  echo "coverage file not found: ${coverage_file}" >&2
  exit 1
fi

coverage="$(go tool cover -func="${coverage_file}" | awk '/^total:/ {print $3}')"

if [[ -z "${coverage}" ]]; then
  echo "failed to extract coverage from ${coverage_file}" >&2
  exit 1
fi

coverage_value="${coverage%\%}"

if awk -v actual="${coverage_value}" -v minimum="${threshold}" 'BEGIN { exit !(actual + 0 >= minimum + 0) }'; then
  echo "Go coverage ${coverage} meets threshold ${threshold}%"
  exit 0
fi

echo "Go coverage ${coverage} is below threshold ${threshold}%" >&2
exit 1
