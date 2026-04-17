# Contract: Go S3 Client (`libs/pkg/s3client`)

**Branch**: `034-s3-migration` | **Date**: 2026-04-17

## Package

```go
package s3client // import "github.com/estategap/estategap/libs/pkg/s3client"
```

## Interface

```go
// S3Operations is the interface that all callers depend on.
// Use this for mocking in tests.
type S3Operations interface {
    BucketName(logical string) string
    PutObject(ctx context.Context, bucket, key string, body io.Reader, size int64) error
    GetObject(ctx context.Context, bucket, key string) (io.ReadCloser, error)
    DeleteObject(ctx context.Context, bucket, key string) error
    ListObjects(ctx context.Context, bucket, prefix string) ([]string, error)
    PresignGetObject(ctx context.Context, bucket, key string, expiry time.Duration) (string, error)
    HealthCheck(ctx context.Context, requiredBuckets []string) error
}
```

## Constructor

```go
func NewS3Client(cfg Config) (*S3Client, error)
```

Returns an error only if the configuration is invalid (empty endpoint, missing keys). Does not make a network call. The `HealthCheck` method is the network-hitting gate.

## Method Contracts

### BucketName

```go
func (c *S3Client) BucketName(logical string) string
// Returns: fmt.Sprintf("%s-%s", c.config.BucketPrefix, logical)
// Example: BucketName("ml-models") → "estategap-ml-models"
// Panics: never
```

### PutObject

```go
func (c *S3Client) PutObject(ctx context.Context, bucket, key string, body io.Reader, size int64) error
// bucket: full physical bucket name (use BucketName() to resolve)
// size: content length in bytes (-1 if unknown — SDK buffers internally)
// Returns: nil on success; wrapped AWS error on failure
// Does NOT close body
```

### GetObject

```go
func (c *S3Client) GetObject(ctx context.Context, bucket, key string) (io.ReadCloser, error)
// Returns: ReadCloser — CALLER MUST CLOSE
// Returns: nil, err if object not found or network error
```

### DeleteObject

```go
func (c *S3Client) DeleteObject(ctx context.Context, bucket, key string) error
// Idempotent — deleting a non-existent key returns nil (S3 semantics)
```

### ListObjects

```go
func (c *S3Client) ListObjects(ctx context.Context, bucket, prefix string) ([]string, error)
// Returns: slice of object keys matching the prefix (empty slice if none)
// prefix: "" lists all objects in bucket
// Handles pagination internally (up to 10,000 objects per call is sufficient for current scale)
```

### PresignGetObject

```go
func (c *S3Client) PresignGetObject(ctx context.Context, bucket, key string, expiry time.Duration) (string, error)
// expiry: must be > 0 and ≤ 7*24*time.Hour (Hetzner limit)
// Returns: pre-signed HTTPS URL valid for expiry duration
// Does NOT verify the object exists — signs the request regardless
```

### HealthCheck

```go
func (c *S3Client) HealthCheck(ctx context.Context, requiredBuckets []string) error
// Calls HeadBucket for each bucket in requiredBuckets
// Collects ALL failures before returning
// Returns: nil if all buckets exist and are accessible
// Returns: error listing every missing/inaccessible bucket by name
// Format: "S3 health check failed: missing buckets: [estategap-ml-models, estategap-exports]"
```

## Configuration from Environment

```go
// LoadConfigFromEnv reads S3_* environment variables.
func LoadConfigFromEnv() (Config, error)
// Reads: S3_ENDPOINT, S3_REGION, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_PREFIX
// Returns error if any required var is missing or Endpoint is not a valid URL
```

## Error Handling

- All errors are wrapped with `fmt.Errorf("s3client: %w", err)` for context
- AWS SDK errors can be inspected with `errors.As(err, &smithy.OperationError{})` for callers that need to distinguish 404 vs. 403 vs. 5xx
- The client itself does not retry — callers are responsible for retry logic at their level

## Usage Example

```go
cfg, err := s3client.LoadConfigFromEnv()
if err != nil {
    log.Fatal("invalid S3 config", "error", err)
}

client, err := s3client.NewS3Client(cfg)
if err != nil {
    log.Fatal("failed to create S3 client", "error", err)
}

// Startup health check
if err := client.HealthCheck(ctx, []string{
    client.BucketName("ml-models"),
    client.BucketName("training-data"),
}); err != nil {
    log.Fatal("S3 health check failed", "error", err)
}

// Upload
if err := client.PutObject(ctx, client.BucketName("ml-models"), "fr/v42/model.onnx", file, size); err != nil {
    return fmt.Errorf("upload model: %w", err)
}
```
