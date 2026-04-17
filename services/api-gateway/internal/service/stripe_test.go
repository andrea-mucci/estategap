package service

import (
	"encoding/json"
	"testing"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/config"
	"github.com/stripe/stripe-go/v81"
	"github.com/stripe/stripe-go/v81/webhook"
)

func TestTierAlertLimitCoversAllTiers(t *testing.T) {
	t.Parallel()

	tests := []struct {
		tier models.SubscriptionTier
		want int16
	}{
		{tier: models.SubscriptionTierFree, want: 3},
		{tier: models.SubscriptionTierBasic, want: 10},
		{tier: models.SubscriptionTierPro, want: 25},
		{tier: models.SubscriptionTierGlobal, want: 50},
		{tier: models.SubscriptionTierAPI, want: 100},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(string(tt.tier), func(t *testing.T) {
			t.Parallel()
			if got := TierAlertLimit[tt.tier]; got != tt.want {
				t.Fatalf("TierAlertLimit[%q] = %d, want %d", tt.tier, got, tt.want)
			}
		})
	}
}

func TestStripeServiceTrialDaysLogic(t *testing.T) {
	t.Parallel()

	svc := NewStripeService(&config.Config{})
	tests := []struct {
		tier models.SubscriptionTier
		want int64
	}{
		{tier: models.SubscriptionTierBasic, want: 14},
		{tier: models.SubscriptionTierPro, want: 14},
		{tier: models.SubscriptionTierGlobal, want: 14},
		{tier: models.SubscriptionTierAPI, want: 0},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(string(tt.tier), func(t *testing.T) {
			t.Parallel()
			if got := svc.trialDaysFor(tt.tier); got != tt.want {
				t.Fatalf("trialDaysFor(%q) = %d, want %d", tt.tier, got, tt.want)
			}
		})
	}
}

func TestStripeServicePriceIDResolution(t *testing.T) {
	t.Parallel()

	svc := NewStripeService(&config.Config{
		StripePriceBasicMonthly:  "price_basic_monthly",
		StripePriceBasicAnnual:   "price_basic_annual",
		StripePriceProMonthly:    "price_pro_monthly",
		StripePriceProAnnual:     "price_pro_annual",
		StripePriceGlobalMonthly: "price_global_monthly",
		StripePriceGlobalAnnual:  "price_global_annual",
		StripePriceAPIMonthly:    "price_api_monthly",
		StripePriceAPIAnnual:     "price_api_annual",
	})

	tests := []struct {
		name   string
		tier   models.SubscriptionTier
		period string
		want   string
	}{
		{name: "basic monthly", tier: models.SubscriptionTierBasic, period: "monthly", want: "price_basic_monthly"},
		{name: "basic annual", tier: models.SubscriptionTierBasic, period: "annual", want: "price_basic_annual"},
		{name: "pro monthly", tier: models.SubscriptionTierPro, period: "monthly", want: "price_pro_monthly"},
		{name: "pro annual", tier: models.SubscriptionTierPro, period: "annual", want: "price_pro_annual"},
		{name: "global monthly", tier: models.SubscriptionTierGlobal, period: "monthly", want: "price_global_monthly"},
		{name: "global annual", tier: models.SubscriptionTierGlobal, period: "annual", want: "price_global_annual"},
		{name: "api monthly", tier: models.SubscriptionTierAPI, period: "monthly", want: "price_api_monthly"},
		{name: "api annual", tier: models.SubscriptionTierAPI, period: "annual", want: "price_api_annual"},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got, err := svc.priceIDFor(tt.tier, tt.period)
			if err != nil {
				t.Fatalf("priceIDFor(%q, %q) error = %v", tt.tier, tt.period, err)
			}
			if got != tt.want {
				t.Fatalf("priceIDFor(%q, %q) = %q, want %q", tt.tier, tt.period, got, tt.want)
			}
		})
	}
}

func TestStripeServiceParseWebhookEventRejectsInvalidSignature(t *testing.T) {
	t.Parallel()

	payload := map[string]any{
		"id":          "evt_test_webhook",
		"object":      "event",
		"api_version": stripe.APIVersion,
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("json.Marshal() error = %v", err)
	}

	signed := webhook.GenerateTestSignedPayload(&webhook.UnsignedPayload{
		Payload: payloadBytes,
		Secret:  "whsec_valid",
	})

	svc := NewStripeService(&config.Config{
		StripeSecretKey:     "sk_test_123",
		StripeWebhookSecret: "whsec_other",
	})

	if _, err := svc.ParseWebhookEvent(signed.Payload, signed.Header); err == nil {
		t.Fatal("ParseWebhookEvent() error = nil, want invalid signature error")
	}
}

func TestStripeServiceParseWebhookEventAcceptsFakeSignatureInTestMode(t *testing.T) {
	t.Parallel()

	t.Setenv("ESTATEGAP_TEST_MODE", "true")

	payload := map[string]any{
		"id":          "evt_testmode",
		"object":      "event",
		"api_version": stripe.APIVersion,
		"type":        "invoice.payment_succeeded",
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("json.Marshal() error = %v", err)
	}

	svc := NewStripeService(&config.Config{
		StripeSecretKey:     "sk_test_123",
		StripeWebhookSecret: "whsec_test_fake",
	})

	event, err := svc.ParseWebhookEvent(payloadBytes, "whsec_test_fake")
	if err != nil {
		t.Fatalf("ParseWebhookEvent() error = %v", err)
	}
	if event.ID != "evt_testmode" {
		t.Fatalf("event.ID = %q, want evt_testmode", event.ID)
	}
}
