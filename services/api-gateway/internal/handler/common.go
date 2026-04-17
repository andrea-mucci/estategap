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

func parseOptionalInt(raw string) (*int, error) {
	if raw == "" {
		return nil, nil
	}
	value, err := strconv.Atoi(raw)
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

func parseSortBy(raw string) (string, error) {
	if raw == "" {
		return "recency", nil
	}

	switch strings.ToLower(raw) {
	case "recency", "deal_score", "price", "price_m2", "days_on_market":
		return strings.ToLower(raw), nil
	default:
		return "", errors.New("invalid sort_by")
	}
}

func parseSortDir(raw string) string {
	if strings.EqualFold(raw, "asc") {
		return "asc"
	}
	return "desc"
}

func parseUUID(raw string) (*uuid.UUID, error) {
	if raw == "" {
		return nil, nil
	}

	value, err := uuid.Parse(raw)
	if err != nil {
		return nil, err
	}
	return &value, nil
}

type tokenPairResponse struct {
	AccessToken  string              `json:"access_token"`
	RefreshToken string              `json:"refresh_token"`
	ExpiresIn    int                 `json:"expires_in"`
	User         *userProfilePayload `json:"user,omitempty"`
}

type userProfilePayload struct {
	ID                  string                  `json:"id"`
	Email               string                  `json:"email"`
	DisplayName         *string                 `json:"display_name,omitempty"`
	AvatarURL           *string                 `json:"avatar_url,omitempty"`
	SubscriptionTier    models.SubscriptionTier `json:"subscription_tier"`
	PreferredCurrency   string                  `json:"preferred_currency"`
	OnboardingCompleted bool                    `json:"onboarding_completed"`
	Role                string                  `json:"role"`
	AlertLimit          int16                   `json:"alert_limit"`
	EmailVerified       bool                    `json:"email_verified"`
	CreatedAt           string                  `json:"created_at"`
}

type listingSummaryPayload struct {
	ID               string                   `json:"id"`
	Source           string                   `json:"source"`
	Country          string                   `json:"country"`
	City             *string                  `json:"city,omitempty"`
	Address          *string                  `json:"address,omitempty"`
	Latitude         *float64                 `json:"latitude,omitempty"`
	Longitude        *float64                 `json:"longitude,omitempty"`
	AskingPrice      *decimal.Decimal         `json:"asking_price,omitempty"`
	AskingPriceEUR   *decimal.Decimal         `json:"asking_price_eur,omitempty"`
	PriceConverted   *decimal.Decimal         `json:"price_converted,omitempty"`
	Currency         string                   `json:"currency"`
	PricePerM2EUR    *decimal.Decimal         `json:"price_per_m2_eur,omitempty"`
	AreaM2           *decimal.Decimal         `json:"area_m2,omitempty"`
	Bedrooms         *int16                   `json:"bedrooms,omitempty"`
	Bathrooms        *int16                   `json:"bathrooms,omitempty"`
	PropertyCategory *models.PropertyCategory `json:"property_category,omitempty"`
	PropertyType     *string                  `json:"property_type,omitempty"`
	DealScore        *decimal.Decimal         `json:"deal_score,omitempty"`
	DealTier         *models.DealTier         `json:"deal_tier,omitempty"`
	Status           models.ListingStatus     `json:"status"`
	DaysOnMarket     *int32                   `json:"days_on_market,omitempty"`
	PhotoURL         *string                  `json:"photo_url"`
	FirstSeenAt      string                   `json:"first_seen_at"`
}

type priceHistoryItem struct {
	OldPriceEUR *decimal.Decimal `json:"old_price_eur,omitempty"`
	NewPriceEUR *decimal.Decimal `json:"new_price_eur,omitempty"`
	ChangeType  string           `json:"change_type"`
	RecordedAt  string           `json:"recorded_at"`
}

type zoneSummaryStats struct {
	ZoneID           string  `json:"zone_id"`
	ZoneName         string  `json:"zone_name"`
	ListingCount     int64   `json:"listing_count"`
	MedianPriceM2EUR float64 `json:"median_price_m2_eur"`
	DealCount        int64   `json:"deal_count"`
}

type listingDetailPayload struct {
	listingSummaryPayload
	ZoneID         *string            `json:"zone_id,omitempty"`
	SourceURL      string             `json:"source_url"`
	UsableAreaM2   *decimal.Decimal   `json:"usable_area_m2,omitempty"`
	PlotAreaM2     *decimal.Decimal   `json:"plot_area_m2,omitempty"`
	FloorNumber    *int16             `json:"floor_number,omitempty"`
	YearBuilt      *int16             `json:"year_built,omitempty"`
	Condition      *string            `json:"condition,omitempty"`
	EnergyRating   *string            `json:"energy_rating,omitempty"`
	HasLift        *bool              `json:"has_lift,omitempty"`
	HasPool        *bool              `json:"has_pool,omitempty"`
	HasGarden      *bool              `json:"has_garden,omitempty"`
	EstimatedPrice *decimal.Decimal   `json:"estimated_price,omitempty"`
	ConfidenceLow  *decimal.Decimal   `json:"confidence_low,omitempty"`
	ConfidenceHigh *decimal.Decimal   `json:"confidence_high,omitempty"`
	ShapFeatures   json.RawMessage    `json:"shap_features,omitempty"`
	ModelVersion   *string            `json:"model_version,omitempty"`
	PublishedAt    *string            `json:"published_at,omitempty"`
	PriceHistory   []priceHistoryItem `json:"price_history"`
	Comparables    []string           `json:"comparable_ids"`
	ZoneStats      *zoneSummaryStats  `json:"zone_stats"`
}

type zoneDetailPayload struct {
	ID               string   `json:"id"`
	Name             string   `json:"name"`
	NameLocal        *string  `json:"name_local,omitempty"`
	Country          string   `json:"country"`
	Level            int16    `json:"level"`
	ParentID         *string  `json:"parent_id,omitempty"`
	Slug             *string  `json:"slug,omitempty"`
	AreaKm2          *float64 `json:"area_km2,omitempty"`
	ListingCount     int64    `json:"listing_count"`
	MedianPriceM2EUR float64  `json:"median_price_m2_eur"`
	DealCount        int64    `json:"deal_count"`
	PriceTrendPct    *float64 `json:"price_trend_pct,omitempty"`
}

type zoneMonthlyStatPayload struct {
	Month            string  `json:"month"`
	MedianPriceM2EUR float64 `json:"median_price_m2_eur"`
	ListingCount     int64   `json:"listing_count"`
	DealCount        int64   `json:"deal_count"`
	AvgDaysOnMarket  float64 `json:"avg_days_on_market"`
}

type zoneAnalyticsResponse struct {
	ZoneID string                   `json:"zone_id"`
	Months []zoneMonthlyStatPayload `json:"months"`
}

type zonePriceDistributionPayload struct {
	ZoneID       string    `json:"zone_id"`
	PricesEUR    []float64 `json:"prices_eur"`
	ListingCount int64     `json:"listing_count"`
}

type zoneComparePayload struct {
	Zones []zoneCompareItem `json:"zones"`
}

type zoneCompareItem struct {
	zoneDetailPayload
	LocalCurrency      string   `json:"local_currency"`
	MedianPriceM2Local *float64 `json:"median_price_m2_local,omitempty"`
}

type countryPayload struct {
	Code         string `json:"code"`
	Name         string `json:"name"`
	Currency     string `json:"currency"`
	ListingCount int64  `json:"listing_count"`
	DealCount    int64  `json:"deal_count"`
	PortalCount  int64  `json:"portal_count"`
}

type portalPayload struct {
	ID           string  `json:"id"`
	Name         string  `json:"name"`
	Country      string  `json:"country"`
	BaseURL      string  `json:"base_url"`
	Enabled      bool    `json:"enabled"`
	LastScrapeAt *string `json:"last_scrape_at"`
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
		ID:                  uuidString(user.ID),
		Email:               user.Email,
		DisplayName:         user.DisplayName,
		AvatarURL:           user.AvatarURL,
		SubscriptionTier:    user.SubscriptionTier,
		PreferredCurrency:   strings.ToUpper(strings.TrimSpace(defaultString(user.PreferredCurrency, "EUR"))),
		OnboardingCompleted: user.OnboardingCompleted,
		Role:                userRoleFromEmail(user.Email),
		AlertLimit:          user.AlertLimit,
		EmailVerified:       user.EmailVerified,
		CreatedAt:           timeString(user.CreatedAt),
	}
}

