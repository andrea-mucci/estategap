package consumer

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"sync"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/metrics"
	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/nats-io/nats.go"
)

const (
	streamName      = "ALERTS"
	subjectFilter   = "alerts.notifications.>"
	maxAckPending   = 500
	consumerAckWait = 60 * time.Second
)

type Dispatcher interface {
	Dispatch(ctx context.Context, event model.NotificationEvent) (model.DeliveryResult, error)
}

type Consumer struct {
	js          nats.JetStreamContext
	dispatcher  Dispatcher
	metrics     *metrics.Registry
	durableName string
	workerPool  int
}

func New(js nats.JetStreamContext, dispatcher Dispatcher, registry *metrics.Registry, durableName string, workerPoolSize int) *Consumer {
	if workerPoolSize <= 0 {
		workerPoolSize = 4
	}
	return &Consumer{
		js:          js,
		dispatcher:  dispatcher,
		metrics:     registry,
		durableName: durableName,
		workerPool:  workerPoolSize,
	}
}

func (c *Consumer) Start(ctx context.Context, batchSize int) error {
	if batchSize <= 0 {
		batchSize = 50
	}
	if err := c.ensureConsumer(); err != nil {
		return err
	}

	sub, err := c.js.PullSubscribe(
		subjectFilter,
		c.durableName,
		nats.Bind(streamName, c.durableName),
		nats.ManualAck(),
		nats.AckWait(consumerAckWait),
		nats.MaxAckPending(maxAckPending),
	)
	if err != nil {
		return err
	}

	jobs := make(chan *nats.Msg, batchSize*c.workerPool)
	var wg sync.WaitGroup
	for i := 0; i < c.workerPool; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c.worker(ctx, jobs)
		}()
	}

	defer func() {
		close(jobs)
		wg.Wait()
	}()

	for {
		if ctx.Err() != nil {
			return nil
		}

		msgs, err := sub.Fetch(batchSize, nats.MaxWait(2*time.Second))
		if err != nil {
			if ctx.Err() != nil || errors.Is(err, nats.ErrTimeout) {
				continue
			}
			return err
		}

		for _, msg := range msgs {
			if metadata, metaErr := msg.Metadata(); metaErr == nil && c.metrics != nil {
				c.metrics.ConsumerLag.Set(float64(metadata.NumPending))
			}

			select {
			case <-ctx.Done():
				return nil
			case jobs <- msg:
			}
		}
	}
}

func (c *Consumer) worker(ctx context.Context, jobs <-chan *nats.Msg) {
	for {
		select {
		case <-ctx.Done():
			return
		case msg, ok := <-jobs:
			if !ok {
				return
			}
			c.handleMessage(ctx, msg)
		}
	}
}

func (c *Consumer) handleMessage(ctx context.Context, msg *nats.Msg) {
	var event model.NotificationEvent
	if err := json.Unmarshal(msg.Data, &event); err != nil {
		slog.Warn("discarding malformed notification event", "error", err)
		_ = msg.Ack()
		return
	}

	if _, err := c.dispatcher.Dispatch(ctx, event); err != nil {
		slog.Error("notification dispatch failed", "event_id", event.EventID, "channel", event.Channel, "error", err)
		_ = msg.Nak()
		return
	}

	_ = msg.Ack()
}

func (c *Consumer) ensureConsumer() error {
	if _, err := c.js.ConsumerInfo(streamName, c.durableName); err == nil {
		return nil
	}

	_, err := c.js.AddConsumer(streamName, &nats.ConsumerConfig{
		Durable:       c.durableName,
		Name:          c.durableName,
		Description:   "Notification dispatcher consumer",
		FilterSubject: subjectFilter,
		AckPolicy:     nats.AckExplicitPolicy,
		AckWait:       consumerAckWait,
		MaxDeliver:    1,
		MaxAckPending: maxAckPending,
		DeliverPolicy: nats.DeliverNewPolicy,
		ReplayPolicy:  nats.ReplayInstantPolicy,
	})
	return err
}
