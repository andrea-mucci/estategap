package s3client

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

const (
	defaultRegion    = "fsn1"
	maxPresignExpiry = 7 * 24 * time.Hour
)

// S3Operations defines the shared object-storage contract used by services.
type S3Operations interface {
	BucketName(logical string) string
	PutObject(ctx context.Context, bucket, key string, body io.Reader, size int64) error
	GetObject(ctx context.Context, bucket, key string) (io.ReadCloser, error)
	DeleteObject(ctx context.Context, bucket, key string) error
	ListObjects(ctx context.Context, bucket, prefix string) ([]string, error)
	PresignGetObject(ctx context.Context, bucket, key string, expiry time.Duration) (string, error)
	HealthCheck(ctx context.Context, requiredBuckets []string) error
}

// Config holds the runtime S3 client configuration.
type Config struct {
	Endpoint       string
	Region         string
	AccessKeyID    string
	SecretKey      string
	BucketPrefix   string
	ForcePathStyle bool
}

// S3Client is a thin wrapper around the AWS SDK v2 S3 client.
type S3Client struct {
	config    Config
	client    *s3.Client
	presigner *s3.PresignClient
}

// NewS3Client validates the config and constructs a client without making network calls.
func NewS3Client(cfg Config) (*S3Client, error) {
	cfg = normalizeConfig(cfg)
	if err := validateConfig(cfg); err != nil {
		return nil, err
	}

	resolver := aws.EndpointResolverWithOptionsFunc(func(service, region string, options ...interface{}) (aws.Endpoint, error) {
		if service == s3.ServiceID {
			return aws.Endpoint{
				URL:               cfg.Endpoint,
				HostnameImmutable: true,
			}, nil
		}
		return aws.Endpoint{}, &aws.EndpointNotFoundError{}
	})

	awsCfg, err := awsconfig.LoadDefaultConfig(
		context.Background(),
		awsconfig.WithRegion(cfg.Region),
		awsconfig.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(cfg.AccessKeyID, cfg.SecretKey, "")),
		awsconfig.WithEndpointResolverWithOptions(resolver),
	)
	if err != nil {
		return nil, fmt.Errorf("s3client: %w", err)
	}

	client := s3.NewFromConfig(awsCfg, func(opts *s3.Options) {
		opts.UsePathStyle = cfg.ForcePathStyle
	})

	return &S3Client{
		config:    cfg,
		client:    client,
		presigner: s3.NewPresignClient(client),
	}, nil
}

// LoadConfigFromEnv reads the shared S3 environment variables.
func LoadConfigFromEnv() (Config, error) {
	cfg := normalizeConfig(Config{
		Endpoint:       strings.TrimSpace(os.Getenv("S3_ENDPOINT")),
		Region:         strings.TrimSpace(os.Getenv("S3_REGION")),
		AccessKeyID:    strings.TrimSpace(os.Getenv("S3_ACCESS_KEY_ID")),
		SecretKey:      strings.TrimSpace(os.Getenv("S3_SECRET_ACCESS_KEY")),
		BucketPrefix:   strings.TrimSpace(os.Getenv("S3_BUCKET_PREFIX")),
		ForcePathStyle: true,
	})

	if err := validateConfig(cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

// BucketName resolves a logical bucket name against the configured prefix.
func (c *S3Client) BucketName(logical string) string {
	return fmt.Sprintf("%s-%s", c.config.BucketPrefix, logical)
}

// PutObject uploads a single object without closing the body.
func (c *S3Client) PutObject(ctx context.Context, bucket, key string, body io.Reader, size int64) error {
	input := &s3.PutObjectInput{
		Bucket:        aws.String(bucket),
		Key:           aws.String(key),
		Body:          body,
		ContentLength: aws.Int64(size),
	}
	if size < 0 {
		input.ContentLength = nil
	}
	if _, err := c.client.PutObject(ctx, input); err != nil {
		return fmt.Errorf("s3client: %w", err)
	}
	return nil
}

// GetObject downloads an object and returns the response body.
func (c *S3Client) GetObject(ctx context.Context, bucket, key string) (io.ReadCloser, error) {
	output, err := c.client.GetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(key),
	})
	if err != nil {
		return nil, fmt.Errorf("s3client: %w", err)
	}
	return output.Body, nil
}

