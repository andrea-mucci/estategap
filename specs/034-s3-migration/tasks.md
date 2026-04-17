# Tasks: S3 Migration (MinIO → Hetzner Object Storage)

**Input**: Design documents from `/specs/034-s3-migration/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Test tasks are included where the research explicitly mandates test infrastructure changes (moto/localstack replacement of MinIO containers). Unit tests for new shared client libraries are required by the Constitution (§V).

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

## Path Conventions

This is a monorepo (polyglot). Paths follow the project layout:
- Go shared libs: `libs/pkg/`
- Python shared libs: `libs/common/estategap_common/`
- Go test helpers: `libs/testhelpers/`
- Services: `services/{name}/`
- Helm chart: `helm/estategap/`
- Scripts: `scripts/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency declarations and directory scaffolding for new shared S3 client libraries.

- [X] T001 Create directory `libs/pkg/s3client/` and add empty `doc.go` declaring `package s3client`
- [ ] T002 [P] Add `github.com/aws/aws-sdk-go-v2/service/s3`, `github.com/aws/aws-sdk-go-v2/config`, `github.com/aws/aws-sdk-go-v2/credentials`, and `github.com/testcontainers/testcontainers-go/modules/localstack` to `libs/go.mod` and run `go mod tidy`
- [ ] T003 [P] Create directory `libs/common/estategap_common/s3client/` and add `aiobotocore>=2.13`, `moto[s3]>=5.0` to `libs/common/pyproject.toml` (dev/test group); run `uv lock`

**Checkpoint**: Directory structure exists, dependency manifests updated.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared S3 client libraries for Go and Python. ALL user story work depends on these being complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Implement `Config`, `S3Client` struct, `NewS3Client()`, and `LoadConfigFromEnv()` in `libs/pkg/s3client/client.go` — reads `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_PREFIX`; uses `aws.EndpointResolverWithOptionsFunc` + `UsePathStyle=true`; returns error on missing/invalid config without making network calls
- [X] T005 Implement `BucketName()`, `PutObject()`, `GetObject()`, `DeleteObject()`, `ListObjects()`, `PresignGetObject()`, and `HealthCheck()` on `*S3Client` in `libs/pkg/s3client/client.go` — follow exact method signatures from `specs/034-s3-migration/contracts/go-s3client.md`; `HealthCheck` collects ALL bucket failures before returning a single aggregated error
- [X] T006 [P] Write Go unit tests in `libs/pkg/s3client/client_test.go` using a localstack testcontainer (`testcontainers-go/modules/localstack`): verify `PutObject`/`GetObject` round-trip, `HealthCheck` passes when buckets exist, `HealthCheck` returns all missing bucket names when they don't exist
- [X] T007 [P] Implement `S3Config` (Pydantic v2 `BaseSettings`), `S3Error`, and `S3HealthCheckError` in `libs/common/estategap_common/s3client/__init__.py` — reads `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_PREFIX`; `S3HealthCheckError` carries `missing_buckets: list[str]`
- [X] T008 Implement async `S3Client` class (aiobotocore-backed) and sync `SyncS3Client` class (boto3-backed) in `libs/common/estategap_common/s3client/client.py` — follow exact interface from `specs/034-s3-migration/contracts/python-s3client.md`; both classes expose `bucket_name()`, `put_object()`, `get_object()`, `delete_object()`, `list_objects()`, `presign_get_object()`, `health_check()`; `S3Client` implements async context manager
- [X] T009 [P] Write Python S3 client unit tests in `libs/common/estategap_common/s3client/test_client.py` using `moto` (`@mock_aws` decorator): verify `put_object`/`get_object` round-trip, `health_check` passes when buckets exist, `health_check` raises `S3HealthCheckError` listing all missing buckets, `presign_get_object` returns a non-empty URL string; test both sync and async clients
- [X] T010 Replace `StartMinIO()` function with `StartLocalStack()` in `libs/testhelpers/minio.go` — use `testcontainers-go/modules/localstack`; `StartLocalStack()` must return `(endpoint string, teardown func(), err error)` with the same signature contract as `StartMinIO()` so callers need no change beyond the function name
- [X] T011 [P] Replace `minio_container()` and `minio_client()` pytest fixtures with moto-based equivalents in `libs/common/estategap_common/testing/fixtures.py` — new fixtures: `s3_config()` returning `S3Config` pointing to moto mock, `s3_client()` yielding `SyncS3Client` under `@mock_aws`, `async_s3_client()` yielding `S3Client` under `@mock_aws`; remove all MinIO container imports

