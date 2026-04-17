package broker

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"github.com/estategap/testhelpers"
	"github.com/stretchr/testify/require"
)

func TestKafkaBrokerPublishAndSubscribe(t *testing.T) {
	bootstrapAddr, cleanup := testhelpers.StartKafkaContainer(t)
	t.Cleanup(cleanup)

	pub, err := NewKafkaBroker(KafkaConfig{Brokers: []string{bootstrapAddr}})
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, pub.Close())
	})

	sub, err := NewKafkaBroker(KafkaConfig{Brokers: []string{bootstrapAddr}})
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, sub.Close())
	})

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	received := make(chan Message, 1)
	go func() {
		_ = sub.Subscribe(ctx, []string{"raw-listings"}, "broker-roundtrip", func(_ context.Context, msg Message) error {
			select {
			case received <- msg:
			default:
			}
			cancel()
			return nil
		})
	}()

	require.NoError(t, pub.Publish(ctx, "raw-listings", "ES", []byte(`{"listing_id":"abc"}`)))

	select {
	case msg := <-received:
		require.Equal(t, "ES", msg.Key)
		require.Equal(t, `{"listing_id":"abc"}`, string(msg.Value))
		require.Equal(t, pub.TopicName("raw-listings"), msg.Topic)
	case <-ctx.Done():
		t.Fatalf("timed out waiting for consumed message: %v", ctx.Err())
	}
}

func TestKafkaBrokerPublishesDeadLetterAfterRetries(t *testing.T) {
	bootstrapAddr, cleanup := testhelpers.StartKafkaContainer(t)
	t.Cleanup(cleanup)

	pub, err := NewKafkaBroker(KafkaConfig{
		Brokers:    []string{bootstrapAddr},
		MaxRetries: 3,
	})
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, pub.Close())
	})

	sub, err := NewKafkaBroker(KafkaConfig{
		Brokers:    []string{bootstrapAddr},
		MaxRetries: 3,
	})
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, sub.Close())
	})

	inspector, err := NewKafkaBroker(KafkaConfig{Brokers: []string{bootstrapAddr}})
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, inspector.Close())
	})

	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()

	var attempts atomic.Int32
	go func() {
		_ = sub.Subscribe(ctx, []string{"raw-listings"}, "broker-dlt-source", func(context.Context, Message) error {
			attempts.Add(1)
			return errors.New("simulated handler failure")
		})
	}()

	dltReader, err := inspector.NewReader("dead-letter", "broker-dlt-inspector")
	require.NoError(t, err)

	deadLetters := make(chan Message, 1)
	go func() {
		_ = inspector.ConsumeReader(ctx, dltReader, "broker-dlt-inspector", func(_ context.Context, msg Message) error {
			select {
			case deadLetters <- msg:
			default:
			}
			cancel()
			return nil
		})
	}()

	require.NoError(t, pub.Publish(ctx, "raw-listings", "FR", []byte(`{"listing_id":"boom"}`)))

	select {
	case msg := <-deadLetters:
		require.Equal(t, int32(3), attempts.Load())
		require.Equal(t, "FR", msg.Key)
		require.Equal(t, "broker-dlt-source", msg.Headers["x-service"])
		require.Equal(t, pub.TopicName("raw-listings"), msg.Headers["x-original-topic"])
		require.Equal(t, "3", msg.Headers["x-retry-count"])
	case <-ctx.Done():
		t.Fatalf("timed out waiting for dead-letter message: %v", ctx.Err())
	}
}
