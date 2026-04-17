package handler

import (
	"context"
	"encoding/json"
	"errors"
	"math"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/estategap/libs/models"
	cachepkg "github.com/estategap/services/api-gateway/internal/cache"
	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type AlertRulesRepository interface {
	CountActiveRules(ctx context.Context, userID uuid.UUID) (int, error)
	CreateRule(ctx context.Context, input repository.AlertRuleInput) (*repository.AlertRule, error)
	ListRules(ctx context.Context, userID uuid.UUID, page, pageSize int, isActive *bool) ([]repository.AlertRule, int, error)
	GetRule(ctx context.Context, id, userID uuid.UUID) (*repository.AlertRule, error)
	UpdateRule(ctx context.Context, id, userID uuid.UUID, input repository.UpdateRuleInput) (*repository.AlertRule, error)
	DeleteRule(ctx context.Context, id, userID uuid.UUID) error
	ValidateZoneIDs(ctx context.Context, zoneIDs []uuid.UUID) ([]uuid.UUID, error)
	ListHistory(ctx context.Context, userID uuid.UUID, filter repository.HistoryFilter, page, pageSize int) ([]repository.AlertHistoryEntry, int, error)
}

type AlertRulesHandler struct {
	repo            AlertRulesRepository
	alertRulesCache cachepkg.AlertRulesCache
}

var tierAlertRuleLimits = map[string]int{
	"free":   0,
	"basic":  3,
	"pro":    -1,
	"global": -1,
	"api":    -1,
}

var allowedFilterFields = map[string]map[string]bool{
	"residential": {
		"price_eur":        true,
		"area_m2":          true,
		"bedrooms":         true,
		"bathrooms":        true,
		"floor":            true,
		"has_parking":      true,
		"has_elevator":     true,
		"property_type":    true,
		"listing_age_days": true,
	},
	"commercial": {
		"price_eur":        true,
		"area_m2":          true,
		"floor":            true,
		"has_parking":      true,
		"property_type":    true,
		"listing_age_days": true,
	},
	"industrial": {
		"price_eur":        true,
		"area_m2":          true,
		"property_type":    true,
		"listing_age_days": true,
	},
	"land": {
		"price_eur":        true,
		"area_m2":          true,
		"listing_age_days": true,
	},
}

type notificationChannel struct {
	Type       string  `json:"type"`
	WebhookURL *string `json:"webhook_url,omitempty"`
}

func NewAlertRulesHandler(repo AlertRulesRepository, cacheClient ...*cachepkg.Client) *AlertRulesHandler {
	handler := &AlertRulesHandler{repo: repo}
	if len(cacheClient) > 0 {
		handler.alertRulesCache = cachepkg.NewAlertRulesCache(cacheClient[0])
	}
	return handler
}

func (h *AlertRulesHandler) ListAlertRules(w http.ResponseWriter, r *http.Request) {
	userID, ok := alertUserID(w, r)
	if !ok {
		return
	}

	page, pageSize, ok := paginationParams(w, r)
	if !ok {
		return
	}

	var isActive *bool
	if raw := r.URL.Query().Get("is_active"); raw != "" {
		value, err := strconv.ParseBool(raw)
		if err != nil {
			writeFeatureError(w, http.StatusBadRequest, "is_active must be a boolean", "INVALID_QUERY_PARAM", nil)
			return
		}
		isActive = &value
	}

	type alertRuleListCacheEntry struct {
		Data       []alertRuleResponse `json:"data"`
		Pagination map[string]int      `json:"pagination"`
	}

	payload, hit, err := cachepkg.GetOrSetRequest(
		r.Context(),
		h.alertRulesCache.RequestCache,
		r,
		func() (alertRuleListCacheEntry, error) {
			items, total, err := h.repo.ListRules(r.Context(), userID, page, pageSize, isActive)
			if err != nil {
				return alertRuleListCacheEntry{}, err
			}

			rules := make([]alertRuleResponse, 0, len(items))
			for _, item := range items {
				rules = append(rules, alertRuleFromRepository(item))
			}

			return alertRuleListCacheEntry{
				Data:       rules,
				Pagination: paginationMeta(page, pageSize, total),
			}, nil
		},
	)
	if err != nil {
		writeFeatureError(w, http.StatusServiceUnavailable, "failed to load alert rules", "ALERT_RULES_UNAVAILABLE", nil)
		return
	}

	if hit {
		w.Header().Set("X-Cache", "HIT")
	} else {
		w.Header().Set("X-Cache", "MISS")
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"data":       payload.Data,
		"pagination": payload.Pagination,
	})
}

