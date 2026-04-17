# Implementation Plan: S3 Migration (MinIO → Hetzner Object Storage)

**Branch**: `034-s3-migration` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/034-s3-migration/spec.md`

## Summary

Replace the self-hosted MinIO StatefulSet with Hetzner Object Storage (S3-compatible). All services that currently talk to MinIO are updated to use a shared S3 client wrapper configured via `S3_*` environment variables instead of `MINIO_*`. No bucket names change, no object paths change, no business logic changes — this is a pure infrastructure plumbing swap.

**Key finding from codebase audit**: Python services already use `boto3` (the AWS SDK) against MinIO — the client library itself does not change. The work is (1) creating shared S3 client wrappers with the correct Hetzner-specific configuration, (2) renaming env vars, (3) removing MinIO from Helm, and (4) updating test infrastructure.

## Technical Context

**Language/Version**: Go 1.23 (`libs/pkg/s3client/`), Python 3.12 (`libs/common/s3client/`), YAML (Helm)  
**Primary Dependencies**:
- Go: `github.com/aws/aws-sdk-go-v2/service/s3` + presign subpackage, `github.com/aws/aws-sdk-go-v2/config`, `github.com/aws/aws-sdk-go-v2/credentials`
- Python: `boto3>=1.34` (already present), `aiobotocore>=2.13` (async variant), `moto[s3]>=5.0` (test mock)
- Helm: removes `minio/minio` + `minio/mc` images; adds `s3:` values block  
**Storage**: Hetzner Object Storage (S3-compatible, endpoint: `https://fsn1.your-objectstorage.com`)  
**Testing**: Go table-driven + localstack testcontainer; Python pytest + moto; E2E kind cluster + localstack  
**Target Platform**: Linux/Kubernetes (same as existing services)  
**Project Type**: Library + infrastructure configuration change  
**Performance Goals**: Presigned URL generation < 500 ms; bucket health check < 5 s at startup  
**Constraints**: Zero MinIO references in final state; backward-compatible bucket names; no functional changes  
**Scale/Scope**: 5 affected services (ml-trainer, ml-scorer, spider-workers, api-gateway, postgresql-cnpg-backup), 2 shared libraries, 1 Helm chart

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Shared clients go in `libs/pkg/` (Go) and `libs/common/` (Python) as mandated |
| II. Event-Driven Communication | ✅ N/A | No messaging changes |
| III. Country-First Data Sovereignty | ✅ PASS | Constitution §III explicitly mandates Hetzner S3; bucket names preserved |
| IV. ML-Powered Intelligence | ✅ PASS | Constitution §IV mandates S3 for model artifacts; artifact paths unchanged |
| V. Code Quality Discipline | ✅ PASS | Go: golangci-lint; Python: ruff + mypy strict; no ORM, pgx not involved |
| VI. Security & Ethical Scraping | ✅ PASS | S3 credentials injected via Kubernetes Sealed Secrets; never hardcoded |
| VII. Brownfield Kubernetes Deployment | ✅ PASS | MinIO StatefulSet removed; Hetzner S3 is an external service per §VII table |

**Migration Strategy compliance**: bucket names preserved; S3_* env vars introduced alongside MINIO_* during transition (removed at merge); no big-bang cutover.

**No violations detected.** Complexity tracking table omitted.

## Project Structure

### Documentation (this feature)

```text
specs/034-s3-migration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/           # Phase 1 output (S3 client interface contracts)
│   ├── go-s3client.md
│   └── python-s3client.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (files changed or created)

```text
libs/
├── pkg/
│   └── s3client/                          # NEW — Go shared S3 client
│       ├── client.go                      # S3Client struct + NewS3Client()
│       ├── client_test.go                 # Unit tests (mock S3)
│       └── health.go                      # HealthCheck() — bucket existence verification
└── common/
    └── s3client/                          # NEW — Python async S3 client
        ├── __init__.py
        ├── client.py                      # S3Client class (boto3 + aiobotocore)
        └── test_client.py                 # Unit tests (moto)

services/
├── ml/
│   └── estategap_ml/
│       ├── settings.py                    # MINIO_* → S3_* env vars
│       ├── trainer/
│       │   └── registry.py               # Use libs/common/s3client; update build_minio_client()
│       └── scorer/
│           └── model_registry.py          # Use libs/common/s3client; update _download_s3_object()
└── spider-workers/
    └── estategap_spiders/
        ├── settings.py                    # MINIO_* → S3_* env vars
        └── spiders/
            └── fixture_spider.py          # Use libs/common/s3client; update _client()

libs/testhelpers/
└── minio.go                              # REPLACE: StartMinIO() → StartLocalStack()

libs/common/
└── estategap_common/
    └── testing/
        └── fixtures.py                   # minio_container() → localstack_container()

helm/estategap/
├── values.yaml                           # ADD s3: block; REMOVE minio: block
├── values-staging.yaml                   # ADD s3 overrides; REMOVE minio overrides
├── values-test.yaml                      # ADD s3 overrides; REMOVE minio overrides
├── templates/
│   ├── minio.yaml                        # DELETE
│   ├── minio-setup-job.yaml              # DELETE
│   ├── configmap.yaml                    # MINIO_* → S3_* env var references
│   ├── sealed-secrets.yaml               # MINIO_* → AWS_* credential keys
│   └── postgresql-cluster.yaml           # Update backup endpoint to Hetzner S3
└── HELM_VALUES.md                        # ADD s3 section documentation

scripts/
└── create-s3-buckets.sh                  # NEW — one-time bucket provisioning script

services/ml/.env.example                  # MINIO_* → S3_* vars
services/spider-workers/.env.example      # MINIO_* → S3_* vars (if exists)
```