func listingSummaryFromModel(item *models.Listing, convertedPrice *decimal.Decimal, targetCurrency string) listingSummaryPayload {
	var priceConverted *decimal.Decimal
	if strings.ToUpper(targetCurrency) != "EUR" {
		priceConverted = convertedPrice
	}

	return listingSummaryPayload{
		ID:               uuidString(item.ID),
		Source:           item.Source,
		Country:          item.Country,
		City:             item.City,
		Address:          item.Address,
		Latitude:         item.Latitude,
		Longitude:        item.Longitude,
		AskingPrice:      item.AskingPrice,
		AskingPriceEUR:   item.AskingPriceEUR,
		PriceConverted:   priceConverted,
		Currency:         item.Currency,
		PricePerM2EUR:    item.PricePerM2EUR,
		AreaM2:           item.BuiltAreaM2,
		Bedrooms:         item.Bedrooms,
		Bathrooms:        item.Bathrooms,
		PropertyCategory: item.PropertyCategory,
		PropertyType:     item.PropertyType,
		DealScore:        item.DealScore,
		DealTier:         item.DealTier,
		Status:           item.Status,
		DaysOnMarket:     item.DaysOnMarket,
		PhotoURL:         nil,
		FirstSeenAt:      timeString(item.FirstSeenAt),
	}
}

