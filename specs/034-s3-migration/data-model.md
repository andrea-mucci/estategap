# Data Model: S3 Migration

**Branch**: `034-s3-migration` | **Date**: 2026-04-17

> This migration introduces no new database tables or schema changes. The data model described here is the shared S3 client configuration model used across all services.

## S3 Configuration

### Go — `pkg/s3client.Config`

```go
type Config struct {
    Endpoint       string // "https://fsn1.your-objectstorage.com"
    Region         string // "fsn1"
    AccessKeyID    string
    SecretKey      string
    BucketPrefix   string // "estategap" — prepended to all logical bucket names
    ForcePathStyle bool   // true — required by Hetzner (no DNS wildcard)
}
```

**Validation rules**:
- `Endpoint` MUST be non-empty and a valid HTTPS URL
- `AccessKeyID` and `SecretKey` MUST be non-empty
- `BucketPrefix` MUST be non-empty (prevents unnamed buckets)
- `Region` defaults to `"fsn1"` if empty

### Python — `s3client.S3Config` (Pydantic v2)

```python
class S3Config(BaseSettings):
    s3_endpoint: str          = Field(alias="S3_ENDPOINT")
    s3_region: str            = Field(default="fsn1", alias="S3_REGION")
    s3_access_key_id: str     = Field(alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(alias="S3_SECRET_ACCESS_KEY")
    s3_bucket_prefix: str     = Field(alias="S3_BUCKET_PREFIX")
```

## Bucket Registry

Fixed set of five logical buckets. Physical name = `{bucket_prefix}-{logical_name}`.

| Logical Name    | Physical Name (prefix=estategap) | Owner Services              | Contents                         |
|-----------------|----------------------------------|-----------------------------|----------------------------------|
| `ml-models`     | `estategap-ml-models`            | ml-trainer (write), ml-scorer (read) | ONNX files, feature engineers |
| `training-data` | `estategap-training-data`        | ml-trainer (write/read)     | Training datasets                |
| `listing-photos`| `estategap-listing-photos`       | spider-workers (write), api-gateway (presign) | Cached property photos |
| `exports`       | `estategap-exports`              | api-gateway (write/presign) | GDPR data export archives        |
| `backups`       | `estategap-backups`              | CNPG (write)                | PostgreSQL WAL + base backups    |

## Object Key Conventions

Key structure is unchanged from the MinIO era:

| Bucket          | Key Pattern                                    | Example |
|-----------------|------------------------------------------------|---------|
| `ml-models`     | `{country}/{model_version}/{artifact}.onnx`    | `fr/v42/model.onnx` |
| `ml-models`     | `{country}/{model_version}/feature_engineer.pkl` | `fr/v42/feature_engineer.pkl` |
| `training-data` | `{country}/{date}/{filename}.parquet`          | `fr/2026-04-17/listings.parquet` |
| `listing-photos`| `{country}/{listing_id}/{index}.jpg`           | `fr/abc123/0.jpg` |
| `exports`       | `{user_id}/{export_id}.zip`                    | `user-42/export-2026-04-17.zip` |
| `backups`       | Managed by CNPG                                | — |

## State Transitions

Object lifecycle is unchanged from MinIO. No new state transitions are introduced.

## Helm Values Schema

```yaml
# New s3: block replaces minio: block
s3:
  endpoint: "https://fsn1.your-objectstorage.com"  # Hetzner S3 endpoint
  region: "fsn1"                                     # Hetzner datacenter region
  bucketPrefix: "estategap"                          # Prefix for all bucket names
  forcePathStyle: true                               # Required for Hetzner
  credentials:
    secret: "estategap-s3-credentials"              # K8s Secret with AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
  buckets:
    mlModels: "ml-models"                            # Logical name suffix
    trainingData: "training-data"
    listingPhotos: "listing-photos"
    exports: "exports"
    backups: "backups"
```

## Kubernetes Secret Schema

Secret name: `estategap-s3-credentials`

| Key                   | Description                   |
|-----------------------|-------------------------------|
| `AWS_ACCESS_KEY_ID`   | Hetzner S3 access key         |
| `AWS_SECRET_ACCESS_KEY` | Hetzner S3 secret key       |