func (h *AlertRulesHandler) CreateAlertRule(w http.ResponseWriter, r *http.Request) {
	userID, ok := alertUserID(w, r)
	if !ok {
		return
	}

	req, rawFilter, rawChannels, ok := decodeCreateAlertRuleRequest(w, r)
	if !ok {
		return
	}

	tier := strings.ToLower(ctxkey.String(r.Context(), ctxkey.UserTier))
	limit := tierLimitFor(tier)
	if limit == 0 {
		writeFeatureError(
			w,
			http.StatusForbidden,
			"Alert rules are not available on the free tier. Upgrade to Basic or higher.",
			"TIER_NOT_PERMITTED",
			nil,
		)
		return
	}
	if limit > 0 {
		currentCount, err := h.repo.CountActiveRules(r.Context(), userID)
		if err != nil {
			writeFeatureError(w, http.StatusServiceUnavailable, "failed to check alert rule limits", "ALERT_RULES_UNAVAILABLE", nil)
			return
		}
		if currentCount >= limit {
			writeFeatureError(
				w,
				http.StatusUnprocessableEntity,
				"Maximum alert rules for Basic tier (3) reached",
				"TIER_LIMIT_REACHED",
				nil,
			)
			return
		}
	}

	zoneIDs, invalid, ok := validateAndParseZoneIDs(req.ZoneIDs)
	if !ok {
		writeFeatureError(w, http.StatusUnprocessableEntity, "zone_ids must contain valid UUIDs", "INVALID_ZONE_IDS", map[string]any{
			"invalid_ids": invalid,
		})
		return
	}

	invalidZoneIDs, err := h.repo.ValidateZoneIDs(r.Context(), zoneIDs)
	if err != nil {
		writeFeatureError(w, http.StatusServiceUnavailable, "failed to validate zone_ids", "ALERT_RULES_UNAVAILABLE", nil)
		return
	}
	if len(invalidZoneIDs) > 0 {
		writeFeatureError(w, http.StatusUnprocessableEntity, "zone_ids contains invalid or inactive zones", "INVALID_ZONE_IDS", map[string]any{
			"invalid_ids": uuidStrings(invalidZoneIDs),
		})
		return
	}

	disallowedFields := validateAlertFilter(req.Category, req.Filter)
	if len(disallowedFields) > 0 {
		writeFeatureError(
			w,
			http.StatusUnprocessableEntity,
			"filter contains fields not permitted for category '"+req.Category+"'",
			"INVALID_FILTER_FIELDS",
			map[string]any{"disallowed_fields": disallowedFields},
		)
		return
	}

	rule, err := h.repo.CreateRule(r.Context(), repository.AlertRuleInput{
		UserID:   userID,
		Name:     req.Name,
		ZoneIDs:  uuidStrings(zoneIDs),
		Category: req.Category,
		Filter:   rawFilter,
		Channels: rawChannels,
		IsActive: true,
	})
	if err != nil {
		writeFeatureError(w, http.StatusServiceUnavailable, "failed to create alert rule", "ALERT_RULES_UNAVAILABLE", nil)
		return
	}

	respond.JSON(w, http.StatusCreated, alertRuleFromRepository(*rule))
}

