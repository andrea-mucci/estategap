package publisher

import (
	"context"
	"encoding/json"

	sharedbroker "github.com/estategap/libs/broker"
	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/model"
)

type NotificationEvent = model.NotificationEvent
type ListingSummary = model.ListingSummary
type DigestListing = model.DigestListing

type Publisher struct {
	broker  sharedbroker.Publisher
	metrics *metrics.Registry
}

func New(messageBroker sharedbroker.Publisher, registry *metrics.Registry) *Publisher {
	return &Publisher{
		broker:  messageBroker,
		metrics: registry,
	}
}

func (p *Publisher) PublishNotification(ctx context.Context, event NotificationEvent) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}

	if err := p.broker.Publish(ctx, "alerts-notifications", event.UserID, payload); err != nil {
		return err
	}

	if p.metrics != nil {
		p.metrics.NotificationsPublished.WithLabelValues(event.Channel, event.Frequency).Inc()
	}

	return nil
}
