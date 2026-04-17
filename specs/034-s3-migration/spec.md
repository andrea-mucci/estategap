# Feature Specification: S3 Migration (MinIO → Hetzner Object Storage)

**Feature Branch**: `034-s3-migration`  
**Created**: 2026-04-17  
**Status**: Draft  

## User Scenarios & Testing *(mandatory)*

### User Story 1 — ML Model Artifacts Flow (Priority: P1)

The ML trainer uploads trained ONNX model artifacts to object storage after each training run. The ML scorer downloads those artifacts at startup and hot-reloads them when new versions become available. This flow must work identically after migration — same bucket names, same object paths, different storage backend.

**Why this priority**: The ML pipeline is the most latency-sensitive object-storage user. If model artifacts cannot be retrieved at scorer startup, the service crashes and deal-scoring goes offline.

**Independent Test**: Train a model with the trainer service, verify artifacts appear in the configured S3 bucket under the expected path, then start the scorer and confirm it loads the model successfully.

**Acceptance Scenarios**:

1. **Given** a completed ML training run, **When** the trainer publishes a new model version, **Then** the ONNX artifact and feature-engineer file are accessible in the `{prefix}-ml-models` bucket under the expected key prefix.
2. **Given** a new model version exists in the bucket, **When** the scorer performs a hot-reload check, **Then** it downloads and activates the new model within 60 seconds without service restart.
3. **Given** the `{prefix}-ml-models` bucket does not exist, **When** either service starts, **Then** it exits immediately with a clear error message naming the missing bucket.

---

### User Story 2 — Presigned URL Access (Priority: P2)

The API gateway generates time-limited presigned URLs so frontend clients can access listing photos and GDPR data-export files directly from object storage without proxying the data through the gateway.

**Why this priority**: Presigned URLs are the mechanism for serving listing photos on the frontend. Without them, photo access is broken for end users.

**Independent Test**: Request a presigned URL from the API gateway for a known object key; fetch the object using only the returned URL (no auth header) and verify the content is returned correctly.

**Acceptance Scenarios**:

1. **Given** a listing photo exists in the `{prefix}-listing-photos` bucket, **When** the API gateway is asked for a presigned URL with a 1-hour expiry, **Then** an unauthenticated HTTP GET to that URL returns the photo within the expiry window.
2. **Given** a GDPR export file exists in the `{prefix}-exports` bucket, **When** the API gateway generates a presigned download URL, **Then** the user can download the file without additional authentication.
3. **Given** a presigned URL has expired, **When** a client attempts to use it, **Then** the request is rejected with an appropriate access-denied error.

---

### User Story 3 — Bucket Health Check at Service Startup (Priority: P3)

Each service that uses object storage verifies that its required buckets exist before accepting traffic. If a bucket is missing, the service exits with a clear, actionable error message rather than failing silently at the first read/write.

**Why this priority**: Fail-fast prevents hard-to-debug runtime failures. Operators need an obvious signal when a bucket is missing.

**Independent Test**: Start a service with an S3 endpoint that has no buckets provisioned; confirm the service exits with a non-zero code and logs a message that names every missing bucket.

**Acceptance Scenarios**:

1. **Given** all required buckets exist, **When** a service starts, **Then** the health check passes and the service begins processing normally.
2. **Given** one or more required buckets are missing, **When** a service starts, **Then** it logs an error that lists each missing bucket by full name and exits with a non-zero status code.
3. **Given** the S3 endpoint is unreachable, **When** a service starts, **Then** it exits with a connectivity error that includes the configured endpoint URL.

---

### Edge Cases