func (h *AlertRulesHandler) UpdateAlertRule(w http.ResponseWriter, r *http.Request) {
	userID, ok := alertUserID(w, r)
	if !ok {
		return
	}

	ruleID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeFeatureError(w, http.StatusBadRequest, "invalid alert rule id", "INVALID_ALERT_RULE_ID", nil)
		return
	}

	currentRule, err := h.repo.GetRule(r.Context(), ruleID, userID)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeFeatureError(w, http.StatusNotFound, "alert rule not found", "ALERT_RULE_NOT_FOUND", nil)
			return
		}
		writeFeatureError(w, http.StatusServiceUnavailable, "failed to load alert rule", "ALERT_RULES_UNAVAILABLE", nil)
		return
	}

	req, rawFilter, rawChannels, ok := decodeUpdateAlertRuleRequest(w, r)
	if !ok {
		return
	}

	if req.ZoneIDs != nil {
		zoneIDs, invalid, valid := validateAndParseZoneIDs(*req.ZoneIDs)
		if !valid {
			writeFeatureError(w, http.StatusUnprocessableEntity, "zone_ids must contain valid UUIDs", "INVALID_ZONE_IDS", map[string]any{
				"invalid_ids": invalid,
			})
			return
		}
		invalidZoneIDs, err := h.repo.ValidateZoneIDs(r.Context(), zoneIDs)
		if err != nil {
			writeFeatureError(w, http.StatusServiceUnavailable, "failed to validate zone_ids", "ALERT_RULES_UNAVAILABLE", nil)
			return
		}
		if len(invalidZoneIDs) > 0 {
			writeFeatureError(w, http.StatusUnprocessableEntity, "zone_ids contains invalid or inactive zones", "INVALID_ZONE_IDS", map[string]any{
				"invalid_ids": uuidStrings(invalidZoneIDs),
			})
			return
		}
	}

	if req.Filter != nil {
		disallowedFields := validateAlertFilter(currentRule.Category, *req.Filter)
		if len(disallowedFields) > 0 {
			writeFeatureError(
				w,
				http.StatusUnprocessableEntity,
				"filter contains fields not permitted for category '"+currentRule.Category+"'",
				"INVALID_FILTER_FIELDS",
				map[string]any{"disallowed_fields": disallowedFields},
			)
			return
		}
	}

	if req.IsActive != nil && *req.IsActive && !currentRule.IsActive {
		tier := strings.ToLower(ctxkey.String(r.Context(), ctxkey.UserTier))
		limit := tierLimitFor(tier)
		if limit == 0 {
			writeFeatureError(
				w,
				http.StatusForbidden,
				"Alert rules are not available on the free tier. Upgrade to Basic or higher.",
				"TIER_NOT_PERMITTED",
				nil,
			)
			return
		}
		if limit > 0 {
			currentCount, err := h.repo.CountActiveRules(r.Context(), userID)
			if err != nil {
				writeFeatureError(w, http.StatusServiceUnavailable, "failed to check alert rule limits", "ALERT_RULES_UNAVAILABLE", nil)
				return
			}
			if currentCount >= limit {
				writeFeatureError(
					w,
					http.StatusUnprocessableEntity,
					"Maximum alert rules for Basic tier (3) reached",
					"TIER_LIMIT_REACHED",
					nil,
				)
				return
			}
		}
	}

	update := repository.UpdateRuleInput{
		Name:     req.Name,
		IsActive: req.IsActive,
	}
	if req.ZoneIDs != nil {
		zoneIDs, _, _ := validateAndParseZoneIDs(*req.ZoneIDs)
		normalized := uuidStrings(zoneIDs)
		update.ZoneIDs = &normalized
	}
	if req.Filter != nil {
		update.Filter = &rawFilter
	}
	if req.Channels != nil {
		update.Channels = &rawChannels
	}

	rule, err := h.repo.UpdateRule(r.Context(), ruleID, userID, update)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeFeatureError(w, http.StatusNotFound, "alert rule not found", "ALERT_RULE_NOT_FOUND", nil)
			return
		}
		writeFeatureError(w, http.StatusServiceUnavailable, "failed to update alert rule", "ALERT_RULES_UNAVAILABLE", nil)
		return
	}

	respond.JSON(w, http.StatusOK, alertRuleFromRepository(*rule))
}

func (h *AlertRulesHandler) DeleteAlertRule(w http.ResponseWriter, r *http.Request) {
	userID, ok := alertUserID(w, r)
	if !ok {
		return
	}

	ruleID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeFeatureError(w, http.StatusBadRequest, "invalid alert rule id", "INVALID_ALERT_RULE_ID", nil)
		return
	}

	if err := h.repo.DeleteRule(r.Context(), ruleID, userID); err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeFeatureError(w, http.StatusNotFound, "alert rule not found", "ALERT_RULE_NOT_FOUND", nil)
			return
		}
		writeFeatureError(w, http.StatusServiceUnavailable, "failed to delete alert rule", "ALERT_RULES_UNAVAILABLE", nil)
		return
	}

	respond.NoContent(w)
}

func (h *AlertRulesHandler) ListAlertHistory(w http.ResponseWriter, r *http.Request) {
	h.listAlertHistory(w, r, nil)
}

