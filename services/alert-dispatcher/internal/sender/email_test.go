package sender

import (
	"context"
	"strings"
	"testing"

	"github.com/estategap/services/alert-dispatcher/internal/model"
)

type emailClientStub struct {
	message EmailMessage
	calls   int
	err     error
}

func (c *emailClientStub) SendEmail(_ context.Context, message EmailMessage) error {
	c.calls++
	c.message = message
	return c.err
}

func TestEmailSenderRendersLocalesAndTracking(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name          string
		locale        string
		expectedLabel string
		expectedColor string
	}{
		{name: "english", locale: "en", expectedLabel: "View Analysis", expectedColor: "#22c55e"},
		{name: "spanish", locale: "es", expectedLabel: "Ver analisis", expectedColor: "#22c55e"},
		{name: "german", locale: "de", expectedLabel: "Analyse ansehen", expectedColor: "#22c55e"},
		{name: "french", locale: "fr", expectedLabel: "Voir analyse", expectedColor: "#22c55e"},
		{name: "portuguese", locale: "pt", expectedLabel: "Ver analise", expectedColor: "#22c55e"},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			client := &emailClientStub{}
			sender, err := NewEmailSender(client, "https://api.estategap.test", "alerts@estategap.com", "EstateGap Alerts")
			if err != nil {
				t.Fatalf("NewEmailSender() error = %v", err)
			}

			listingID := "listing-123"
			score := 0.91
			tier := 1
			imageURL := "https://images.estategap.test/listing.jpg"
			event := model.NotificationEvent{
				EventID:   "event-1",
				UserID:    "user-1",
				RuleID:    "rule-1",
				RuleName:  "Top picks",
				ListingID: &listingID,
				Channel:   model.ChannelEmail,
				DealScore: &score,
				DealTier:  &tier,
				ListingSummary: &model.ListingSummary{
					Title:    "Sunny apartment",
					PriceEUR: 245000,
					AreaM2:   88,
					City:     "Madrid",
					ImageURL: &imageURL,
					Features: []string{"Lift", "Balcony"},
				},
			}
			user := &model.UserChannelProfile{Email: "user@example.com", PreferredLanguage: tc.locale}

			result, err := sender.Send(WithHistoryID(context.Background(), "history-1"), event, user)
			if err != nil {
				t.Fatalf("Send() error = %v", err)
			}
			if !result.Success {
				t.Fatalf("Send() success = false, result = %#v", result)
			}
			if client.calls != 1 {
				t.Fatalf("SendEmail() calls = %d, want 1", client.calls)
			}
			if !strings.Contains(client.message.HTMLBody, tc.expectedLabel) {
				t.Fatalf("HTML body missing label %q", tc.expectedLabel)
			}
			if !strings.Contains(client.message.HTMLBody, "action=open") {
				t.Fatalf("HTML body missing open tracking URL")
			}
			if !strings.Contains(client.message.HTMLBody, "action=click") {
				t.Fatalf("HTML body missing click tracking URL")
			}
			if !strings.Contains(client.message.HTMLBody, tc.expectedColor) {
				t.Fatalf("HTML body missing deal badge color %q", tc.expectedColor)
			}
		})
	}
}

func TestEmailSenderDigestAndFallbackLocale(t *testing.T) {
	t.Parallel()

	client := &emailClientStub{}
	sender, err := NewEmailSender(client, "https://api.estategap.test", "alerts@estategap.com", "EstateGap Alerts")
	if err != nil {
		t.Fatalf("NewEmailSender() error = %v", err)
	}

	totalMatches := 2
	event := model.NotificationEvent{
		EventID:      "event-2",
		UserID:       "user-1",
		RuleID:       "rule-1",
		RuleName:     "Digest",
		Channel:      model.ChannelEmail,
		IsDigest:     true,
		TotalMatches: &totalMatches,
		Listings: []model.DigestListing{
			{ListingID: "one", Title: "First listing", PriceEUR: 180000, City: "Porto", DealScore: 0.88},
			{ListingID: "two", Title: "Second listing", PriceEUR: 220000, City: "Lisbon", DealScore: 0.91},
		},
	}
	user := &model.UserChannelProfile{Email: "user@example.com", PreferredLanguage: "it"}

	result, err := sender.Send(WithHistoryID(context.Background(), "history-2"), event, user)
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if !result.Success {
		t.Fatalf("Send() success = false, result = %#v", result)
	}
	if !strings.Contains(client.message.HTMLBody, "Digest summary") {
		t.Fatalf("expected fallback to english template")
	}
	if !strings.Contains(client.message.HTMLBody, "Second listing") {
		t.Fatalf("digest listing loop did not render")
	}
}
