package wsnats

import (
	"context"
	"encoding/json"
	"errors"
	"sync"
	"time"

	"github.com/estategap/services/ws-server/internal/config"
	"github.com/estategap/services/ws-server/internal/hub"
	"github.com/estategap/services/ws-server/internal/metrics"
	"github.com/estategap/services/ws-server/internal/protocol"
	"github.com/nats-io/nats.go"
)

const (
	streamName    = "ALERTS"
	durableName   = "ws-server-notifications"
	subjectFilter = "alerts.notifications.>"
)

type Consumer struct {
	js     nats.JetStreamContext
	hub    *hub.Hub
	cfg    *config.Config
	sub    *nats.Subscription
	cancel context.CancelFunc
	wg     sync.WaitGroup
}

type notificationEvent struct {
	EventID        string               `json:"event_id"`
	UserID         string               `json:"user_id"`
	RuleName       string               `json:"rule_name"`
	ListingID      string               `json:"listing_id"`
	DealScore      float64              `json:"deal_score"`
	DealTier       int                  `json:"deal_tier"`
	ListingSummary *notificationSummary `json:"listing_summary,omitempty"`
	TriggeredAt    time.Time            `json:"triggered_at"`
}

type notificationSummary struct {
	Title       string  `json:"title"`
	PriceEUR    float64 `json:"price_eur"`
	AreaM2      float64 `json:"area_m2"`
	City        string  `json:"city"`
	ImageURL    string  `json:"image_url,omitempty"`
	AnalysisURL string  `json:"analysis_url,omitempty"`
	Address     string  `json:"address,omitempty"`
}

func New(js nats.JetStreamContext, hub *hub.Hub, cfg *config.Config) *Consumer {
	return &Consumer{
		js:  js,
		hub: hub,
		cfg: cfg,
	}
}

func (c *Consumer) Setup() error {
	if _, err := c.js.ConsumerInfo(streamName, durableName); err != nil {
		if _, addErr := c.js.AddConsumer(streamName, &nats.ConsumerConfig{
			Durable:       durableName,
			Name:          durableName,
			FilterSubject: subjectFilter,
			AckPolicy:     nats.AckExplicitPolicy,
			AckWait:       10 * time.Second,
			MaxDeliver:    1,
			MaxAckPending: 1000,
			DeliverPolicy: nats.DeliverNewPolicy,
			ReplayPolicy:  nats.ReplayInstantPolicy,
		}); addErr != nil {
			return addErr
		}
	}

	sub, err := c.js.PullSubscribe(
		subjectFilter,
		durableName,
		nats.Bind(streamName, durableName),
		nats.ManualAck(),
		nats.AckWait(10*time.Second),
		nats.MaxAckPending(1000),
	)
	if err != nil {
		return err
	}

	c.sub = sub
	return nil
}

func (c *Consumer) Start(ctx context.Context) error {
	if c.sub == nil {
		if err := c.Setup(); err != nil {
			return err
		}
	}

	runCtx, cancel := context.WithCancel(ctx)
	c.cancel = cancel

	errCh := make(chan error, 1)
	workers := c.cfg.NATSWorkers
	if workers <= 0 {
		workers = 4
	}

	for i := 0; i < workers; i++ {
		c.wg.Add(1)
		go func() {
			defer c.wg.Done()
			if err := c.worker(runCtx); err != nil && !errors.Is(err, context.Canceled) {
				select {
				case errCh <- err:
				default:
				}
				cancel()
			}
		}()
	}

	done := make(chan struct{})
	go func() {
		c.wg.Wait()
		close(done)
	}()

	select {
	case <-runCtx.Done():
		<-done
		return nil
	case err := <-errCh:
		<-done
		return err
	}
}

func (c *Consumer) Stop() {
	if c.cancel != nil {
		c.cancel()
	}
	if c.sub != nil {
		_ = c.sub.Unsubscribe()
	}
	c.wg.Wait()
}

func (c *Consumer) worker(ctx context.Context) error {
	for {
		if ctx.Err() != nil {
			return nil
		}

		msgs, err := c.sub.Fetch(10, nats.MaxWait(2*time.Second))
		if err != nil {
			if ctx.Err() != nil || errors.Is(err, nats.ErrTimeout) {
				continue
			}
			return err
		}

		for _, msg := range msgs {
			c.handleMessage(msg)
		}
	}
}

func (c *Consumer) handleMessage(msg *nats.Msg) {
	defer func() { _ = msg.Ack() }()

	var event notificationEvent
	if err := json.Unmarshal(msg.Data, &event); err != nil {
		metrics.NATSNotificationsSkippedTotal.Inc()
		return
	}

	payload := protocol.DealAlertPayload{
		EventID:     event.EventID,
		ListingID:   event.ListingID,
		RuleName:    event.RuleName,
		TriggeredAt: event.TriggeredAt.Format(time.RFC3339),
		DealScore:   event.DealScore,
		DealTier:    event.DealTier,
	}
	if event.ListingSummary != nil {
		payload.Title = event.ListingSummary.Title
		payload.Address = event.ListingSummary.Address
		if payload.Address == "" {
			payload.Address = event.ListingSummary.City
		}
		payload.PriceEUR = event.ListingSummary.PriceEUR
		payload.AreaM2 = event.ListingSummary.AreaM2
		payload.PhotoURL = event.ListingSummary.ImageURL
		payload.AnalysisURL = event.ListingSummary.AnalysisURL
	}

	raw, err := protocol.MarshalEnvelope("deal_alert", "", payload)
	if err != nil {
		metrics.NATSNotificationsSkippedTotal.Inc()
		return
	}

	if c.hub.Send(event.UserID, raw) {
		metrics.NATSNotificationsDeliveredTotal.Inc()
		return
	}
	metrics.NATSNotificationsSkippedTotal.Inc()
}
