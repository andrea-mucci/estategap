package publisher

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/nats-io/nats.go"
)

type NotificationEvent = model.NotificationEvent
type ListingSummary = model.ListingSummary
type DigestListing = model.DigestListing

type Publisher struct {
	js      nats.JetStreamContext
	metrics *metrics.Registry
}

func New(js nats.JetStreamContext, registry *metrics.Registry) *Publisher {
	return &Publisher{
		js:      js,
		metrics: registry,
	}
}

func (p *Publisher) PublishNotification(ctx context.Context, countryCode string, event NotificationEvent) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}

	subject := fmt.Sprintf("alerts.notifications.%s", strings.ToUpper(strings.TrimSpace(countryCode)))
	if _, err := p.js.Publish(subject, payload); err != nil {
		return err
	}

	if p.metrics != nil {
		p.metrics.NotificationsPublished.WithLabelValues(event.Channel, event.Frequency).Inc()
	}

	return nil
}
