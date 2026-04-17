# Feature: MinIO → Hetzner S3-Compatible Object Storage Migration

## /specify prompt

```
Replace all MinIO object storage usage with Hetzner S3-compatible object storage. MinIO client libraries are replaced with standard AWS S3 SDK. No functional changes — same buckets, same objects, different backend.

## What

1. **Replace MinIO client libraries** with standard AWS S3 SDKs:
   - Go: replace `github.com/minio/minio-go/v7` with `github.com/aws/aws-sdk-go-v2/service/s3`
   - Python: replace `minio` package with `boto3` / `aiobotocore` (async)
   
2. **S3 client wrapper** in shared libraries:
   - Go: `pkg/s3client/` with methods: PutObject, GetObject, DeleteObject, ListObjects, PresignURL
   - Python: `libs/common/s3client/` with same async methods
   - Both configured via env vars: S3_ENDPOINT, S3_REGION, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_PREFIX

3. **Bucket provisioning** — NOT in Helm (buckets are external). Instead:
   - Document required buckets in HELM_VALUES.md
   - Startup health check in each service verifies required buckets exist (fail fast with clear error if not)
   - Script `scripts/create-s3-buckets.sh` for initial setup using AWS CLI

4. **Bucket mapping** with configurable prefix:
   - `{prefix}-ml-models` — ONNX model artifacts (MLflow, scorer)
   - `{prefix}-training-data` — ML training datasets
   - `{prefix}-listing-photos` — cached listing images
   - `{prefix}-exports` — user data exports (GDPR)
   - `{prefix}-backups` — application backups

5. **Services affected:**
   - ml-trainer: upload model artifacts after training
   - ml-scorer: download model artifacts on startup and hot-reload
   - pipeline-enricher: cache listing photos
   - api-gateway: generate presigned URLs for photo access, data export download
   - admin: upload/download backups

6. **Remove MinIO** — Delete MinIO client libraries, Helm templates, and all MinIO-specific configuration.

## Acceptance Criteria

- All 5 S3 buckets accessible from services via standard AWS SDK
- ML model upload (training) → download (scorer) works end-to-end via S3
- Presigned URLs work for photo access and data export
- Bucket health check fails fast with clear error message if bucket missing
- `scripts/create-s3-buckets.sh` creates all buckets successfully
- Zero MinIO references remaining in codebase
- All tests pass with S3 (using localstack or moto for test environments)
```
