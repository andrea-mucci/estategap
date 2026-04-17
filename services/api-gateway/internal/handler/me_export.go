package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/redis/go-redis/v9"
)

type MeExportHandler struct {
	usersRepo      *repository.UsersRepo
	alertRulesRepo *repository.AlertRulesRepo
	portfolioRepo  *repository.PortfolioRepo
	redisClient    *redis.Client
}

type conversationExport struct {
	SessionID string                  `json:"session_id"`
	Messages  []conversationExportMsg `json:"messages"`
}

type conversationExportMsg struct {
	Role      string `json:"role"`
	Content   string `json:"content"`
	Timestamp string `json:"timestamp"`
}

type alertRuleExport struct {
	ID        string                `json:"id"`
	Name      string                `json:"name"`
	ZoneIDs   []string              `json:"zone_ids"`
	Category  string                `json:"category"`
	Filters   map[string]any        `json:"filters"`
	Channels  []notificationChannel `json:"channels"`
	CreatedAt string                `json:"created_at"`
	IsActive  bool                  `json:"is_active"`
}

type portfolioPropertyExport struct {
	ID           string   `json:"id"`
	Address      string   `json:"address"`
	Country      string   `json:"country"`
	ZoneID       *string  `json:"zone_id,omitempty"`
	PurchaseDate string   `json:"purchase_date"`
	Notes        *string  `json:"notes,omitempty"`
	AreaM2       *float64 `json:"area_m2,omitempty"`
	AddedAt      string   `json:"added_at"`
}

type alertHistoryExport struct {
	ID          string `json:"id"`
	RuleID      string `json:"rule_id"`
	ListingID   string `json:"listing_id"`
	TriggeredAt string `json:"triggered_at"`
	Channel     string `json:"channel"`
}

func NewMeExportHandler(
	usersRepo *repository.UsersRepo,
	alertRulesRepo *repository.AlertRulesRepo,
	portfolioRepo *repository.PortfolioRepo,
	redisClient *redis.Client,
) *MeExportHandler {
	return &MeExportHandler{
		usersRepo:      usersRepo,
		alertRulesRepo: alertRulesRepo,
		portfolioRepo:  portfolioRepo,
		redisClient:    redisClient,
	}
}

func (h *MeExportHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	user, err := h.usersRepo.GetUserByID(r.Context(), userID)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "user not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load user profile")
		return
	}

	alertRules, _, err := h.alertRulesRepo.ListRules(r.Context(), userID, 1, 100, nil)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load alert rules")
		return
	}

	alertHistory, _, err := h.alertRulesRepo.ListHistory(r.Context(), userID, repository.HistoryFilter{}, 1, 1000)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load alert history")
		return
	}

	portfolioProperties, _, err := h.portfolioRepo.ListPortfolioProperties(r.Context(), userID)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load portfolio properties")
		return
	}

	conversations, err := exportConversations(r.Context(), h.redisClient, userID.String())
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load conversation history")
		return
	}

	rulesPayload := make([]alertRuleExport, 0, len(alertRules))
	for _, item := range alertRules {
		rulesPayload = append(rulesPayload, alertRuleExport{
			ID:        item.ID.String(),
			Name:      item.Name,
			ZoneIDs:   append([]string(nil), item.ZoneIDs...),
			Category:  item.Category,
			Filters:   decodeJSONObject(item.Filter),
			Channels:  decodeNotificationChannels(item.Channels),
			CreatedAt: item.CreatedAt.UTC().Format(time.RFC3339),
			IsActive:  item.IsActive,
		})
	}

	portfolioPayload := make([]portfolioPropertyExport, 0, len(portfolioProperties))
	for _, item := range portfolioProperties {
		portfolioPayload = append(portfolioPayload, portfolioPropertyExport{
			ID:           item.ID,
			Address:      item.Address,
			Country:      item.Country,
			ZoneID:       item.ZoneID,
			PurchaseDate: item.PurchaseDate,
			Notes:        item.Notes,
			AreaM2:       item.AreaM2,
			AddedAt:      item.CreatedAt,
		})
	}

	historyPayload := make([]alertHistoryExport, 0, len(alertHistory))
	for _, item := range alertHistory {
		historyPayload = append(historyPayload, alertHistoryExport{
			ID:          item.ID.String(),
			RuleID:      item.RuleID.String(),
			ListingID:   item.ListingID.String(),
			TriggeredAt: item.TriggeredAt.UTC().Format(time.RFC3339),
			Channel:     item.Channel,
		})
	}

	profileName := strings.TrimSpace(defaultString(stringPtrValue(user.DisplayName), user.Email))
	filenameDate := time.Now().UTC().Format("2006-01-02")
	w.Header().Set("Content-Disposition", `attachment; filename="estategap-export-`+filenameDate+`.json"`)

	respond.JSON(w, http.StatusOK, map[string]any{
		"exported_at":    time.Now().UTC().Format(time.RFC3339),
		"schema_version": "1",
		"profile": map[string]any{
			"id":                uuidString(user.ID),
			"email":             user.Email,
			"name":              profileName,
			"avatar_url":        user.AvatarURL,
			"created_at":        timeString(user.CreatedAt),
			"subscription_tier": string(user.SubscriptionTier),
		},
		"alert_rules":          rulesPayload,
		"portfolio_properties": portfolioPayload,
		"alert_history":        historyPayload,
		"conversations":        conversations,
	})
}

func exportConversations(ctx context.Context, redisClient *redis.Client, userID string) ([]conversationExport, error) {
	if redisClient == nil {
		return nil, nil
	}

	keys, err := matchingConversationKeys(ctx, redisClient, userID)
	if err != nil {
		return nil, err
	}

	conversations := make([]conversationExport, 0, len(keys))
	for _, key := range keys {
		sessionID := strings.TrimPrefix(key, "conv:")
		rawMessages, err := redisClient.LRange(ctx, key+":messages", 0, -1).Result()
		if err != nil && !errors.Is(err, redis.Nil) {
			return nil, err
		}

		messages := make([]conversationExportMsg, 0, len(rawMessages))
		for _, rawMessage := range rawMessages {
			var payload conversationExportMsg
			if err := json.Unmarshal([]byte(rawMessage), &payload); err != nil {
				continue
			}
			messages = append(messages, payload)
		}

		conversations = append(conversations, conversationExport{
			SessionID: sessionID,
			Messages:  messages,
		})
	}

	return conversations, nil
}
