package s3client

import (
	"bytes"
	"context"
	"io"
	"strings"
	"testing"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/localstack"
	"github.com/testcontainers/testcontainers-go/wait"
)

func TestS3ClientRoundTripAndHealthCheck(t *testing.T) {
	t.Parallel()

	ctx := context.Background()
	container, err := localstack.Run(
		ctx,
		"localstack/localstack:3.7.2",
		testcontainers.WithEnv(map[string]string{"SERVICES": "s3"}),
		testcontainers.WithWaitStrategy(wait.ForLog("Ready.")),
	)
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, testcontainers.TerminateContainer(container))
	})

	endpoint := localstackEndpoint(t, ctx, container)
	awsClient := mustAWSClient(t, endpoint)
	_, err = awsClient.CreateBucket(ctx, &s3.CreateBucketInput{Bucket: aws.String("test-ml-models")})
	require.NoError(t, err)
	_, err = awsClient.CreateBucket(ctx, &s3.CreateBucketInput{Bucket: aws.String("test-training-data")})
	require.NoError(t, err)

	client, err := NewS3Client(Config{
		Endpoint:       endpoint,
		Region:         "us-east-1",
		AccessKeyID:    "test",
		SecretKey:      "test",
		BucketPrefix:   "test",
		ForcePathStyle: true,
	})
	require.NoError(t, err)

	require.NoError(t, client.PutObject(ctx, client.BucketName("ml-models"), "models/test.bin", bytes.NewReader([]byte("hello")), 5))

	body, err := client.GetObject(ctx, client.BucketName("ml-models"), "models/test.bin")
	require.NoError(t, err)
	defer body.Close()

	payload, err := io.ReadAll(body)
	require.NoError(t, err)
	require.Equal(t, "hello", string(payload))

	require.NoError(t, client.HealthCheck(ctx, []string{
		client.BucketName("ml-models"),
		client.BucketName("training-data"),
	}))
}

func TestS3ClientHealthCheckAggregatesMissingBuckets(t *testing.T) {
	t.Parallel()

	ctx := context.Background()
	container, err := localstack.Run(
		ctx,
		"localstack/localstack:3.7.2",
		testcontainers.WithEnv(map[string]string{"SERVICES": "s3"}),
		testcontainers.WithWaitStrategy(wait.ForLog("Ready.")),
	)
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, testcontainers.TerminateContainer(container))
	})

	endpoint := localstackEndpoint(t, ctx, container)
	awsClient := mustAWSClient(t, endpoint)
	_, err = awsClient.CreateBucket(ctx, &s3.CreateBucketInput{Bucket: aws.String("test-ml-models")})
	require.NoError(t, err)

	client, err := NewS3Client(Config{
		Endpoint:       endpoint,
		Region:         "us-east-1",
		AccessKeyID:    "test",
		SecretKey:      "test",
		BucketPrefix:   "test",
		ForcePathStyle: true,
	})
	require.NoError(t, err)

	err = client.HealthCheck(ctx, []string{
		client.BucketName("ml-models"),
		client.BucketName("training-data"),
		client.BucketName("exports"),
	})
	require.Error(t, err)
	require.Equal(t, "S3 health check failed: missing buckets: [test-training-data, test-exports]", err.Error())
}

func TestS3ClientPresignGetObjectReturnsURL(t *testing.T) {
	t.Parallel()

	client, err := NewS3Client(Config{
		Endpoint:       "http://localhost:4566",
		Region:         "us-east-1",
		AccessKeyID:    "test",
		SecretKey:      "test",
		BucketPrefix:   "test",
		ForcePathStyle: true,
	})
	require.NoError(t, err)

	url, err := client.PresignGetObject(context.Background(), "test-ml-models", "models/test.bin", time.Hour)
	require.NoError(t, err)
	require.NotEmpty(t, url)
	require.True(t, strings.Contains(url, "test-ml-models"))
}

func localstackEndpoint(t *testing.T, ctx context.Context, container *localstack.LocalStackContainer) string {
	t.Helper()

	port, err := container.MappedPort(ctx, "4566/tcp")
	require.NoError(t, err)
	host, err := container.Host(ctx)
	require.NoError(t, err)
	return "http://" + host + ":" + port.Port()
}

func mustAWSClient(t *testing.T, endpoint string) *s3.Client {
	t.Helper()

	cfg, err := awsconfig.LoadDefaultConfig(
		context.Background(),
		awsconfig.WithRegion("us-east-1"),
		awsconfig.WithCredentialsProvider(credentials.NewStaticCredentialsProvider("test", "test", "")),
	)
	require.NoError(t, err)

	return s3.NewFromConfig(cfg, func(opts *s3.Options) {
		opts.BaseEndpoint = aws.String(endpoint)
		opts.UsePathStyle = true
	})
}