func (h *AlertRulesHandler) ListAlertHistoryByRule(w http.ResponseWriter, r *http.Request) {
	ruleID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeFeatureError(w, http.StatusBadRequest, "invalid alert rule id", "INVALID_ALERT_RULE_ID", nil)
		return
	}
	h.listAlertHistory(w, r, &ruleID)
}

func (h *AlertRulesHandler) listAlertHistory(w http.ResponseWriter, r *http.Request, forcedRuleID *uuid.UUID) {
	userID, ok := alertUserID(w, r)
	if !ok {
		return
	}

	page, pageSize, ok := paginationParams(w, r)
	if !ok {
		return
	}

	filter := repository.HistoryFilter{RuleID: forcedRuleID}
	if forcedRuleID == nil && r.URL.Query().Get("rule_id") != "" {
		ruleID, err := uuid.Parse(r.URL.Query().Get("rule_id"))
		if err != nil {
			writeFeatureError(w, http.StatusBadRequest, "rule_id must be a UUID", "INVALID_QUERY_PARAM", nil)
			return
		}
		filter.RuleID = &ruleID
	}
	if status := strings.TrimSpace(strings.ToLower(r.URL.Query().Get("delivery_status"))); status != "" {
		switch status {
		case "pending", "delivered", "failed":
			filter.DeliveryStatus = &status
		default:
			writeFeatureError(w, http.StatusBadRequest, "delivery_status must be one of pending, delivered, or failed", "INVALID_QUERY_PARAM", nil)
			return
		}
	}
	if rawSince := strings.TrimSpace(r.URL.Query().Get("since")); rawSince != "" {
		since, err := time.Parse(time.RFC3339, rawSince)
		if err != nil {
			writeFeatureError(w, http.StatusBadRequest, "since must be RFC3339", "INVALID_QUERY_PARAM", nil)
			return
		}
		filter.Since = &since
	}

	items, total, err := h.repo.ListHistory(r.Context(), userID, filter, page, pageSize)
	if err != nil {
		writeFeatureError(w, http.StatusServiceUnavailable, "failed to load alert history", "ALERT_HISTORY_UNAVAILABLE", nil)
		return
	}

	payload := make([]alertHistoryResponse, 0, len(items))
	for _, item := range items {
		payload = append(payload, alertHistoryFromRepository(item))
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"data":       payload,
		"pagination": paginationMeta(page, pageSize, total),
	})
}

func validateAlertFilter(category string, filter map[string]map[string]any) []string {
	if len(filter) == 0 {
		return nil
	}

	allowed, ok := allowedFilterFields[strings.ToLower(category)]
	if !ok {
		return keysSorted(filter)
	}

	disallowed := make([]string, 0)
	for field := range filter {
		if !allowed[field] {
			disallowed = append(disallowed, field)
		}
	}
	return disallowed
}

type alertRuleResponse struct {
	ID        string                `json:"id"`
	Name      string                `json:"name"`
	ZoneIDs   []string              `json:"zone_ids"`
	Category  string                `json:"category"`
	Filter    map[string]any        `json:"filter"`
	Channels  []notificationChannel `json:"channels"`
	IsActive  bool                  `json:"is_active"`
	CreatedAt string                `json:"created_at"`
	UpdatedAt string                `json:"updated_at"`
}

type alertHistoryResponse struct {
	ID             string  `json:"id"`
	RuleID         string  `json:"rule_id"`
	RuleName       string  `json:"rule_name"`
	ListingID      string  `json:"listing_id"`
	TriggeredAt    string  `json:"triggered_at"`
	Channel        string  `json:"channel"`
	DeliveryStatus string  `json:"delivery_status"`
	DeliveredAt    *string `json:"delivered_at,omitempty"`
	ErrorDetail    *string `json:"error_detail,omitempty"`
}

type alertErrorResponse struct {
	Error   string         `json:"error"`
	Code    string         `json:"code"`
	Details map[string]any `json:"details,omitempty"`
}

type createAlertRuleRequest struct {
	Name     string                    `json:"name"`
	ZoneIDs  []string                  `json:"zone_ids"`
	Category string                    `json:"category"`
	Filter   map[string]map[string]any `json:"filter"`
	Channels []notificationChannel     `json:"channels"`
}

