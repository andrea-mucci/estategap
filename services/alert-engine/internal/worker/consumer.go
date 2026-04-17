package worker

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"time"

	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/nats-io/nats.go"
)

const (
	scoredStream          = "scored-listings"
	scoredSubject         = "scored.listings"
	scoredDurable         = "alert-engine-scored"
	priceChangesStream    = "price-changes"
	priceChangesSubject   = "listings.price-change.>"
	priceChangesDurable   = "alert-engine-price"
	defaultPriceBatchSize = 50
)

type ScoredListingHandler func(context.Context, model.ScoredListingEvent) error
type PriceChangeHandler func(context.Context, model.PriceChangeEvent) error

type Consumer struct {
	js      nats.JetStreamContext
	metrics *metrics.Registry
}

func NewConsumer(js nats.JetStreamContext, registry *metrics.Registry) *Consumer {
	return &Consumer{
		js:      js,
		metrics: registry,
	}
}

func (c *Consumer) StartScoredListings(ctx context.Context, batchSize int, handler ScoredListingHandler) error {
	if batchSize <= 0 {
		batchSize = 100
	}

	sub, err := c.js.PullSubscribe(
		scoredSubject,
		scoredDurable,
		nats.BindStream(scoredStream),
		nats.ManualAck(),
		nats.AckWait(30*time.Second),
		nats.MaxAckPending(batchSize),
	)
	if err != nil {
		return err
	}

	return c.consumeScored(ctx, sub, batchSize, handler)
}

func (c *Consumer) StartPriceChanges(ctx context.Context, handler PriceChangeHandler) error {
	sub, err := c.js.PullSubscribe(
		priceChangesSubject,
		priceChangesDurable,
		nats.BindStream(priceChangesStream),
		nats.ManualAck(),
		nats.AckWait(30*time.Second),
		nats.MaxAckPending(defaultPriceBatchSize),
	)
	if err != nil {
		return err
	}

	return c.consumePriceChanges(ctx, sub, defaultPriceBatchSize, handler)
}

func (c *Consumer) consumeScored(ctx context.Context, sub *nats.Subscription, batchSize int, handler ScoredListingHandler) error {
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
			var event model.ScoredListingEvent
			if err := json.Unmarshal(msg.Data, &event); err != nil {
				slog.Warn("discarding malformed scored listing event", "error", err)
				_ = msg.Ack()
				continue
			}

			if c.metrics != nil {
				c.metrics.EventsProcessed.WithLabelValues("scored_listing").Inc()
			}

			if err := handler(ctx, event); err != nil {
				slog.Error("scored listing handler failed", "listing_id", event.ListingID, "error", err)
				_ = msg.Nak()
				continue
			}
			_ = msg.Ack()
		}
	}
}

func (c *Consumer) consumePriceChanges(ctx context.Context, sub *nats.Subscription, batchSize int, handler PriceChangeHandler) error {
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
			var event model.PriceChangeEvent
			if err := json.Unmarshal(msg.Data, &event); err != nil {
				slog.Warn("discarding malformed price change event", "error", err)
				_ = msg.Ack()
				continue
			}

			if c.metrics != nil {
				c.metrics.EventsProcessed.WithLabelValues("price_change").Inc()
			}

			if err := handler(ctx, event); err != nil {
				slog.Error("price change handler failed", "listing_id", event.ListingID, "error", err)
				_ = msg.Nak()
				continue
			}
			_ = msg.Ack()
		}
	}
}
