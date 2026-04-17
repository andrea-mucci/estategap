# Research: S3 Migration (MinIO → Hetzner Object Storage)

**Branch**: `034-s3-migration` | **Date**: 2026-04-17

## Decision Log

### D-001: Go S3 SDK — aws-sdk-go-v2 vs. minio-go

**Decision**: Use `github.com/aws/aws-sdk-go-v2/service/s3`  
**Rationale**: The user's technical spec explicitly mandates aws-sdk-go-v2. It is the official AWS Go SDK (v1 is maintenance-only), supports custom endpoints for S3-compatible stores, and aligns with the existing Python boto3 usage. Hetzner Object Storage is S3-compatible and works with the standard SDK.  
**Alternatives considered**:
- `minio-go` — current (to be removed); MinIO-specific, violates constitution §III
- `gocloud.dev/blob` — too high-level; hides path-style vs. virtual-hosted distinction needed for Hetzner

### D-002: Python S3 Client — boto3 vs. aiobotocore

**Decision**: Use `boto3` for synchronous calls and `aiobotocore` for async contexts  
**Rationale**: Python services already use boto3 against MinIO — no client library change required. The shared `libs/common/s3client/` wrapper accepts either a boto3 or aiobotocore session so callers pick the right flavour for their event loop. aiobotocore wraps botocore with asyncio support and is the standard async S3 client in the Python ecosystem.  
**Alternatives considered**:
- `s3transfer` — lower-level; boto3 already uses it internally
- `aiofiles` + `httpx` — would require re-implementing S3 protocol; not viable

### D-003: Path-Style vs. Virtual-Hosted Addressing

**Decision**: `ForcePathStyle = true` in Go, `addressing_style="path"` in Python  
**Rationale**: Hetzner Object Storage requires path-style addressing (`endpoint/bucket/key`) rather than virtual-hosted style (`bucket.endpoint/key`). The DNS wildcard needed for virtual-hosted style is not available on Hetzner. Both aws-sdk-go-v2 and boto3 support this via a single configuration flag.  
**Alternatives considered**: virtual-hosted style — not compatible with Hetzner's DNS setup.

### D-004: Endpoint Resolver — aws-sdk-go-v2

**Decision**: Use `aws.EndpointResolverWithOptionsFunc` as shown in the user spec  
**Rationale**: This is the v2 mechanism for overriding endpoints on a per-service basis. It injects the Hetzner endpoint URL while preserving all other SDK behaviour.  
**Note**: aws-sdk-go-v2 ≥ 1.28 introduced `BaseEndpoint` on `s3.Options` as the preferred approach. If the project upgrades past that version, migrate to `BaseEndpoint`. For now, `EndpointResolverWithOptions` is correct.

### D-005: Presigned URLs

**Decision**: Use `s3.NewPresignClient()` from `github.com/aws/aws-sdk-go-v2/service/s3` (Go); `generate_presigned_url()` from boto3 (Python)  
**Rationale**: Both SDKs generate standard S3 pre-signed URLs. Hetzner S3 honours them. The signature version is SigV4, which Hetzner requires.  
**Constraint**: Presigned URL expiry must be ≤ 7 days (Hetzner limit, same as AWS).

### D-006: Test Infrastructure — moto vs. localstack

**Decision**: `moto[s3]` for Python unit/integration tests; localstack container for Go integration tests and kind e2e  
**Rationale**: moto intercepts boto3/botocore calls in-process — no container needed, zero network latency, ideal for unit and integration tests. localstack provides a full S3-compatible HTTP server, making it suitable for Go SDK tests (which can't be intercepted in-process) and kind cluster e2e tests.  
**Alternatives considered**:
- localstack for everything — works, but adds container startup overhead to Python unit tests
- fake-s3 — less maintained, moto is the de-facto standard

### D-007: Bucket Health Check Strategy

**Decision**: On startup, call `HeadBucket` for each required bucket; collect all failures before returning a single aggregated error  
**Rationale**: `HeadBucket` is cheap (HEAD request, no data transfer). Collecting all failures before aborting gives operators a complete list in a single startup failure, not one bucket at a time.  
**Implementation**: In Go, `(*s3.Client).HeadBucket`; in Python, `client.head_bucket()`. Wrap in the `HealthCheck(ctx, buckets []string)` method.

### D-008: CNPG Backup Endpoint Update

**Decision**: Update `helm/estategap/templates/postgresql-cluster.yaml` backup endpoint from `http://minio.estategap-system.svc.cluster.local:9000` to the Hetzner S3 endpoint via Helm values  
**Rationale**: CNPG's S3 backup plugin uses standard S3 semantics; it works with any S3-compatible endpoint. The backup bucket (`{prefix}-backups`) must be pre-created via `create-s3-buckets.sh`.  
**Constraint**: CNPG requires the backup secret to contain `ACCESS_KEY_ID` and `ACCESS_SECRET_KEY` keys — map from the `estategap-s3-credentials` Kubernetes Secret accordingly.

### D-009: Testhelpers — minio.go Replacement

**Decision**: Replace `libs/testhelpers/minio.go`'s `StartMinIO()` with `StartLocalStack()` using the `testcontainers-go` localstack module  
**Rationale**: localstack provides a drop-in S3-compatible endpoint that works with the standard aws-sdk-go-v2 client. No change to calling code is needed beyond the URL returned by `StartLocalStack()`.  
**Module**: `github.com/testcontainers/testcontainers-go/modules/localstack`

### D-010: Env Var Naming

**Decision**: New names: `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_PREFIX`  
**Rationale**: Standard naming convention (AWS-style) rather than MinIO-specific names. All five vars are uniform across Go and Python services.  
**Old → New mapping**:
- `MINIO_ENDPOINT` → `S3_ENDPOINT`
- `MINIO_ACCESS_KEY` → `S3_ACCESS_KEY_ID`
- `MINIO_SECRET_KEY` → `S3_SECRET_ACCESS_KEY`
- `MINIO_BUCKET` → derived from `S3_BUCKET_PREFIX` + logical bucket name
- No old equivalent → `S3_REGION` (new; set to `"fsn1"` for Hetzner FSN1)

## Open Questions (all resolved)

All NEEDS CLARIFICATION items from the spec were resolved via codebase audit and the user's explicit technical decisions. No open questions remain.