**Checkpoint**: `go test ./libs/pkg/s3client/...` and `uv run pytest libs/common/estategap_common/s3client/` both pass. No MinIO references remain in `libs/`.

---

## Phase 3: User Story 1 — ML Model Artifacts Flow (Priority: P1) 🎯 MVP

**Goal**: ML trainer uploads and ML scorer downloads ONNX artifacts via the shared S3 client using Hetzner Object Storage. Services fail fast at startup if required buckets are missing.

**Independent Test**: Run `uv run pytest services/ml/tests/` — all ML training and scoring tests pass with moto. Manually start the scorer with a localstack instance missing the `estategap-ml-models` bucket and confirm it exits with a non-zero code and a message listing the missing bucket.

### Implementation for User Story 1

- [X] T012 [US1] Update `services/ml/estategap_ml/settings.py` — rename all `MINIO_*` field aliases to `S3_*`: `minio_endpoint` → `s3_endpoint` (alias `S3_ENDPOINT`), `minio_access_key` → `s3_access_key_id` (alias `S3_ACCESS_KEY_ID`), `minio_secret_key` → `s3_secret_access_key` (alias `S3_SECRET_ACCESS_KEY`), `minio_bucket` → remove (bucket name derived from prefix); add `s3_bucket_prefix` (alias `S3_BUCKET_PREFIX`), `s3_region` (alias `S3_REGION`, default `"fsn1"`)
- [X] T013 [P] [US1] Refactor `build_minio_client()` in `services/ml/estategap_ml/trainer/registry.py` — replace boto3 manual client construction with `SyncS3Client(S3Config())` from `estategap_common.s3client`; update `insert_staging_version()` and all upload calls to use `client.put_object(client.bucket_name("ml-models"), key, data)`; remove direct boto3 import
- [X] T014 [P] [US1] Refactor `_download_s3_object()`, `_materialize_artifacts()`, and `ModelRegistry.__init__()` in `services/ml/estategap_ml/scorer/model_registry.py` — replace boto3 manual client with `S3Client(S3Config())`; update all `get_object()` calls to use `await client.get_object(client.bucket_name("ml-models"), key)`; remove direct boto3 import
- [X] T015 [US1] Add S3 bucket health check to ml-scorer startup in `services/ml/estategap_ml/scorer/__main__.py` — after logger init and before consuming any Kafka messages, call `await s3.health_check([s3.bucket_name("ml-models")])` and `sys.exit(1)` on `S3HealthCheckError`, logging the full error message
- [X] T016 [P] [US1] Add S3 bucket health check to ml-trainer startup (locate trainer entry point, e.g., `services/ml/estategap_ml/trainer/__main__.py` or equivalent) — check `ml-models` and `training-data` buckets; exit with non-zero code and clear error on failure
- [X] T017 [P] [US1] Update `services/ml/.env.example` — replace all `MINIO_*` vars with `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_PREFIX`; set example values pointing to localstack (`http://localhost:4566`, `us-east-1`, `test`, `test`, `estategap`)
- [X] T018 [US1] Update `services/ml/pyproject.toml` — add `aiobotocore>=2.13` to main dependencies if not already present; replace `testcontainers[minio]` with `testcontainers[localstack]` in test dependencies; ensure `moto[s3]>=5.0` is in test dependencies

**Checkpoint**: `uv run pytest services/ml/tests/` passes. Starting the scorer without the `estategap-ml-models` bucket produces a clear error and exits non-zero.

---

## Phase 4: User Story 2 — Presigned URL Access (Priority: P2)

**Goal**: Spider workers store listing photos via the shared S3 client. The API gateway generates presigned GET URLs for listing photo access and GDPR data export downloads, enabling clients to fetch objects directly from Hetzner S3 without proxying through the gateway.

