package handler

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/mail"
	"strconv"
	"strings"
	"time"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/shopspring/decimal"
)

func requestID(ctx context.Context) string {
	return respond.RequestIDFromContext(ctx)
}

func writeError(w http.ResponseWriter, r *http.Request, status int, message string) {
	respond.Error(w, status, message, requestID(r.Context()))
}

func decodeJSON(r *http.Request, dest any) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	return dec.Decode(dest)
}

func parseUserID(ctx context.Context) (uuid.UUID, error) {
	value := ctxkey.String(ctx, ctxkey.UserID)
	if value == "" {
		return uuid.Nil, errors.New("missing user id")
	}
	return uuid.Parse(value)
}

func validateEmail(email string) bool {
	_, err := mail.ParseAddress(email)
	return err == nil
}

func parseLimit(raw string) int {
	if raw == "" {
		return 20
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 20
	}
	if value < 1 {
		return 1
	}
	if value > 100 {
		return 100
	}
	return value
}

func parseOptionalFloat(raw string) (*float64, error) {
	if raw == "" {
		return nil, nil
	}
	value, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return nil, err
	}
	return &value, nil
}

func parsePropertyCategory(raw string) (*models.PropertyCategory, error) {
	if raw == "" {
		return nil, nil
	}
	value := models.PropertyCategory(strings.ToLower(raw))
	switch value {
	case models.PropertyCategoryResidential, models.PropertyCategoryCommercial, models.PropertyCategoryIndustrial, models.PropertyCategoryLand:
		return &value, nil
	default:
		return nil, errors.New("invalid property_category")
	}
}

func parseDealTier(raw string) (*models.DealTier, error) {
	if raw == "" {
		return nil, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return nil, err
	}
	tier := models.DealTier(value)
	switch tier {
	case models.DealTierGreatDeal, models.DealTierGoodDeal, models.DealTierFair, models.DealTierOverpriced:
		return &tier, nil
	default:
		return nil, errors.New("invalid deal_tier")
	}
}

func parseListingStatus(raw string) (*models.ListingStatus, error) {
	if raw == "" {
		status := models.ListingStatusActive
		return &status, nil
	}
	value := models.ListingStatus(strings.ToLower(raw))
	switch value {
	case models.ListingStatusActive, models.ListingStatusDelisted, models.ListingStatusSold:
		return &value, nil
	default:
		return nil, errors.New("invalid status")
	}
}

func parsePeriodDays(raw string) (int, error) {
	if raw == "" {
		return 30, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 0, err
	}
	switch value {
	case 7, 30, 90, 365:
		return value, nil
	default:
		return 0, errors.New("invalid period_days")
	}
}

type tokenPairResponse struct {
	AccessToken  string              `json:"access_token"`
	RefreshToken string              `json:"refresh_token"`
	ExpiresIn    int                 `json:"expires_in"`
	User         *userProfilePayload `json:"user,omitempty"`
}

type userProfilePayload struct {
	ID               string                  `json:"id"`
	Email            string                  `json:"email"`
	DisplayName      *string                 `json:"display_name,omitempty"`
	AvatarURL        *string                 `json:"avatar_url,omitempty"`
	SubscriptionTier models.SubscriptionTier `json:"subscription_tier"`
	AlertLimit       int16                   `json:"alert_limit"`
	EmailVerified    bool                    `json:"email_verified"`
	CreatedAt        string                  `json:"created_at"`
}

type listingPayload struct {
	ID               string                   `json:"id"`
	Country          string                   `json:"country"`
	City             *string                  `json:"city,omitempty"`
	Address          *string                  `json:"address,omitempty"`
	AskingPrice      *decimal.Decimal         `json:"asking_price,omitempty"`
	AskingPriceEUR   *decimal.Decimal         `json:"asking_price_eur,omitempty"`
	PricePerM2EUR    *decimal.Decimal         `json:"price_per_m2_eur,omitempty"`
	PropertyCategory *models.PropertyCategory `json:"property_category,omitempty"`
	BuiltAreaM2      *decimal.Decimal         `json:"built_area_m2,omitempty"`
	Bedrooms         *int16                   `json:"bedrooms,omitempty"`
	Bathrooms        *int16                   `json:"bathrooms,omitempty"`
	DealScore        *decimal.Decimal         `json:"deal_score,omitempty"`
	DealTier         *models.DealTier         `json:"deal_tier,omitempty"`
	Status           models.ListingStatus     `json:"status"`
	ImagesCount      int16                    `json:"images_count"`
	FirstSeenAt      string                   `json:"first_seen_at"`
}

type zonePayload struct {
	ID               string   `json:"id"`
	Name             string   `json:"name"`
	Country          string   `json:"country"`
	Region           *string  `json:"region,omitempty"`
	City             *string  `json:"city,omitempty"`
	ListingCount     int      `json:"listing_count,omitempty"`
	AvgPricePerM2EUR *float64 `json:"avg_price_per_m2_eur,omitempty"`
}

