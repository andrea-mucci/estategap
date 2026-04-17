package testhelpers

import (
	"context"
	"fmt"
	"testing"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/docker/go-connections/nat"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/localstack"
)

func StartLocalStack(t *testing.T) (endpoint string, teardown func(), err error) {
	t.Helper()

	ctx := context.Background()

	container, err := localstack.Run(ctx, "localstack/localstack:3.7.2", testcontainers.WithEnv(map[string]string{
		"SERVICES": "s3",
	}))
	if err != nil {
		return "", nil, err
	}

	port, err := container.MappedPort(ctx, nat.Port("4566/tcp"))
	require.NoError(t, err)
	host, err := container.Host(ctx)
	require.NoError(t, err)
	endpoint = fmt.Sprintf("http://%s:%s", host, port.Port())

	cfg, err := awsconfig.LoadDefaultConfig(
		ctx,
		awsconfig.WithRegion("us-east-1"),
		awsconfig.WithCredentialsProvider(credentials.NewStaticCredentialsProvider("test", "test", "")),
	)
	require.NoError(t, err)
	client := s3.NewFromConfig(cfg, func(opts *s3.Options) {
		opts.BaseEndpoint = aws.String(endpoint)
		opts.UsePathStyle = true
	})
	_, err = client.ListBuckets(ctx, &s3.ListBucketsInput{})
	require.NoError(t, err)

	return endpoint, func() {
		require.NoError(t, testcontainers.TerminateContainer(container))
	}, nil
}