type updateAlertRuleRequest struct {
	Name     *string                    `json:"name"`
	ZoneIDs  *[]string                  `json:"zone_ids"`
	Filter   *map[string]map[string]any `json:"filter"`
	Channels *[]notificationChannel     `json:"channels"`
	IsActive *bool                      `json:"is_active"`
}

func decodeCreateAlertRuleRequest(w http.ResponseWriter, r *http.Request) (createAlertRuleRequest, json.RawMessage, json.RawMessage, bool) {
	var req createAlertRuleRequest
	if err := decodeJSON(r, &req); err != nil {
		writeFeatureError(w, http.StatusBadRequest, "invalid request body", "INVALID_REQUEST_BODY", nil)
		return createAlertRuleRequest{}, nil, nil, false
	}

	req.Name = strings.TrimSpace(req.Name)
	req.Category = strings.ToLower(strings.TrimSpace(req.Category))
	if req.Name == "" || req.Category == "" || len(req.ZoneIDs) == 0 || len(req.Channels) == 0 {
		writeFeatureError(w, http.StatusBadRequest, "name, zone_ids, category, and channels are required", "INVALID_REQUEST_BODY", nil)
		return createAlertRuleRequest{}, nil, nil, false
	}
	if _, ok := allowedFilterFields[req.Category]; !ok {
		writeFeatureError(w, http.StatusUnprocessableEntity, "category must be one of residential, commercial, industrial, or land", "INVALID_CATEGORY", nil)
		return createAlertRuleRequest{}, nil, nil, false
	}

	rawFilter, err := json.Marshal(req.Filter)
	if err != nil {
		writeFeatureError(w, http.StatusBadRequest, "invalid filter payload", "INVALID_REQUEST_BODY", nil)
		return createAlertRuleRequest{}, nil, nil, false
	}
	rawChannels, err := json.Marshal(req.Channels)
	if err != nil {
		writeFeatureError(w, http.StatusBadRequest, "invalid channels payload", "INVALID_REQUEST_BODY", nil)
		return createAlertRuleRequest{}, nil, nil, false
	}
	return req, rawFilter, rawChannels, true
}

func decodeUpdateAlertRuleRequest(w http.ResponseWriter, r *http.Request) (updateAlertRuleRequest, json.RawMessage, json.RawMessage, bool) {
	var req updateAlertRuleRequest
	if err := decodeJSON(r, &req); err != nil {
		writeFeatureError(w, http.StatusBadRequest, "invalid request body", "INVALID_REQUEST_BODY", nil)
		return updateAlertRuleRequest{}, nil, nil, false
	}

	if req.Name != nil {
		trimmed := strings.TrimSpace(*req.Name)
		req.Name = &trimmed
		if trimmed == "" {
			writeFeatureError(w, http.StatusBadRequest, "name cannot be empty", "INVALID_REQUEST_BODY", nil)
			return updateAlertRuleRequest{}, nil, nil, false
		}
	}
	if req.ZoneIDs != nil && len(*req.ZoneIDs) == 0 {
		writeFeatureError(w, http.StatusBadRequest, "zone_ids cannot be empty", "INVALID_REQUEST_BODY", nil)
		return updateAlertRuleRequest{}, nil, nil, false
	}
	if req.Channels != nil && len(*req.Channels) == 0 {
		writeFeatureError(w, http.StatusBadRequest, "channels cannot be empty", "INVALID_REQUEST_BODY", nil)
		return updateAlertRuleRequest{}, nil, nil, false
	}

	var rawFilter json.RawMessage
	if req.Filter != nil {
		payload, err := json.Marshal(*req.Filter)
		if err != nil {
			writeFeatureError(w, http.StatusBadRequest, "invalid filter payload", "INVALID_REQUEST_BODY", nil)
			return updateAlertRuleRequest{}, nil, nil, false
		}
		rawFilter = payload
	}

	var rawChannels json.RawMessage
	if req.Channels != nil {
		payload, err := json.Marshal(*req.Channels)
		if err != nil {
			writeFeatureError(w, http.StatusBadRequest, "invalid channels payload", "INVALID_REQUEST_BODY", nil)
			return updateAlertRuleRequest{}, nil, nil, false
		}
		rawChannels = payload
	}

	return req, rawFilter, rawChannels, true
}

