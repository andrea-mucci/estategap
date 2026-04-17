package service

import (
	"errors"
	"fmt"
	"strings"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/config"
	"github.com/stripe/stripe-go/v81"
	billingportalsession "github.com/stripe/stripe-go/v81/billingportal/session"
	checkoutsession "github.com/stripe/stripe-go/v81/checkout/session"
	subscriptionclient "github.com/stripe/stripe-go/v81/subscription"
	"github.com/stripe/stripe-go/v81/webhook"
)

var TierAlertLimit = map[models.SubscriptionTier]int16{
	models.SubscriptionTierFree:   3,
	models.SubscriptionTierBasic:  10,
	models.SubscriptionTierPro:    25,
	models.SubscriptionTierGlobal: 50,
	models.SubscriptionTierAPI:    100,
}

type StripeService struct {
	cfg *config.Config
}

func NewStripeService(cfg *config.Config) *StripeService {
	if cfg != nil {
		stripe.Key = cfg.StripeSecretKey
	}
	return &StripeService{cfg: cfg}
}

func (s *StripeService) DefaultPortalReturnURL() string {
	if s == nil || s.cfg == nil {
		return ""
	}
	return s.cfg.StripePortalReturnURL
}

func (s *StripeService) ParseWebhookEvent(payload []byte, sigHeader string) (stripe.Event, error) {
	if s == nil || s.cfg == nil {
		return stripe.Event{}, errors.New("stripe not configured")
	}
	return webhook.ConstructEvent(payload, sigHeader, s.cfg.StripeWebhookSecret)
}

func (s *StripeService) CreateCheckoutSession(
	userID,
	email string,
	tier,
	period string,
) (*stripe.CheckoutSession, error) {
	params, err := s.checkoutSessionParams(userID, email, models.SubscriptionTier(tier), period)
	if err != nil {
		return nil, err
	}
	return checkoutsession.New(params)
}

func (s *StripeService) CreatePortalSession(stripeCustomerID, returnURL string) (*stripe.BillingPortalSession, error) {
	if s == nil || s.cfg == nil {
		return nil, errors.New("stripe not configured")
	}
	if strings.TrimSpace(returnURL) == "" {
		returnURL = s.cfg.StripePortalReturnURL
	}
	params := &stripe.BillingPortalSessionParams{
		Customer:  stripe.String(strings.TrimSpace(stripeCustomerID)),
		ReturnURL: stripe.String(strings.TrimSpace(returnURL)),
	}
	return billingportalsession.New(params)
}

func (s *StripeService) GetSubscription(subscriptionID string) (*stripe.Subscription, error) {
	if s == nil || s.cfg == nil {
		return nil, errors.New("stripe not configured")
	}
	return subscriptionclient.Get(strings.TrimSpace(subscriptionID), nil)
}

func (s *StripeService) checkoutSessionParams(
	userID,
	email string,
	tier models.SubscriptionTier,
	period string,
) (*stripe.CheckoutSessionParams, error) {
	if s == nil || s.cfg == nil {
		return nil, errors.New("stripe not configured")
	}

	priceID, err := s.priceIDFor(tier, period)
	if err != nil {
		return nil, err
	}

	params := &stripe.CheckoutSessionParams{
		CancelURL:         stripe.String(s.cfg.StripeCancelURL),
		ClientReferenceID: stripe.String(strings.TrimSpace(userID)),
		CustomerEmail:     stripe.String(strings.TrimSpace(email)),
		LineItems: []*stripe.CheckoutSessionLineItemParams{
			{
				Price:    stripe.String(priceID),
				Quantity: stripe.Int64(1),
			},
		},
		Metadata: map[string]string{
			"tier":           string(tier),
			"billing_period": period,
		},
		Mode:               stripe.String(string(stripe.CheckoutSessionModeSubscription)),
		PaymentMethodTypes: stripe.StringSlice([]string{"card"}),
		SuccessURL:         stripe.String(s.cfg.StripeSuccessURL),
		SubscriptionData: &stripe.CheckoutSessionSubscriptionDataParams{
			Metadata: map[string]string{
				"tier":           string(tier),
				"billing_period": period,
			},
		},
	}

	if trialDays := s.trialDaysFor(tier); trialDays > 0 {
		params.SubscriptionData.TrialPeriodDays = stripe.Int64(trialDays)
	}

	return params, nil
}

func (s *StripeService) priceIDFor(tier models.SubscriptionTier, period string) (string, error) {
	if s == nil || s.cfg == nil {
		return "", errors.New("stripe not configured")
	}

	period = strings.ToLower(strings.TrimSpace(period))

	var value string
	switch tier {
	case models.SubscriptionTierBasic:
		if period == "monthly" {
			value = s.cfg.StripePriceBasicMonthly
		} else if period == "annual" {
			value = s.cfg.StripePriceBasicAnnual
		}
	case models.SubscriptionTierPro:
		if period == "monthly" {
			value = s.cfg.StripePriceProMonthly
		} else if period == "annual" {
			value = s.cfg.StripePriceProAnnual
		}
	case models.SubscriptionTierGlobal:
		if period == "monthly" {
			value = s.cfg.StripePriceGlobalMonthly
		} else if period == "annual" {
			value = s.cfg.StripePriceGlobalAnnual
		}
	case models.SubscriptionTierAPI:
		if period == "monthly" {
			value = s.cfg.StripePriceAPIMonthly
		} else if period == "annual" {
			value = s.cfg.StripePriceAPIAnnual
		}
	default:
		return "", fmt.Errorf("unsupported tier %q", tier)
	}

	value = strings.TrimSpace(value)
	if value == "" {
		return "", fmt.Errorf("missing Stripe price id for %s/%s", tier, period)
	}
	return value, nil
}

func (s *StripeService) trialDaysFor(tier models.SubscriptionTier) int64 {
	switch tier {
	case models.SubscriptionTierBasic, models.SubscriptionTierPro, models.SubscriptionTierGlobal:
		return 14
	default:
		return 0
	}
}
