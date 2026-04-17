package testhelpers

import (
	"context"
	"strings"
	"testing"

	"github.com/stretchr/testify/require"
	kafkamodule "github.com/testcontainers/testcontainers-go/modules/kafka"
)

// StartKafkaContainer starts a disposable Kafka broker for integration tests.
func StartKafkaContainer(t testing.TB) (bootstrapAddr string, cleanup func()) {
	t.Helper()

	ctx := context.Background()
	container, err := kafkamodule.Run(ctx, "confluentinc/confluent-local:7.5.0")
	require.NoError(t, err)

	brokers, err := container.Brokers(ctx)
	require.NoError(t, err)
	require.NotEmpty(t, brokers)

	return strings.TrimSpace(brokers[0]), func() {
		require.NoError(t, container.Terminate(ctx))
	}
}
