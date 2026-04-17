#!/usr/bin/env bash
set -euo pipefail

required_vars=(
  S3_ENDPOINT
  S3_REGION
  S3_ACCESS_KEY_ID
  S3_SECRET_ACCESS_KEY
  S3_BUCKET_PREFIX
)

for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "missing required environment variable: ${var}" >&2
    exit 1
  fi
done

export AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY}"
export AWS_DEFAULT_REGION="${S3_REGION}"

buckets=(
  "${S3_BUCKET_PREFIX}-ml-models"
  "${S3_BUCKET_PREFIX}-training-data"
  "${S3_BUCKET_PREFIX}-listing-photos"
  "${S3_BUCKET_PREFIX}-exports"
  "${S3_BUCKET_PREFIX}-backups"
)

for bucket in "${buckets[@]}"; do
  if aws s3 ls --endpoint-url "${S3_ENDPOINT}" "s3://${bucket}" >/dev/null 2>&1; then
    echo "skip ${bucket} (already exists)"
    continue
  fi

  if aws s3 mb --endpoint-url "${S3_ENDPOINT}" "s3://${bucket}" >/tmp/create-s3-buckets.log 2>&1; then
    echo "created ${bucket}"
    continue
  fi

  if grep -qi 'BucketAlreadyOwnedByYou' /tmp/create-s3-buckets.log; then
    echo "skip ${bucket} (already owned)"
    continue
  fi

  cat /tmp/create-s3-buckets.log >&2
  echo "failed to create ${bucket}" >&2
  exit 1
done