func alertRuleFromRepository(item repository.AlertRule) alertRuleResponse {
	return alertRuleResponse{
		ID:        item.ID.String(),
		Name:      item.Name,
		ZoneIDs:   append([]string(nil), item.ZoneIDs...),
		Category:  item.Category,
		Filter:    decodeJSONObject(item.Filter),
		Channels:  decodeNotificationChannels(item.Channels),
		IsActive:  item.IsActive,
		CreatedAt: item.CreatedAt.UTC().Format(time.RFC3339),
		UpdatedAt: item.UpdatedAt.UTC().Format(time.RFC3339),
	}
}

func alertHistoryFromRepository(item repository.AlertHistoryEntry) alertHistoryResponse {
	resp := alertHistoryResponse{
		ID:             item.ID.String(),
		RuleID:         item.RuleID.String(),
		RuleName:       item.RuleName,
		ListingID:      item.ListingID.String(),
		TriggeredAt:    item.TriggeredAt.UTC().Format(time.RFC3339),
		Channel:        item.Channel,
		DeliveryStatus: item.DeliveryStatus,
		ErrorDetail:    item.ErrorDetail,
	}
	if item.DeliveredAt != nil {
		value := item.DeliveredAt.UTC().Format(time.RFC3339)
		resp.DeliveredAt = &value
	}
	return resp
}

func decodeJSONObject(raw json.RawMessage) map[string]any {
	if len(raw) == 0 {
		return map[string]any{}
	}
	var value map[string]any
	if err := json.Unmarshal(raw, &value); err != nil {
		return map[string]any{}
	}
	return value
}

func decodeNotificationChannels(raw json.RawMessage) []notificationChannel {
	if len(raw) == 0 {
		return nil
	}
	var value []notificationChannel
	if err := json.Unmarshal(raw, &value); err != nil {
		return nil
	}
	return value
}

func paginationMeta(page, pageSize, total int) map[string]int {
	totalPages := 0
	if total > 0 {
		totalPages = int(math.Ceil(float64(total) / float64(pageSize)))
	}
	return map[string]int{
		"page":        page,
		"page_size":   pageSize,
		"total":       total,
		"total_pages": totalPages,
	}
}

func paginationParams(w http.ResponseWriter, r *http.Request) (int, int, bool) {
	page := 1
	if raw := r.URL.Query().Get("page"); raw != "" {
		value, err := strconv.Atoi(raw)
		if err != nil || value < 1 {
			writeFeatureError(w, http.StatusBadRequest, "page must be >= 1", "INVALID_QUERY_PARAM", nil)
			return 0, 0, false
		}
		page = value
	}

	pageSize := 20
	if raw := r.URL.Query().Get("page_size"); raw != "" {
		value, err := strconv.Atoi(raw)
		if err != nil || value < 1 || value > 100 {
			writeFeatureError(w, http.StatusBadRequest, "page_size must be between 1 and 100", "INVALID_QUERY_PARAM", nil)
			return 0, 0, false
		}
		pageSize = value
	}

	return page, pageSize, true
}

func alertUserID(w http.ResponseWriter, r *http.Request) (uuid.UUID, bool) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeFeatureError(w, http.StatusUnauthorized, "missing user", "UNAUTHORIZED", nil)
		return uuid.Nil, false
	}
	return userID, true
}

func tierLimitFor(tier string) int {
	if limit, ok := tierAlertRuleLimits[tier]; ok {
		return limit
	}
	return tierAlertRuleLimits[string(models.SubscriptionTierFree)]
}

func validateAndParseZoneIDs(zoneIDs []string) ([]uuid.UUID, []string, bool) {
	parsed := make([]uuid.UUID, 0, len(zoneIDs))
	invalid := make([]string, 0)
	for _, raw := range zoneIDs {
		id, err := uuid.Parse(strings.TrimSpace(raw))
		if err != nil {
			invalid = append(invalid, raw)
			continue
		}
		parsed = append(parsed, id)
	}
	return parsed, invalid, len(invalid) == 0
}

func uuidStrings(ids []uuid.UUID) []string {
	values := make([]string, 0, len(ids))
	for _, id := range ids {
		values = append(values, id.String())
	}
	return values
}

func keysSorted(values map[string]map[string]any) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func writeFeatureError(w http.ResponseWriter, status int, message, code string, details map[string]any) {
	respond.JSON(w, status, alertErrorResponse{
		Error:   message,
		Code:    code,
		Details: details,
	})
}