type alertRulePayload struct {
	ID              string          `json:"id"`
	Name            string          `json:"name"`
	Filters         json.RawMessage `json:"filters"`
	Channels        json.RawMessage `json:"channels"`
	Active          bool            `json:"active"`
	LastTriggeredAt *string         `json:"last_triggered_at,omitempty"`
	TriggerCount    int32           `json:"trigger_count"`
	CreatedAt       string          `json:"created_at"`
}

type alertEventPayload struct {
	ID           string `json:"id"`
	TriggeredAt  string `json:"triggered_at"`
	ListingCount int64  `json:"listing_count"`
}

type zoneAnalyticsPayload struct {
	ZoneID           string  `json:"zone_id"`
	PeriodDays       int     `json:"period_days"`
	AvgPricePerM2EUR float64 `json:"avg_price_per_m2_eur"`
	MedianPriceEUR   float64 `json:"median_price_eur"`
	ListingCount     int64   `json:"listing_count"`
	PriceChangePct   float64 `json:"price_change_pct"`
}

func tokenPairWithUser(pairAccess, pairRefresh string, expiresIn int, user *models.User) tokenPairResponse {
	return tokenPairResponse{
		AccessToken:  pairAccess,
		RefreshToken: pairRefresh,
		ExpiresIn:    expiresIn,
		User:         userPayload(user),
	}
}

func userPayload(user *models.User) *userProfilePayload {
	if user == nil {
		return nil
	}
	return &userProfilePayload{
		ID:               uuidString(user.ID),
		Email:            user.Email,
		DisplayName:      user.DisplayName,
		AvatarURL:        user.AvatarURL,
		SubscriptionTier: user.SubscriptionTier,
		AlertLimit:       user.AlertLimit,
		EmailVerified:    user.EmailVerified,
		CreatedAt:        timeString(user.CreatedAt),
	}
}

func listingFromModel(item *models.Listing) listingPayload {
	return listingPayload{
		ID:               uuidString(item.ID),
		Country:          item.Country,
		City:             item.City,
		Address:          item.Address,
		AskingPrice:      item.AskingPrice,
		AskingPriceEUR:   item.AskingPriceEUR,
		PricePerM2EUR:    item.PricePerM2EUR,
		PropertyCategory: item.PropertyCategory,
		BuiltAreaM2:      item.BuiltAreaM2,
		Bedrooms:         item.Bedrooms,
		Bathrooms:        item.Bathrooms,
		DealScore:        item.DealScore,
		DealTier:         item.DealTier,
		Status:           item.Status,
		ImagesCount:      item.ImagesCount,
		FirstSeenAt:      timeString(item.FirstSeenAt),
	}
}

func zoneFromModel(item *models.Zone) zonePayload {
	return zonePayload{
		ID:      uuidString(item.ID),
		Name:    item.Name,
		Country: item.CountryCode,
	}
}

func zoneAnalyticsFromRepo(item *repository.ZoneAnalytics) zoneAnalyticsPayload {
	return zoneAnalyticsPayload{
		ZoneID:           item.ZoneID.String(),
		PeriodDays:       item.PeriodDays,
		AvgPricePerM2EUR: item.AvgPricePerM2EUR,
		MedianPriceEUR:   item.MedianPriceEUR,
		ListingCount:     item.ListingCount,
		PriceChangePct:   item.PriceChangePercent,
	}
}

func alertFromModel(item *models.AlertRule) alertRulePayload {
	return alertRulePayload{
		ID:              uuidString(item.ID),
		Name:            item.Name,
		Filters:         item.Filters,
		Channels:        item.Channels,
		Active:          item.Active,
		LastTriggeredAt: timeStringPtr(item.LastTriggeredAt),
		TriggerCount:    item.TriggerCount,
		CreatedAt:       timeString(item.CreatedAt),
	}
}

func alertEventFromRepo(item repository.AlertEvent) alertEventPayload {
	return alertEventPayload{
		ID:           item.ID.String(),
		TriggeredAt:  item.TriggeredAt,
		ListingCount: item.ListingCount,
	}
}

func uuidString(id pgtype.UUID) string {
	if !id.Valid {
		return ""
	}
	return uuid.UUID(id.Bytes).String()
}

func timeString(value pgtype.Timestamptz) string {
	if !value.Valid {
		return ""
	}
	return value.Time.UTC().Format(time.RFC3339Nano)
}

func timeStringPtr(value *pgtype.Timestamptz) *string {
	if value == nil || !value.Valid {
		return nil
	}
	formatted := value.Time.UTC().Format(time.RFC3339Nano)
	return &formatted
}
