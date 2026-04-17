package worker

import (
	"context"
	"encoding/json"
	"log/slog"
	"sync"

	sharedbroker "github.com/estategap/libs/broker"
	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/segmentio/kafka-go"
)

const (
	consumerGroup = "estategap.alert-engine"
	scoredTopic   = "scored-listings"
	priceTopic    = "price-changes"
)

type ScoredListingHandler func(context.Context, model.ScoredListingEvent) error
type PriceChangeHandler func(context.Context, model.PriceChangeEvent) error

type Consumer struct {
	broker  *sharedbroker.KafkaBroker
	metrics *metrics.Registry
}

func NewConsumer(messageBroker *sharedbroker.KafkaBroker, registry *metrics.Registry) *Consumer {
	return &Consumer{
		broker:  messageBroker,
		metrics: registry,
	}
}

func (c *Consumer) Start(
	ctx context.Context,
	_ int,
	scoredHandler ScoredListingHandler,
	priceHandler PriceChangeHandler,
) error {
	type subscription struct {
		topic   string
		handler sharedbroker.MessageHandler
	}

	subscriptions := []subscription{
		{topic: scoredTopic, handler: c.wrapScoredHandler(scoredHandler)},
		{topic: priceTopic, handler: c.wrapPriceHandler(priceHandler)},
	}

	errCh := make(chan error, len(subscriptions))
	var wg sync.WaitGroup
	for _, sub := range subscriptions {
		reader, err := c.broker.NewReader(sub.topic, consumerGroup)
		if err != nil {
			return err
		}
		sharedbroker.StartLagPoller(ctx, reader, consumerGroup)

		wg.Add(1)
		go func(rd *kafka.Reader, handler sharedbroker.MessageHandler) {
			defer wg.Done()
			if err := c.broker.ConsumeReader(ctx, rd, consumerGroup, handler); err != nil && ctx.Err() == nil {
				errCh <- err
			}
		}(reader, sub.handler)
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

func (c *Consumer) wrapScoredHandler(handler ScoredListingHandler) sharedbroker.MessageHandler {
	return func(ctx context.Context, message sharedbroker.Message) error {
		var event model.ScoredListingEvent
		if err := json.Unmarshal(message.Value, &event); err != nil {
			slog.Warn("discarding malformed scored listing event", "error", err)
			return nil
		}

		if c.metrics != nil {
			c.metrics.EventsProcessed.WithLabelValues("scored_listing").Inc()
		}

		if err := handler(ctx, event); err != nil {
			slog.Error("scored listing handler failed", "listing_id", event.ListingID, "error", err)
			return err
		}
		return nil
	}
}

func (c *Consumer) wrapPriceHandler(handler PriceChangeHandler) sharedbroker.MessageHandler {
	return func(ctx context.Context, message sharedbroker.Message) error {
		var event model.PriceChangeEvent
		if err := json.Unmarshal(message.Value, &event); err != nil {
			slog.Warn("discarding malformed price change event", "error", err)
			return nil
		}

		if c.metrics != nil {
			c.metrics.EventsProcessed.WithLabelValues("price_change").Inc()
		}

		if err := handler(ctx, event); err != nil {
			slog.Error("price change handler failed", "listing_id", event.ListingID, "error", err)
			return err
		}
		return nil
	}
}
