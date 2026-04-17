package consumer

import (
	"context"
	"encoding/json"
	"log/slog"
	"sync"

	sharedbroker "github.com/estategap/libs/broker"
	"github.com/estategap/services/alert-dispatcher/internal/metrics"
	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/segmentio/kafka-go"
)

const (
	consumerGroup = "estategap.alert-dispatcher"
	topicName     = "alerts-notifications"
)

type Dispatcher interface {
	Dispatch(ctx context.Context, event model.NotificationEvent) (model.DeliveryResult, error)
}

type Consumer struct {
	broker     *sharedbroker.KafkaBroker
	dispatcher Dispatcher
	metrics    *metrics.Registry
	workerPool int
}

func New(messageBroker *sharedbroker.KafkaBroker, dispatcher Dispatcher, registry *metrics.Registry, workerPoolSize int) *Consumer {
	if workerPoolSize <= 0 {
		workerPoolSize = 4
	}
	return &Consumer{
		broker:     messageBroker,
		dispatcher: dispatcher,
		metrics:    registry,
		workerPool: workerPoolSize,
	}
}

func (c *Consumer) Start(ctx context.Context, _ int) error {
	errCh := make(chan error, c.workerPool)
	var wg sync.WaitGroup

	for i := 0; i < c.workerPool; i++ {
		reader, err := c.broker.NewReader(topicName, consumerGroup)
		if err != nil {
			return err
		}
		sharedbroker.StartLagPoller(ctx, reader, consumerGroup)

		wg.Add(1)
		go func(rd *kafka.Reader) {
			defer wg.Done()
			if err := c.broker.ConsumeReader(ctx, rd, consumerGroup, c.handleMessage); err != nil && ctx.Err() == nil {
				errCh <- err
			}
		}(reader)
	}

	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-ctx.Done():
		<-done
		return nil
	case err := <-errCh:
		<-done
		return err
	case <-done:
		return nil
	}
}

func (c *Consumer) handleMessage(ctx context.Context, message sharedbroker.Message) error {
	if c.metrics != nil {
		c.metrics.ConsumerLag.Set(0)
	}

	var event model.NotificationEvent
	if err := json.Unmarshal(message.Value, &event); err != nil {
		slog.Warn("discarding malformed notification event", "error", err)
		return nil
	}

	if _, err := c.dispatcher.Dispatch(ctx, event); err != nil {
		slog.Error("notification dispatch failed", "event_id", event.EventID, "channel", event.Channel, "error", err)
		return err
	}

	return nil
}