**Independent Test**: Start spider-workers with localstack; confirm fixture data is read successfully. Call the presigned URL endpoint on the api-gateway and verify the returned URL is a valid pre-signed URL that downloads the target object.

### Implementation for User Story 2

- [X] T019 [US2] Update `services/spider-workers/estategap_spiders/settings.py` — rename `MINIO_*` field aliases to `S3_*` (same pattern as T012): `fixture_minio_bucket` → `fixture_s3_bucket` (alias `FIXTURE_S3_BUCKET`, default `"fixtures"`); add `s3_bucket_prefix` (alias `S3_BUCKET_PREFIX`)
- [X] T020 [P] [US2] Refactor `_client()` and `_read_fixture_payload()` in `services/spider-workers/estategap_spiders/spiders/fixture_spider.py` — replace inline boto3 client construction with `SyncS3Client(S3Config())` from `estategap_common.s3client`; update `get_object()` calls accordingly; remove direct boto3 import
- [X] T021 [P] [US2] Update `services/spider-workers/pyproject.toml` — ensure `aiobotocore>=2.13` present; replace any `testcontainers[minio]` with `testcontainers[localstack]`; ensure `moto[s3]>=5.0` in test dependencies
- [X] T022 [US2] Add S3 client configuration to the api-gateway service — locate the api-gateway config module (e.g., `services/api-gateway/internal/config/config.go`) and add S3 config fields reading `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_PREFIX` via viper; initialize a `*s3client.S3Client` in the service's dependency graph
- [X] T023 [US2] Implement presigned URL generation for listing photos in api-gateway — add handler (e.g., `services/api-gateway/internal/handler/photos.go`) that calls `s3Client.PresignGetObject(ctx, s3Client.BucketName("listing-photos"), key, 1*time.Hour)` and returns the URL to the caller; wire the route in the existing chi router
- [X] T024 [P] [US2] Implement presigned URL generation for GDPR data exports in api-gateway — add handler (e.g., `services/api-gateway/internal/handler/exports.go`) that generates a presigned URL for the user's export archive in the `exports` bucket; wire the route in the existing chi router
- [X] T025 [P] [US2] Update spider-workers `.env.example` (if it exists, otherwise create it) — same `S3_*` variables as T017 plus `FIXTURE_S3_BUCKET=fixtures`

**Checkpoint**: Spider-workers reads fixture data from localstack. API gateway returns a non-empty presigned URL string for a valid object key.

---

## Phase 5: User Story 3 — Bucket Health Check at Service Startup (Priority: P3)

**Goal**: Every service that uses S3 verifies its required buckets exist at startup and exits immediately with a human-readable error listing all missing buckets. No service fails silently on a missing bucket.

**Independent Test**: For each service, start it pointed at a localstack instance with zero buckets provisioned. Verify exit code is non-zero and log output names the missing buckets.

### Implementation for User Story 3

- [X] T026 [US3] Add S3 health check to spider-workers startup — locate the entry point (e.g., `services/spider-workers/estategap_spiders/__main__.py`); add `s3.health_check([s3.bucket_name("listing-photos"), s3.bucket_name("fixtures")])` call before the Scrapy crawler starts; exit with `sys.exit(1)` on `S3HealthCheckError`
- [X] T027 [US3] Add S3 health check to api-gateway startup — in the api-gateway `main.go` or server initialization, call `s3Client.HealthCheck(ctx, []string{s3Client.BucketName("listing-photos"), s3Client.BucketName("exports")})` before binding to the HTTP port; log the error and exit non-zero on failure
- [X] T028 [P] [US3] Verify all health check error messages follow the format `"S3 health check failed: missing buckets: [bucket1, bucket2]"` — grep across all service entry points and adjust log statements to be consistent; verify exit code is non-zero (`os.Exit(1)` in Go, `sys.exit(1)` in Python)

**Checkpoint**: Each service, when started with missing buckets, exits non-zero within 3 seconds and logs all missing bucket names in a single message.

---

## Phase 6: Helm & Infrastructure Cleanup

