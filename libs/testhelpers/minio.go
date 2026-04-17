package testhelpers

import (
	"context"
	"fmt"
	"net/http"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func StartMinIO(t *testing.T) (endpoint, accessKey, secretKey string) {
	t.Helper()

	ctx := context.Background()
	accessKey = "minioadmin"
	secretKey = "minioadmin"

	container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "minio/minio:latest",
			ExposedPorts: []string{"9000/tcp"},
			Env: map[string]string{
				"MINIO_ROOT_USER":     accessKey,
				"MINIO_ROOT_PASSWORD": secretKey,
			},
			Cmd:        []string{"server", "/data", "--console-address", ":9001"},
			WaitingFor: wait.ForListeningPort("9000/tcp"),
		},
		Started: true,
	})
	require.NoError(t, err)

	t.Cleanup(func() {
		require.NoError(t, container.Terminate(ctx))
	})

	host, err := container.Host(ctx)
	require.NoError(t, err)

	port, err := container.MappedPort(ctx, "9000/tcp")
	require.NoError(t, err)

	endpoint = fmt.Sprintf("http://%s:%s", host, port.Port())

	WaitForCondition(t, func() bool {
		response, requestErr := http.Get(endpoint + "/minio/health/ready")
		if requestErr != nil {
			return false
		}
		defer response.Body.Close()
		return response.StatusCode == http.StatusOK
	}, 30*time.Second, 500*time.Millisecond)

	return endpoint, accessKey, secretKey
}
