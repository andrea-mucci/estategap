package model

import (
	"crypto/rand"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

const (
	FrequencyInstant = "instant"
	FrequencyHourly  = "hourly"
	FrequencyDaily   = "daily"
)

type NotificationChannel struct {
	Type       string  `json:"type"`
	WebhookURL *string `json:"webhook_url,omitempty"`
}

type RuleFilter struct {
	PropertyTypes     []string `json:"-"`
	PriceMin          *float64 `json:"-"`
	PriceMax          *float64 `json:"-"`
	AreaMin           *float64 `json:"-"`
	AreaMax           *float64 `json:"-"`
	BedroomsMin       *int     `json:"-"`
	BedroomsMax       *int     `json:"-"`
	DealTierMax       *int     `json:"-"`
	Features          []string `json:"-"`
	UnsupportedFields []string `json:"-"`
}

type CachedRule struct {
	ID          string
	UserID      string
	Name        string
	CountryCode string
	ZoneIDs     []string
	Category    string
	Filter      RuleFilter
	Channels    []NotificationChannel
	Frequency   string
}

type ZoneGeometry struct {
	ID          string
	CountryCode string
	BBoxMinLat  float64
	BBoxMaxLat  float64
	BBoxMinLon  float64
	BBoxMaxLon  float64
}

type ScoredListingEvent struct {
	ListingID         string    `json:"listing_id"`
	CountryCode       string    `json:"country_code"`
	Lat               float64   `json:"lat"`
	Lon               float64   `json:"lon"`
	PropertyType      string    `json:"property_type"`
	PriceEUR          float64   `json:"price_eur"`
	AreaM2            float64   `json:"area_m2"`
	Bedrooms          *int      `json:"bedrooms,omitempty"`
	Features          []string  `json:"features,omitempty"`
	DealScore         float64   `json:"deal_score"`
	DealTier          int       `json:"deal_tier"`
	EstimatedPriceEUR float64   `json:"estimated_price_eur"`
	ModelVersion      string    `json:"model_version"`
	ScoredAt          time.Time `json:"scored_at"`
	Title             string    `json:"title,omitempty"`
	City              string    `json:"city,omitempty"`
	ImageURL          *string   `json:"image_url,omitempty"`
}

type PriceChangeEvent struct {
	ListingID   string    `json:"listing_id"`
	CountryCode string    `json:"country_code"`
	OldPriceEUR float64   `json:"old_price_eur"`
	NewPriceEUR float64   `json:"new_price_eur"`
	ChangePct   float64   `json:"change_pct,omitempty"`
	ChangedAt   time.Time `json:"changed_at"`
}

type ListingSummary struct {
	Title       string  `json:"title"`
	PriceEUR    float64 `json:"price_eur"`
	AreaM2      float64 `json:"area_m2"`
	Bedrooms    *int    `json:"bedrooms,omitempty"`
	City        string  `json:"city"`
	ImageURL    *string `json:"image_url,omitempty"`
	CountryCode string  `json:"-"`
	DealScore   float64 `json:"-"`
	DealTier    int     `json:"-"`
}

type DigestListing struct {
	ListingID string  `json:"listing_id"`
	DealScore float64 `json:"deal_score"`
	DealTier  int     `json:"deal_tier"`
	Title     string  `json:"title"`
	PriceEUR  float64 `json:"price_eur"`
	AreaM2    float64 `json:"area_m2"`
	Bedrooms  *int    `json:"bedrooms,omitempty"`
	City      string  `json:"city"`
	ImageURL  *string `json:"image_url,omitempty"`
}

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

func NormalizeFrequency(value string) string {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case FrequencyHourly:
		return FrequencyHourly
	case FrequencyDaily:
		return FrequencyDaily
	default:
		return FrequencyInstant
	}
}

func NormalizeCountryCode(value string) string {
	return strings.ToUpper(strings.TrimSpace(value))
}

func NewEventID() string {
	var raw [16]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}

	raw[6] = (raw[6] & 0x0f) | 0x40
	raw[8] = (raw[8] & 0x3f) | 0x80

	return fmt.Sprintf(
		"%x-%x-%x-%x-%x",
		raw[0:4],
		raw[4:6],
		raw[6:8],
		raw[8:10],
		raw[10:16],
	)
}

func (f RuleFilter) HasUnsupportedFields() bool {
	return len(f.UnsupportedFields) > 0
}

func (e ScoredListingEvent) ListingSummary() ListingSummary {
	return ListingSummary{
		Title:    strings.TrimSpace(e.Title),
		PriceEUR: e.PriceEUR,
		AreaM2:   e.AreaM2,
		Bedrooms: e.Bedrooms,
		City:     strings.TrimSpace(e.City),
		ImageURL: e.ImageURL,
	}
}

func (e ScoredListingEvent) WithSummary(summary ListingSummary) ScoredListingEvent {
	if strings.TrimSpace(e.Title) == "" {
		e.Title = strings.TrimSpace(summary.Title)
	}
	if strings.TrimSpace(e.City) == "" {
		e.City = strings.TrimSpace(summary.City)
	}
	if e.ImageURL == nil {
		e.ImageURL = summary.ImageURL
	}
	if e.PriceEUR == 0 && summary.PriceEUR != 0 {
		e.PriceEUR = summary.PriceEUR
	}
	if e.AreaM2 == 0 && summary.AreaM2 != 0 {
		e.AreaM2 = summary.AreaM2
	}
	if e.Bedrooms == nil && summary.Bedrooms != nil {
		e.Bedrooms = summary.Bedrooms
	}
	return e
}

