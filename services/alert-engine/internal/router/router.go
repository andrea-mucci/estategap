package router

import (
	"context"
	"fmt"
	"time"

	"github.com/estategap/services/alert-engine/internal/digest"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/estategap/services/alert-engine/internal/publisher"
)

type Router struct {
	publisher *publisher.Publisher
	buffer    *digest.Buffer
}

func New(publisherClient *publisher.Publisher, buffer *digest.Buffer) *Router {
	return &Router{
		publisher: publisherClient,
		buffer:    buffer,
	}
}

func (r *Router) RouteInstant(ctx context.Context, rule *model.CachedRule, listing model.ScoredListingEvent) ([]string, error) {
	if rule == nil || model.NormalizeFrequency(rule.Frequency) != model.FrequencyInstant {
		return nil, nil
	}

	summary := listing.ListingSummary()
	channels := make([]string, 0, len(rule.Channels))

	for _, channel := range rule.Channels {
		event := publisher.NotificationEvent{
			EventID:        model.NewEventID(),
			UserID:         rule.UserID,
			RuleID:         rule.ID,
			RuleName:       rule.Name,
			ListingID:      stringPtr(listing.ListingID),
			CountryCode:    listing.CountryCode,
			Channel:        channel.Type,
			WebhookURL:     channel.WebhookURL,
			Frequency:      model.FrequencyInstant,
			IsDigest:       false,
			DealScore:      float64Ptr(listing.DealScore),
			DealTier:       intPtr(listing.DealTier),
			ListingSummary: &summary,
			TriggeredAt:    time.Now().UTC(),
		}
		if err := r.publisher.PublishNotification(ctx, listing.CountryCode, event); err != nil {
			return channels, fmt.Errorf("publish instant notification for rule %s: %w", rule.ID, err)
		}
		channels = append(channels, channel.Type)
	}

	return channels, nil
}

func (r *Router) RouteDigest(ctx context.Context, rule *model.CachedRule, listing model.ScoredListingEvent) error {
	if rule == nil || model.NormalizeFrequency(rule.Frequency) == model.FrequencyInstant {
		return nil
	}
	if r.buffer == nil {
		return fmt.Errorf("digest buffer is not configured")
	}
	return r.buffer.Add(ctx, rule.UserID, rule.ID, rule.Frequency, listing.ListingID, listing.DealScore)
}

func float64Ptr(value float64) *float64 {
	return &value
}

func intPtr(value int) *int {
	return &value
}

func stringPtr(value string) *string {
	return &value
}