- What happens when the S3 endpoint returns a transient 5xx error during object upload? The client retries with exponential back-off; after max retries, propagates the error to the caller.
- What happens when a presigned URL is generated for a key that does not exist? The URL is returned (S3 signs the request); the downstream fetch returns 404.
- What happens if the bucket prefix is empty? The service exits at startup with a configuration validation error.
- What happens during a hot-reload if the new artifact download fails midway? The scorer continues using the previously loaded model; the failed reload is logged and retried on the next cycle.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a shared Go S3 client in `libs/pkg/s3client/` with methods: PutObject, GetObject, DeleteObject, ListObjects, PresignGetObject, HealthCheck, and BucketName (prefix resolution).
- **FR-002**: System MUST provide a shared Python async S3 client in `libs/common/s3client/` with equivalent methods using `boto3` / `aiobotocore`.
- **FR-003**: Both clients MUST be configurable via environment variables: `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_PREFIX`.
- **FR-004**: Both clients MUST support path-style addressing (required by Hetzner Object Storage).
- **FR-005**: The Go client MUST support presigned GET URLs with configurable expiry duration.
- **FR-006**: Every service that uses object storage MUST run a bucket health check at startup and fail fast if required buckets are absent.
- **FR-007**: The `scripts/create-s3-buckets.sh` script MUST create all five buckets using the AWS CLI and the same `S3_*` environment variables.
- **FR-008**: Helm values MUST expose an `s3` section replacing the `minio` section, with fields for endpoint, region, bucketPrefix, forcePathStyle, credentials secret reference, and bucket name overrides.
- **FR-009**: All MinIO Helm templates (`minio.yaml`, `minio-setup-job.yaml`) MUST be removed. No MinIO StatefulSet or setup Job may remain in the chart.
- **FR-010**: Sealed-secrets MUST be updated to reference S3 credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) instead of MinIO credentials.
- **FR-011**: The PostgreSQL CNPG backup destination MUST be updated to reference the Hetzner S3 endpoint instead of the in-cluster MinIO service.
- **FR-012**: Test infrastructure MUST replace MinIO containers with `moto` (Python unit/integration tests) or localstack (Go integration and kind e2e tests). No real Hetzner endpoints are called during tests.
- **FR-013**: Zero MinIO references MUST remain in production code, Helm templates, configuration files, or dependency manifests after migration.

### Key Entities

- **S3 Client Configuration**: endpoint URL, region, access key ID, secret access key, bucket prefix, path-style flag.
- **Bucket**: logical storage container identified by `{prefix}-{name}`. Fixed set of five: `ml-models`, `training-data`, `listing-photos`, `exports`, `backups`.
- **Object**: stored blob identified by bucket + key. Keys preserve their existing MinIO-era structure unchanged.
- **Presigned URL**: time-limited, unauthenticated download URL generated by the S3 client.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five buckets are accessible from all affected services within 5 seconds of service startup.
- **SC-002**: ML model upload (trainer) → download (scorer) round-trip completes within 30 seconds on the test cluster.
- **SC-003**: Presigned URLs for listing photos are generated in under 500 ms and remain valid for the configured expiry period.
- **SC-004**: Services exit within 3 seconds of startup with a human-readable error when a required bucket is absent.
- **SC-005**: `scripts/create-s3-buckets.sh` creates all five buckets idempotently in under 60 seconds.
- **SC-006**: Zero occurrences of the strings `minio`, `MINIO`, `MinIO` remain in production source files, Helm templates, or dependency manifests after the migration PR is merged.
- **SC-007**: All existing test suites pass with the S3 mock backend substituted for MinIO containers.

## Assumptions

- The Hetzner Object Storage endpoint and credentials are available as Kubernetes Sealed Secrets before the Helm chart is deployed.
- Bucket names remain identical to their legacy MinIO names (no rename); only the backend changes.
- The `S3_BUCKET_PREFIX` is set to `"estategap"` in all environments, matching the legacy MinIO bucket structure.
- The `minio` Python package was never used in production code — boto3 was the existing client library; only the configuration (env var names, endpoint) changes.
- PostgreSQL CNPG backups to S3 are handled via the CNPG S3 backup configuration; no application-layer backup code is written.
- The `scripts/create-s3-buckets.sh` script is a one-time operator tool; it is not run by Helm or CI.
- Test environments (kind, CI) use localstack or moto for S3 simulation; real Hetzner credentials are never required in automated tests.
