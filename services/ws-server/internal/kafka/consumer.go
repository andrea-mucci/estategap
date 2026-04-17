package wskafka

import (
	"context"
	"encoding/json"
	"sync"
	"time"

	sharedbroker "github.com/estategap/libs/broker"
	"github.com/estategap/services/ws-server/internal/config"
	"github.com/estategap/services/ws-server/internal/hub"
	"github.com/estategap/services/ws-server/internal/metrics"
	"github.com/estategap/services/ws-server/internal/protocol"
	"github.com/segmentio/kafka-go"
)

const (
	consumerGroup = "estategap.ws-server"
	topicName     = "alerts-notifications"
)

type Consumer struct {
	broker *sharedbroker.KafkaBroker
	hub    *hub.Hub
	cfg    *config.Config
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

func New(messageBroker *sharedbroker.KafkaBroker, h *hub.Hub, cfg *config.Config) *Consumer {
	return &Consumer{
		broker: messageBroker,
		hub:    h,
		cfg:    cfg,
	}
}

func (c *Consumer) Start(ctx context.Context) error {
	runCtx, cancel := context.WithCancel(ctx)
	c.cancel = cancel

	workers := c.cfg.KafkaWorkers
	if workers <= 0 {
		workers = 4
	}

	errCh := make(chan error, workers)
	for i := 0; i < workers; i++ {
		reader, err := c.broker.NewReader(topicName, consumerGroup)
		if err != nil {
			return err
		}
		sharedbroker.StartLagPoller(runCtx, reader, consumerGroup)

		c.wg.Add(1)
		go func(rd *kafka.Reader) {
			defer c.wg.Done()
			if err := c.broker.ConsumeReader(runCtx, rd, consumerGroup, c.handleMessage); err != nil && runCtx.Err() == nil {
				errCh <- err
				cancel()
			}
		}(reader)
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
	case <-done:
		return nil
	}
}

func (c *Consumer) Stop() {
	if c.cancel != nil {
		c.cancel()
	}
	c.wg.Wait()
}

func (c *Consumer) handleMessage(_ context.Context, message sharedbroker.Message) error {
	var event notificationEvent
	if err := json.Unmarshal(message.Value, &event); err != nil {
		metrics.NotificationsSkippedTotal.Inc()
		return nil
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
		metrics.NotificationsSkippedTotal.Inc()
		return nil
	}

	if c.hub.Send(event.UserID, raw) {
		metrics.NotificationsDeliveredTotal.Inc()
		return nil
	}
	metrics.NotificationsSkippedTotal.Inc()
	return nil
}
