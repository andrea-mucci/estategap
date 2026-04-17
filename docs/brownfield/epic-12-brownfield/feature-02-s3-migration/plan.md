# Feature: MinIO → Hetzner S3-Compatible Object Storage Migration

## /plan prompt

```
Implement the S3 migration with these technical decisions:

## Go S3 Client (pkg/s3client/)

```go
type Config struct {
    Endpoint     string // "https://fsn1.your-objectstorage.com"
    Region       string // "fsn1"
    AccessKeyID  string
    SecretKey    string
    BucketPrefix string // "estategap"
    ForcePathStyle bool // true for Hetzner (not virtual-hosted)
}

type S3Client struct {
    client *s3.Client
    config Config
}

func NewS3Client(cfg Config) (*S3Client, error) {
    resolver := aws.EndpointResolverWithOptionsFunc(
        func(service, region string, options ...interface{}) (aws.Endpoint, error) {
            return aws.Endpoint{URL: cfg.Endpoint}, nil
        },
    )
    awsCfg, err := config.LoadDefaultConfig(context.TODO(),
        config.WithRegion(cfg.Region),
        config.WithEndpointResolverWithOptions(resolver),
        config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(
            cfg.AccessKeyID, cfg.SecretKey, "",
        )),
    )
    client := s3.NewFromConfig(awsCfg, func(o *s3.Options) {
        o.UsePathStyle = cfg.ForcePathStyle
    })
    return &S3Client{client: client, config: cfg}, nil
}

func (c *S3Client) BucketName(name string) string {
    return fmt.Sprintf("%s-%s", c.config.BucketPrefix, name)
}

func (c *S3Client) PutObject(ctx context.Context, bucket, key string, body io.Reader) error { ... }
func (c *S3Client) GetObject(ctx context.Context, bucket, key string) (io.ReadCloser, error) { ... }
func (c *S3Client) PresignGetObject(ctx context.Context, bucket, key string, expiry time.Duration) (string, error) { ... }
func (c *S3Client) HealthCheck(ctx context.Context, requiredBuckets []string) error { ... }
```

## Python S3 Client (libs/common/s3client/)

```python
import aiobotocore
from aiobotocore.session import AioSession

class S3Client:
    def __init__(self, config: S3Config):
        self.config = config
        self.session = AioSession()
    
    def bucket_name(self, name: str) -> str:
        return f"{self.config.bucket_prefix}-{name}"
    
    async def put_object(self, bucket: str, key: str, body: bytes) -> None:
        async with self.session.create_client(
            's3',
            endpoint_url=self.config.endpoint,
            region_name=self.config.region,
            aws_access_key_id=self.config.access_key_id,
            aws_secret_access_key=self.config.secret_key,
        ) as client:
            await client.put_object(
                Bucket=self.bucket_name(bucket),
                Key=key,
                Body=body,
            )
    
    async def health_check(self, required_buckets: list[str]) -> None:
        "Fail fast if any required bucket is missing."
        ...
```

## Helm Values — S3 Section

```yaml
s3:
  endpoint: "https://fsn1.your-objectstorage.com"
  region: "fsn1"
  bucketPrefix: "estategap"
  forcePathStyle: true
  credentials:
    secret: "estategap-s3-credentials"    # Must contain AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    # OR inline (not recommended for production):
    # accessKeyId: ""
    # secretAccessKey: ""
  buckets:
    mlModels: "ml-models"
    trainingData: "training-data"
    listingPhotos: "listing-photos"
    exports: "exports"
    backups: "backups"
```

## Bucket Setup Script (scripts/create-s3-buckets.sh)

```bash
#!/bin/bash
set -euo pipefail
PREFIX="${S3_BUCKET_PREFIX:-estategap}"
ENDPOINT="${S3_ENDPOINT:?Required}"
for BUCKET in ml-models training-data listing-photos exports backups; do
    aws s3 mb "s3://${PREFIX}-${BUCKET}" --endpoint-url "$ENDPOINT" 2>/dev/null || echo "Bucket ${PREFIX}-${BUCKET} already exists"
done
echo "All buckets ready."
```

## Test Strategy

- Unit tests: mock S3Client interface
- Integration tests: use `moto` (Python) or `localstack` container for real S3 API simulation
- E2E tests on kind: deploy localstack in kind cluster as S3 mock
- No real Hetzner calls in tests

## Service Migration

1. Create `pkg/s3client/` (Go) and `libs/common/s3client/` (Python)
2. Replace MinIO imports in each service (search for `minio-go` and `from minio`)
3. Update config modules to read S3 env vars
4. Update Helm ConfigMap to inject S3 env vars from values
5. Delete MinIO Helm template and dependencies
6. Remove `minio-go` from go.mod, `minio` from pyproject.toml
```