func listingDetailFromResult(item *repository.ListingDetail) listingDetailPayload {
	comparables := make([]string, 0, len(item.Comparables))
	for _, comparableID := range item.Comparables {
		comparables = append(comparables, comparableID.String())
	}

	priceHistory := make([]priceHistoryItem, 0, len(item.PriceHistory))
	for _, entry := range item.PriceHistory {
		priceHistory = append(priceHistory, priceHistoryItem{
			OldPriceEUR: entry.OldPriceEUR,
			NewPriceEUR: entry.NewPriceEUR,
			ChangeType:  entry.ChangeType,
			RecordedAt:  timeString(entry.RecordedAt),
		})
	}

	var zoneStats *zoneSummaryStats
	if item.ZoneStats != nil {
		zoneStats = &zoneSummaryStats{
			ZoneID:           item.ZoneStats.ZoneID.String(),
			ZoneName:         item.ZoneStats.ZoneName,
			ListingCount:     item.ZoneStats.ListingCount,
			MedianPriceM2EUR: item.ZoneStats.MedianPriceM2EUR,
			DealCount:        item.ZoneStats.DealCount,
		}
	}

	return listingDetailPayload{
		listingSummaryPayload: listingSummaryFromModel(item.Listing, item.Listing.PriceConverted, "EUR"),
		ZoneID:                uuidStringPtr(item.Listing.ZoneID),
		SourceURL:             item.Listing.SourceURL,
		UsableAreaM2:          item.Listing.UsableAreaM2,
		PlotAreaM2:            item.Listing.PlotAreaM2,
		FloorNumber:           item.Listing.FloorNumber,
		YearBuilt:             item.Listing.YearBuilt,
		Condition:             item.Listing.Condition,
		EnergyRating:          item.Listing.EnergyRating,
		HasLift:               item.Listing.HasLift,
		HasPool:               item.Listing.HasPool,
		HasGarden:             item.Listing.HasGarden,
		EstimatedPrice:        item.Listing.EstimatedPrice,
		ConfidenceLow:         item.Listing.ConfidenceLow,
		ConfidenceHigh:        item.Listing.ConfidenceHigh,
		ShapFeatures:          trimShapFeatures(item.Listing.ShapFeatures),
		ModelVersion:          item.Listing.ModelVersion,
		PublishedAt:           timeStringPtr(item.Listing.PublishedAt),
		PriceHistory:          priceHistory,
		Comparables:           comparables,
		ZoneStats:             zoneStats,
	}
}

func zoneDetailFromModel(item *repository.ZoneWithStats) zoneDetailPayload {
	return zoneDetailPayload{
		ID:               item.ID.String(),
		Name:             item.Name,
		NameLocal:        item.NameLocal,
		Country:          item.CountryCode,
		Level:            item.Level,
		ParentID:         uuidUUIDStringPtr(item.ParentID),
		Slug:             item.Slug,
		AreaKm2:          item.AreaKm2,
		ListingCount:     item.ListingCount,
		MedianPriceM2EUR: item.MedianPriceM2EUR,
		DealCount:        item.DealCount,
		PriceTrendPct:    item.PriceTrendPct,
	}
}

func zoneAnalyticsFromMonths(zoneID uuid.UUID, months []repository.ZoneMonthStat) zoneAnalyticsResponse {
	payload := make([]zoneMonthlyStatPayload, 0, len(months))
	for _, month := range months {
		payload = append(payload, zoneMonthlyStatPayload{
			Month:            month.Month.UTC().Format(time.RFC3339),
			MedianPriceM2EUR: month.MedianPriceM2EUR,
			ListingCount:     month.ListingVolume,
			DealCount:        month.DealCount,
			AvgDaysOnMarket:  month.AvgDaysOnMarket,
		})
	}

	return zoneAnalyticsResponse{
		ZoneID: zoneID.String(),
		Months: payload,
	}
}