func (f *RuleFilter) UnmarshalJSON(data []byte) error {
	*f = RuleFilter{}
	if len(data) == 0 || string(data) == "null" {
		return nil
	}

	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}

	for key, value := range raw {
		switch key {
		case "property_type":
			if !parsePropertyTypes(value, &f.PropertyTypes) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "price_min":
			if !parseFloatValue(value, &f.PriceMin) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "price_max":
			if !parseFloatValue(value, &f.PriceMax) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "area_min":
			if !parseFloatValue(value, &f.AreaMin) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "area_max":
			if !parseFloatValue(value, &f.AreaMax) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "bedrooms_min":
			if !parseIntValue(value, &f.BedroomsMin) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "bedrooms_max":
			if !parseIntValue(value, &f.BedroomsMax) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "deal_tier_max":
			if !parseIntValue(value, &f.DealTierMax) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "features":
			if !parseFeatures(value, &f.Features) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "price_eur":
			if !parseNumericOperators(value, &f.PriceMin, &f.PriceMax) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "area_m2":
			if !parseNumericOperators(value, &f.AreaMin, &f.AreaMax) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "bedrooms":
			if !parseIntOperators(value, &f.BedroomsMin, &f.BedroomsMax) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		case "deal_tier":
			if !parseIntOperators(value, nil, &f.DealTierMax) {
				f.UnsupportedFields = append(f.UnsupportedFields, key)
			}
		default:
			f.UnsupportedFields = append(f.UnsupportedFields, key)
		}
	}

	return nil
}

func parseFloatValue(data []byte, target **float64) bool {
	var value float64
	if err := json.Unmarshal(data, &value); err != nil {
		return false
	}
	*target = &value
	return true
}

func parseIntValue(data []byte, target **int) bool {
	var value int
	if err := json.Unmarshal(data, &value); err != nil {
		return false
	}
	*target = &value
	return true
}

func parsePropertyTypes(data []byte, target *[]string) bool {
	var exact string
	if err := json.Unmarshal(data, &exact); err == nil {
		if exact == "" {
			return true
		}
		*target = []string{strings.ToLower(strings.TrimSpace(exact))}
		return true
	}

	var values []string
	if err := json.Unmarshal(data, &values); err == nil {
		*target = normalizeStrings(values)
		return true
	}

	var operators map[string]json.RawMessage
	if err := json.Unmarshal(data, &operators); err != nil {
		return false
	}
	if raw, ok := operators["eq"]; ok {
		return parsePropertyTypes(raw, target)
	}
	if raw, ok := operators["in"]; ok {
		return parsePropertyTypes(raw, target)
	}
	return false
}

func parseFeatures(data []byte, target *[]string) bool {
	var values []string
	if err := json.Unmarshal(data, &values); err == nil {
		*target = normalizeStrings(values)
		return true
	}

	var operators map[string]json.RawMessage
	if err := json.Unmarshal(data, &operators); err != nil {
		return false
	}
	if raw, ok := operators["contains_all"]; ok {
		return parseFeatures(raw, target)
	}
	if raw, ok := operators["in"]; ok {
		return parseFeatures(raw, target)
	}
	return false
}

func parseNumericOperators(data []byte, minTarget, maxTarget **float64) bool {
	var value float64
	if err := json.Unmarshal(data, &value); err == nil {
		if minTarget != nil {
			*minTarget = &value
		}
		if maxTarget != nil {
			*maxTarget = &value
		}
		return true
	}

	var operators map[string]json.RawMessage
	if err := json.Unmarshal(data, &operators); err != nil {
		return false
	}

	parsed := false
	if minTarget != nil {
		if raw, ok := operators["gte"]; ok {
			parsed = parseFloatValue(raw, minTarget) || parsed
		}
		if raw, ok := operators["gt"]; ok {
			parsed = parseFloatValue(raw, minTarget) || parsed
		}
		if raw, ok := operators["eq"]; ok {
			parsed = parseFloatValue(raw, minTarget) || parsed
		}
	}
	if maxTarget != nil {
		if raw, ok := operators["lte"]; ok {
			parsed = parseFloatValue(raw, maxTarget) || parsed
		}
		if raw, ok := operators["lt"]; ok {
			parsed = parseFloatValue(raw, maxTarget) || parsed
		}
		if raw, ok := operators["eq"]; ok {
			parsed = parseFloatValue(raw, maxTarget) || parsed
		}
	}
	return parsed
}

func parseIntOperators(data []byte, minTarget, maxTarget **int) bool {
	var value int
	if err := json.Unmarshal(data, &value); err == nil {
		if minTarget != nil {
			*minTarget = &value
		}
		if maxTarget != nil {
			*maxTarget = &value
		}
		return true
	}

	var operators map[string]json.RawMessage
	if err := json.Unmarshal(data, &operators); err != nil {
		return false
	}

	parsed := false
	if minTarget != nil {
		if raw, ok := operators["gte"]; ok {
			parsed = parseIntValue(raw, minTarget) || parsed
		}
		if raw, ok := operators["gt"]; ok {
			parsed = parseIntValue(raw, minTarget) || parsed
		}
		if raw, ok := operators["eq"]; ok {
			parsed = parseIntValue(raw, minTarget) || parsed
		}
	}
	if maxTarget != nil {
		if raw, ok := operators["lte"]; ok {
			parsed = parseIntValue(raw, maxTarget) || parsed
		}
		if raw, ok := operators["lt"]; ok {
			parsed = parseIntValue(raw, maxTarget) || parsed
		}
		if raw, ok := operators["eq"]; ok {
			parsed = parseIntValue(raw, maxTarget) || parsed
		}
	}
	return parsed
}

func normalizeStrings(values []string) []string {
	normalized := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.ToLower(strings.TrimSpace(value))
		if value == "" {
			continue
		}
		normalized = append(normalized, value)
	}
	return normalized
}
