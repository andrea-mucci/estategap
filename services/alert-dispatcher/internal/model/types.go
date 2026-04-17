package model

import "time"

const (
	ChannelEmail    = "email"
	ChannelTelegram = "telegram"
	ChannelWhatsApp = "whatsapp"
	ChannelPush     = "push"
	ChannelWebhook  = "webhook"
)

type NotificationEvent struct {
	EventID        string          `json:"event_id"`
	UserID         string          `json:"user_id"`
	RuleID         string          `json:"rule_id"`
	RuleName       string          `json:"rule_name"`
	ListingID      *string         `json:"listing_id,omitempty"`
	CountryCode    string          `json:"country_code"`
	Channel        string          `json:"channel"`
	WebhookURL     *string         `json:"webhook_url,omitempty"`
	Frequency      string          `json:"frequency"`
	IsDigest       bool            `json:"is_digest"`
	DealScore      *float64        `json:"deal_score,omitempty"`
	DealTier       *int            `json:"deal_tier,omitempty"`
	ListingSummary *ListingSummary `json:"listing_summary,omitempty"`
	TotalMatches   *int            `json:"total_matches,omitempty"`
	Listings       []DigestListing `json:"listings,omitempty"`
	TriggeredAt    time.Time       `json:"triggered_at"`
}

type ListingSummary struct {
	Title       string   `json:"title"`
	PriceEUR    float64  `json:"price_eur"`
	AreaM2      float64  `json:"area_m2"`
	Bedrooms    *int     `json:"bedrooms,omitempty"`
	City        string   `json:"city"`
	ImageURL    *string  `json:"image_url,omitempty"`
	PortalURL   *string  `json:"portal_url,omitempty"`
	Features    []string `json:"features,omitempty"`
	CountryCode string   `json:"country_code,omitempty"`
}

type DigestListing struct {
	ListingID string   `json:"listing_id"`
	DealScore float64  `json:"deal_score"`
	DealTier  int      `json:"deal_tier"`
	Title     string   `json:"title"`
	PriceEUR  float64  `json:"price_eur"`
	AreaM2    float64  `json:"area_m2"`
	Bedrooms  *int     `json:"bedrooms,omitempty"`
	City      string   `json:"city"`
	ImageURL  *string  `json:"image_url,omitempty"`
	PortalURL *string  `json:"portal_url,omitempty"`
	Features  []string `json:"features,omitempty"`
}

type UserChannelProfile struct {
	UserID            string
	Email             string
	PreferredLanguage string
	TelegramChatID    *int64
	PushToken         *string
	PhoneE164         *string
	WebhookSecret     *string
}

type DeliveryResult struct {
	Success      bool
	AttemptCount int
	ErrorDetail  string
	DeliveredAt  *time.Time
}

type DigestEmailListing struct {
	Title          string
	City           string
	PriceFormatted string
	DealScore      string
	ImageURL       string
	AnalysisURL    string
	PortalURL      string
}

type EmailTemplateData struct {
	PhotoURL           string
	Address            string
	PriceFormatted     string
	DealScore          float64
	DealTier           int
	DealBadgeColor     string
	Features           []string
	AnalysisURL        string
	PortalURL          string
	TrackOpenURL       string
	TrackClickAnalysis string
	TrackClickPortal   string
	IsDigest           bool
	Listings           []DigestEmailListing
	TotalMatches       int
	RuleName           string
	TriggeredAt        time.Time
}
