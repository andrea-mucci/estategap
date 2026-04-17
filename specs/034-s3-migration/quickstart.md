# Quickstart: S3 Migration Development

**Branch**: `034-s3-migration` | **Date**: 2026-04-17

## Local Development Setup

### Prerequisites

- AWS CLI v2 (`brew install awscli` or `apt install awscli`)
- Docker (for localstack and testcontainers)
- Go 1.23, Python 3.12, uv

### Environment Variables

Copy and configure:

```bash
# services/ml/.env
S3_ENDPOINT=http://localhost:4566       # localstack (dev) or Hetzner URL (prod)
S3_REGION=us-east-1                     # localstack uses us-east-1; Hetzner uses fsn1
S3_ACCESS_KEY_ID=test                   # "test" works with localstack
S3_SECRET_ACCESS_KEY=test
S3_BUCKET_PREFIX=estategap
```

### Start localstack

```bash
docker run --rm -p 4566:4566 localstack/localstack:latest
```

### Create buckets locally

```bash
S3_ENDPOINT=http://localhost:4566 \
S3_REGION=us-east-1 \
S3_ACCESS_KEY_ID=test \
S3_SECRET_ACCESS_KEY=test \
S3_BUCKET_PREFIX=estategap \
./scripts/create-s3-buckets.sh
```

## Running Tests

### Go S3 client tests

```bash
cd libs
go test ./pkg/s3client/... -v
```

Tests use localstack testcontainer — Docker must be running.

### Python S3 client tests

```bash
cd libs/common
uv run pytest estategap_common/s3client/ -v
```

Tests use moto — no Docker needed.

### ML service tests

```bash
cd services/ml
uv run pytest tests/ -v
```

## Adding a New Service that Uses S3

### Go service

```go
import "github.com/estategap/estategap/libs/pkg/s3client"

// In main() or service init:
cfg, err := s3client.LoadConfigFromEnv()
client, err := s3client.NewS3Client(cfg)
if err := client.HealthCheck(ctx, []string{client.BucketName("my-bucket")}); err != nil {
    log.Fatal(err)
}
```

### Python service

```python
from estategap_common.s3client import S3Client, S3Config

config = S3Config()  # auto-reads S3_* env vars
async with S3Client(config) as s3:
    await s3.health_check([s3.bucket_name("my-bucket")])
```

## Provisioning Buckets (Production)

Run once per environment. Requires Hetzner S3 credentials.

```bash
export S3_ENDPOINT=https://fsn1.your-objectstorage.com
export S3_REGION=fsn1
export S3_ACCESS_KEY_ID=<hetzner-access-key>
export S3_SECRET_ACCESS_KEY=<hetzner-secret-key>
export S3_BUCKET_PREFIX=estategap

./scripts/create-s3-buckets.sh
```

## Helm Deployment

Update `values-staging.yaml` with S3 config:

```yaml
s3:
  endpoint: "https://fsn1.your-objectstorage.com"
  region: "fsn1"
  bucketPrefix: "estategap-staging"
  forcePathStyle: true
  credentials:
    secret: "estategap-s3-credentials"
```

Create the sealed secret:

```bash
kubectl create secret generic estategap-s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID=<key> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<secret> \
  --dry-run=client -o yaml | kubeseal -o yaml > helm/estategap/templates/sealed-secrets.yaml
```