**Purpose**: Remove MinIO from Kubernetes deployment; wire Hetzner S3 via Helm values. This phase is largely independent of Phase 3–5 and can be worked in parallel with them.

- [X] T029 [P] Delete `helm/estategap/templates/minio.yaml` (MinIO StatefulSet + Services)
- [X] T030 [P] Delete `helm/estategap/templates/minio-setup-job.yaml` (bucket setup Job using `minio/mc`)
- [X] T031 Add `s3:` block to `helm/estategap/values.yaml` — replace the removed `minio:` block with the schema from `specs/034-s3-migration/data-model.md`; add comments on every field; keep the file valid YAML after the change
- [X] T032 [P] Update `helm/estategap/values-staging.yaml` — remove `minio:` overrides; add `s3:` overrides (`bucketPrefix: "estategap-staging"`, retain endpoint/region/credentials ref)
- [X] T033 [P] Update `helm/estategap/values-test.yaml` — remove `minio:` overrides; add `s3:` overrides pointing to localstack (`endpoint: "http://localstack:4566"`, `region: "us-east-1"`, `bucketPrefix: "test"`)
- [X] T034 Update `helm/estategap/templates/configmap.yaml` — replace all `MINIO_*` env vars with `S3_*` equivalents (`S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID` from secret ref, `S3_SECRET_ACCESS_KEY` from secret ref, `S3_BUCKET_PREFIX`); remove any hardcoded `http://minio.estategap-system.svc.cluster.local:9000` references
- [X] T035 [P] Update `helm/estategap/templates/sealed-secrets.yaml` — replace `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` and service-specific MinIO credential keys with `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from secret `estategap-s3-credentials`
- [X] T036 [P] Update `helm/estategap/templates/postgresql-cluster.yaml` — change CNPG backup endpoint from `http://minio.estategap-system.svc.cluster.local:9000` to `{{ .Values.s3.endpoint }}`; update credentials secret reference to `estategap-s3-credentials` with keys `ACCESS_KEY_ID` and `ACCESS_SECRET_KEY` as required by CNPG
- [X] T037 [P] Create or update `helm/estategap/HELM_VALUES.md` — add an `## S3 Object Storage` section documenting every field in the `s3:` block (endpoint, region, bucketPrefix, forcePathStyle, credentials.secret, buckets.*) with type, default, and description; remove the MinIO section if it exists
- [X] T038 Create `scripts/create-s3-buckets.sh` — bash script using the AWS CLI that: reads `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_PREFIX` from env; creates `{prefix}-ml-models`, `{prefix}-training-data`, `{prefix}-listing-photos`, `{prefix}-exports`, `{prefix}-backups` idempotently (`aws s3 mb --endpoint-url $S3_ENDPOINT` ignoring "BucketAlreadyOwnedByYou" errors); prints success/skip status per bucket; exits non-zero if any bucket creation fails

**Checkpoint**: `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml` passes with zero warnings. No MinIO image references remain in Helm templates.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final zero-MinIO audit, smoke test update, documentation.

- [X] T039 Audit entire codebase for remaining MinIO references — run `grep -ri "minio" --include="*.go" --include="*.py" --include="*.yaml" --include="*.toml" --include="*.mod" --include="*.sh" .`; fix any occurrences not yet addressed by previous tasks; confirm zero matches in production code (test files may reference localstack/moto but not MinIO)
- [X] T040 [P] Update `scripts/smoke-test.sh` — replace the MinIO health check section (lines ~10, 42–48) that uses `minio/mc` with an AWS CLI check: `aws s3 ls --endpoint-url $S3_ENDPOINT s3://{prefix}-ml-models` to verify bucket accessibility; update credential retrieval to read from `estategap-s3-credentials` Kubernetes secret instead of MinIO secret
- [ ] T041 [P] Run `helm template estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml` and confirm no MinIO StatefulSet, Job, or Service appears in the output; confirm the S3 env vars appear in the rendered ConfigMap
- [ ] T042 Run full test suite — `cd libs && go test ./...`; `cd libs/common && uv run pytest`; `cd services/ml && uv run pytest`; `cd services/spider-workers && uv run pytest` — all must pass; commit the branch

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS** all user story phases (3, 4, 5)
- **Phase 3 (US1)**: Depends on Phase 2 completion
- **Phase 4 (US2)**: Depends on Phase 2 completion — independent of Phase 3
- **Phase 5 (US3)**: Depends on Phase 2 completion — independent of Phases 3 and 4
- **Phase 6 (Helm)**: Independent — can run in parallel with Phases 2–5 (different files)
- **Phase 7 (Polish)**: Depends on all phases complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependency on US2 or US3
- **US2 (P2)**: Can start after Phase 2 — no dependency on US1 or US3
- **US3 (P3)**: Can start after Phase 2 — largely covered within US1 and US2; remaining tasks (T026–T028) depend on US1/US2 patterns being established

