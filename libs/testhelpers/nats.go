package testhelpers

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func StartNATS(t *testing.T) *nats.Conn {
	t.Helper()

	ctx := context.Background()
	container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "nats:2.10-alpine",
			ExposedPorts: []string{"4222/tcp"},
			Cmd:          []string{"-js"},
			WaitingFor:   wait.ForListeningPort("4222/tcp"),
		},
		Started: true,
	})
	require.NoError(t, err)

	t.Cleanup(func() {
		require.NoError(t, container.Terminate(ctx))
	})

	host, err := container.Host(ctx)
	require.NoError(t, err)

	port, err := container.MappedPort(ctx, "4222/tcp")
	require.NoError(t, err)

	url := fmt.Sprintf("nats://%s:%s", host, port.Port())

	var conn *nats.Conn
	WaitForCondition(t, func() bool {
		candidate, candidateErr := nats.Connect(url, nats.Timeout(5*time.Second))
		if candidateErr != nil {
			return false
		}

		if flushErr := candidate.FlushTimeout(5 * time.Second); flushErr != nil {
			candidate.Close()
			return false
		}

		conn = candidate
		return true
	}, 15*time.Second, 250*time.Millisecond)

	t.Cleanup(func() {
		if conn != nil {
			conn.Close()
		}
	})

	return conn
}