func zonePriceDistributionFromModel(item *repository.ZonePriceDistribution) zonePriceDistributionPayload {
	if item == nil {
		return zonePriceDistributionPayload{}
	}

	return zonePriceDistributionPayload{
		ZoneID:       item.ZoneID.String(),
		PricesEUR:    item.PricesEUR,
		ListingCount: item.ListingCount,
	}
}

func zoneCompareFromItems(items []repository.ZoneCompareItem) zoneComparePayload {
	payload := make([]zoneCompareItem, 0, len(items))
	for _, item := range items {
		payload = append(payload, zoneCompareItem{
			zoneDetailPayload: zoneDetailFromModel(&repository.ZoneWithStats{
				ID:               item.ID,
				Name:             item.Name,
				NameLocal:        item.NameLocal,
				CountryCode:      item.CountryCode,
				Level:            item.Level,
				ParentID:         item.ParentID,
				AreaKm2:          item.AreaKm2,
				Slug:             item.Slug,
				ListingCount:     item.ListingCount,
				MedianPriceM2EUR: item.MedianPriceM2EUR,
				DealCount:        item.DealCount,
				PriceTrendPct:    item.PriceTrendPct,
			}),
			LocalCurrency:      item.LocalCurrency,
			MedianPriceM2Local: item.MedianPriceM2Local,
		})
	}

	return zoneComparePayload{Zones: payload}
}

func countryFromSummary(item *repository.CountrySummary) countryPayload {
	return countryPayload{
		Code:         item.Code,
		Name:         item.Name,
		Currency:     item.Currency,
		ListingCount: item.ListingCount,
		DealCount:    item.DealCount,
		PortalCount:  item.PortalCount,
	}
}

func portalFromModel(item *models.Portal) portalPayload {
	return portalPayload{
		ID:           uuidString(item.ID),
		Name:         item.Name,
		Country:      item.CountryCode,
		BaseURL:      item.BaseURL,
		Enabled:      item.Enabled,
		LastScrapeAt: portalLastScrapeAt(item.Config),
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

func listEnvelope(data any, nextCursor string, hasMore bool, totalCount int64, currency string) map[string]any {
	meta := map[string]any{
		"total_count": totalCount,
	}
	if currency != "" {
		meta["currency"] = strings.ToUpper(currency)
	}

	return map[string]any{
		"data": data,
		"pagination": map[string]any{
			"next_cursor": nextCursor,
			"has_more":    hasMore,
		},
		"meta": meta,
	}
}

func uuidString(id pgtype.UUID) string {
	if !id.Valid {
		return ""
	}
	return uuid.UUID(id.Bytes).String()
}

func uuidStringPtr(value *pgtype.UUID) *string {
	if value == nil || !value.Valid {
		return nil
	}
	formatted := uuid.UUID(value.Bytes).String()
	return &formatted
}

func uuidUUIDStringPtr(value *uuid.UUID) *string {
	if value == nil {
		return nil
	}
	formatted := value.String()
	return &formatted
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

func trimShapFeatures(value json.RawMessage) json.RawMessage {
	if len(value) == 0 {
		return nil
	}

	var features []json.RawMessage
	if err := json.Unmarshal(value, &features); err != nil {
		return value
	}

	if len(features) > 5 {
		features = features[:5]
	}

	trimmed, err := json.Marshal(features)
	if err != nil {
		return value
	}

	return trimmed
}

func portalLastScrapeAt(value json.RawMessage) *string {
	if len(value) == 0 {
		return nil
	}

	var payload map[string]json.RawMessage
	if err := json.Unmarshal(value, &payload); err != nil {
		return nil
	}

	raw, ok := payload["last_scrape_at"]
	if !ok {
		return nil
	}

	var lastScrapeAt string
	if err := json.Unmarshal(raw, &lastScrapeAt); err != nil || lastScrapeAt == "" {
		return nil
	}

	if _, err := time.Parse(time.RFC3339, lastScrapeAt); err != nil {
		return nil
	}

	return &lastScrapeAt
}

func userRoleFromEmail(email string) string {
	if strings.HasSuffix(strings.ToLower(strings.TrimSpace(email)), "@estategap.com") {
		return "admin"
	}

	return "user"
}

func defaultString(value string, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}

	return value
}