### Within Each User Story

- Config/settings update first (T012, T019)
- Service refactor in parallel once config is done (T013+T014, T020+T021)
- Startup health check after service refactor (T015, T016, T026, T027)
- Dependency manifest update can run in parallel with service refactor (T018, T021)

---

## Parallel Example: Phase 2 (Foundational)

```text
# Can launch concurrently after Phase 1:
Task T004: Implement Go S3Client in libs/pkg/s3client/client.go
Task T007: Implement Python S3Config in libs/common/estategap_common/s3client/__init__.py

# After T004+T005 complete, T006 can run:
Task T006: Write Go unit tests in libs/pkg/s3client/client_test.go

# After T007+T008 complete, T009 can run:
Task T009: Write Python unit tests in libs/common/estategap_common/s3client/test_client.py

# Fully independent — run any time in Phase 2:
Task T010: Replace StartMinIO() in libs/testhelpers/minio.go
Task T011: Replace minio_container() in libs/common/estategap_common/testing/fixtures.py
```

## Parallel Example: Phase 6 (Helm Cleanup)

```text
# All independent — launch together:
Task T029: Delete helm/estategap/templates/minio.yaml
Task T030: Delete helm/estategap/templates/minio-setup-job.yaml
Task T032: Update helm/estategap/values-staging.yaml
Task T033: Update helm/estategap/values-test.yaml
Task T035: Update helm/estategap/templates/sealed-secrets.yaml
Task T036: Update helm/estategap/templates/postgresql-cluster.yaml
Task T037: Update helm/estategap/HELM_VALUES.md

# After T029+T030, then do:
Task T031: Update helm/estategap/values.yaml (references removed templates)
Task T034: Update helm/estategap/templates/configmap.yaml
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T011) — **critical gate**
3. Complete Phase 3: US1 ML Model Artifacts (T012–T018)
4. **STOP and VALIDATE**: Run `uv run pytest services/ml/tests/`; manually verify trainer → scorer artifact flow
5. Ship Phase 6 (Helm) in parallel with Phase 3 if a second developer is available

### Incremental Delivery

1. Phase 1 + Phase 2 → Shared S3 libraries ready for all consumers
2. Phase 3 (US1) → ML pipeline fully migrated — demo trainer/scorer with Hetzner S3
3. Phase 4 (US2) → Spider-workers + api-gateway presigned URLs working
4. Phase 5 (US3) → All services fail-fast with clear bucket errors
5. Phase 6 (Helm) → MinIO removed from Kubernetes deployment
6. Phase 7 (Polish) → Zero MinIO references confirmed

### Parallel Team Strategy

With two developers after Phase 2 is complete:
- Developer A: Phases 3 + 5 (Python ML services + health checks)
- Developer B: Phase 4 + Phase 6 (spider-workers, api-gateway, Helm cleanup)

---

## Notes

- [P] tasks = different files, no unresolved dependencies on incomplete tasks in same phase
- [US*] label maps tasks to user stories for traceability
- **moto** is used for Python tests (in-process, no Docker); **localstack** for Go tests (HTTP server via testcontainer)
- `libs/testhelpers/minio.go` → `StartLocalStack()` must preserve the same return signature to minimize calling-code changes
- Phase 6 (Helm) is safe to work in parallel with all user story phases since it touches a completely separate file tree
- After T039 zero-MinIO audit, commit immediately with message referencing SC-006 from spec.md
