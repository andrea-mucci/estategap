package testhelpers

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func StartPostgres(t *testing.T) *pgxpool.Pool {
	t.Helper()

	ctx := context.Background()
	container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "postgis/postgis:16-3.4",
			ExposedPorts: []string{"5432/tcp"},
			Env: map[string]string{
				"POSTGRES_DB":       "estategap",
				"POSTGRES_USER":     "estategap",
				"POSTGRES_PASSWORD": "estategap",
			},
			WaitingFor: wait.ForListeningPort("5432/tcp"),
		},
		Started: true,
	})
	require.NoError(t, err)

	t.Cleanup(func() {
		require.NoError(t, container.Terminate(ctx))
	})

	host, err := container.Host(ctx)
	require.NoError(t, err)

	port, err := container.MappedPort(ctx, "5432/tcp")
	require.NoError(t, err)

	dsn := fmt.Sprintf(
		"postgres://estategap:estategap@%s:%s/estategap?sslmode=disable",
		host,
		port.Port(),
	)

	var pool *pgxpool.Pool
	WaitForCondition(t, func() bool {
		candidate, candidateErr := pgxpool.New(ctx, dsn)
		if candidateErr != nil {
			return false
		}

		if pingErr := candidate.Ping(ctx); pingErr != nil {
			candidate.Close()
			return false
		}

		pool = candidate
		return true
	}, 30*time.Second, 500*time.Millisecond)

	t.Cleanup(func() {
		if pool != nil {
			pool.Close()
		}
	})

	return pool
}
