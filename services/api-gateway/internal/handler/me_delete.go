package handler

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/estategap/services/api-gateway/internal/service"
	"github.com/redis/go-redis/v9"
)

type MeDeleteHandler struct {
	usersRepo   *repository.UsersRepo
	authService *service.AuthService
	redisClient *redis.Client
}

func NewMeDeleteHandler(
	usersRepo *repository.UsersRepo,
	authService *service.AuthService,
	redisClient *redis.Client,
) *MeDeleteHandler {
	return &MeDeleteHandler{
		usersRepo:   usersRepo,
		authService: authService,
		redisClient: redisClient,
	}
}

func (h *MeDeleteHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	var req struct {
		Confirm string `json:"confirm"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.Confirm != "delete my account" {
		writeError(w, r, http.StatusBadRequest, "confirmation string must be exactly 'delete my account'")
		return
	}

	user, err := h.usersRepo.GetUserByID(r.Context(), userID)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusConflict, "account is already pending deletion")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load user")
		return
	}

	if err := h.usersRepo.AnonymiseUser(r.Context(), userID); err != nil {
		if errors.Is(err, repository.ErrConflict) {
			writeError(w, r, http.StatusConflict, "account is already pending deletion")
			return
		}
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "user not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to schedule account deletion")
		return
	}

	if err := h.authService.RevokeUserSessions(r.Context(), userID); err != nil {
		slog.Warn("failed to revoke user sessions", "user_id", userID.String(), "error", err)
	}
	if err := deleteConversationSessions(r.Context(), h.redisClient, userID.String()); err != nil {
		slog.Warn("failed to delete conversation sessions", "user_id", userID.String(), "error", err)
	}

	go slog.Info(
		"account deletion confirmation pending notification",
		"user_id",
		userID.String(),
		"email",
		user.Email,
	)

	respond.JSON(w, http.StatusAccepted, map[string]string{
		"message":                     "Account deletion scheduled. PII anonymised immediately.",
		"scheduled_hard_delete_after": time.Now().UTC().AddDate(0, 0, 30).Format("2006-01-02"),
	})
}

func deleteConversationSessions(ctx context.Context, redisClient *redis.Client, userID string) error {
	if redisClient == nil {
		return nil
	}

	keys, err := matchingConversationKeys(ctx, redisClient, userID)
	if err != nil {
		return err
	}

	for _, key := range keys {
		if err := redisClient.Del(ctx, key, key+":messages").Err(); err != nil {
			return err
		}
	}

	return nil
}

func matchingConversationKeys(ctx context.Context, redisClient *redis.Client, userID string) ([]string, error) {
	cursor := uint64(0)
	keys := make([]string, 0)
	for {
		page, nextCursor, err := redisClient.Scan(ctx, cursor, "conv:*", 100).Result()
		if err != nil {
			return nil, err
		}

		for _, key := range page {
			if strings.HasSuffix(key, ":messages") {
				continue
			}

			data, err := redisClient.HGetAll(ctx, key).Result()
			if err != nil {
				if errors.Is(err, redis.Nil) {
					continue
				}
				return nil, err
			}
			if data["user_id"] == userID {
				keys = append(keys, key)
			}
		}

		cursor = nextCursor
		if cursor == 0 {
			break
		}
	}
	return keys, nil
}

func stringPtrValue(value *string) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(*value)
}