// DeleteObject removes a single object. S3 delete semantics are idempotent.
func (c *S3Client) DeleteObject(ctx context.Context, bucket, key string) error {
	if _, err := c.client.DeleteObject(ctx, &s3.DeleteObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(key),
	}); err != nil {
		return fmt.Errorf("s3client: %w", err)
	}
	return nil
}

// ListObjects returns object keys for the given prefix, handling pagination internally.
func (c *S3Client) ListObjects(ctx context.Context, bucket, prefix string) ([]string, error) {
	paginator := s3.NewListObjectsV2Paginator(c.client, &s3.ListObjectsV2Input{
		Bucket: aws.String(bucket),
		Prefix: aws.String(prefix),
	})

	keys := make([]string, 0)
	for paginator.HasMorePages() {
		page, err := paginator.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("s3client: %w", err)
		}
		for _, object := range page.Contents {
			if object.Key != nil {
				keys = append(keys, *object.Key)
			}
		}
	}

	return keys, nil
}

// PresignGetObject generates a presigned GET URL for an object.
func (c *S3Client) PresignGetObject(ctx context.Context, bucket, key string, expiry time.Duration) (string, error) {
	if expiry <= 0 || expiry > maxPresignExpiry {
		return "", fmt.Errorf("s3client: invalid presign expiry %s", expiry)
	}

	request, err := c.presigner.PresignGetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(key),
	}, func(opts *s3.PresignOptions) {
		opts.Expires = expiry
	})
	if err != nil {
		return "", fmt.Errorf("s3client: %w", err)
	}
	return request.URL, nil
}

// HealthCheck verifies bucket accessibility and aggregates all failures.
func (c *S3Client) HealthCheck(ctx context.Context, requiredBuckets []string) error {
	missing := make([]string, 0)
	for _, bucket := range requiredBuckets {
		if strings.TrimSpace(bucket) == "" {
			continue
		}
		if _, err := c.client.HeadBucket(ctx, &s3.HeadBucketInput{Bucket: aws.String(bucket)}); err != nil {
			missing = append(missing, bucket)
		}
	}
	if len(missing) > 0 {
		return fmt.Errorf("S3 health check failed: missing buckets: [%s]", strings.Join(missing, ", "))
	}
	return nil
}

func normalizeConfig(cfg Config) Config {
	if strings.TrimSpace(cfg.Region) == "" {
		cfg.Region = defaultRegion
	}
	if !cfg.ForcePathStyle {
		cfg.ForcePathStyle = true
	}
	return cfg
}

func validateConfig(cfg Config) error {
	var missing []string
	for _, required := range []struct {
		name  string
		value string
	}{
		{name: "S3_ENDPOINT", value: cfg.Endpoint},
		{name: "S3_ACCESS_KEY_ID", value: cfg.AccessKeyID},
		{name: "S3_SECRET_ACCESS_KEY", value: cfg.SecretKey},
		{name: "S3_BUCKET_PREFIX", value: cfg.BucketPrefix},
	} {
		if strings.TrimSpace(required.value) == "" {
			missing = append(missing, required.name)
		}
	}
	if len(missing) > 0 {
		return fmt.Errorf("s3client: missing required environment variables: %s", strings.Join(missing, ", "))
	}

	parsed, err := url.Parse(cfg.Endpoint)
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return fmt.Errorf("s3client: invalid S3 endpoint %q", cfg.Endpoint)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return fmt.Errorf("s3client: invalid S3 endpoint %q", cfg.Endpoint)
	}
	if strings.TrimSpace(cfg.Region) == "" {
		return errors.New("s3client: S3 region cannot be empty")
	}
	return nil
}
