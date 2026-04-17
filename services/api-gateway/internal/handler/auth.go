package handler

import (
	"errors"
	"net/http"
	"strings"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/estategap/services/api-gateway/internal/service"
	"github.com/google/uuid"
)

type AuthHandler struct {
	authService *service.AuthService
	usersRepo   *repository.UsersRepo
}

func NewAuthHandler(authService *service.AuthService, usersRepo *repository.UsersRepo) *AuthHandler {
	return &AuthHandler{authService: authService, usersRepo: usersRepo}
}

func (h *AuthHandler) Register(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Email    string `json:"email"`
		Password string `json:"password"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}
	req.Email = strings.TrimSpace(strings.ToLower(req.Email))
	if !validateEmail(req.Email) || len(req.Password) < 8 {
		writeError(w, r, http.StatusUnprocessableEntity, "invalid email or password")
		return
	}

	hash, err := h.authService.HashPassword(req.Password)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to hash password")
		return
	}

	user, err := h.usersRepo.CreateUser(r.Context(), req.Email, hash)
	if err != nil {
		if errors.Is(err, repository.ErrConflict) {
			writeError(w, r, http.StatusConflict, "email already registered")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to create user")
		return
	}

	pair, err := h.authService.IssueTokenPair(r.Context(), user)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to issue tokens")
		return
	}

	respond.JSON(w, http.StatusCreated, tokenPairWithUser(pair.AccessToken, pair.RefreshToken, pair.ExpiresIn, user))
}

func (h *AuthHandler) Login(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Email    string `json:"email"`
		Password string `json:"password"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}

	user, err := h.usersRepo.GetUserByEmail(r.Context(), strings.TrimSpace(strings.ToLower(req.Email)))
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "invalid credentials")
		return
	}
	if user.PasswordHash == nil || !h.authService.CheckPassword(*user.PasswordHash, req.Password) {
		writeError(w, r, http.StatusUnauthorized, "invalid credentials")
		return
	}

	userID, err := parseUserIDFromModel(user)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "invalid user record")
		return
	}
	if err := h.usersRepo.UpdateLastLogin(r.Context(), userID); err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to update last login")
		return
	}

	pair, err := h.authService.IssueTokenPair(r.Context(), user)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to issue tokens")
		return
	}

	respond.JSON(w, http.StatusOK, tokenPairWithUser(pair.AccessToken, pair.RefreshToken, pair.ExpiresIn, user))
}

func (h *AuthHandler) Refresh(w http.ResponseWriter, r *http.Request) {
	var req struct {
		RefreshToken string `json:"refresh_token"`
	}
	if err := decodeJSON(r, &req); err != nil || strings.TrimSpace(req.RefreshToken) == "" {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}

	userID, err := h.authService.ConsumeRefreshToken(r.Context(), strings.TrimSpace(req.RefreshToken))
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "invalid refresh token")
		return
	}

	user, err := h.usersRepo.GetUserByID(r.Context(), userID)
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "invalid refresh token")
		return
	}

	pair, err := h.authService.IssueTokenPair(r.Context(), user)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to issue tokens")
		return
	}

	respond.JSON(w, http.StatusOK, tokenPairResponse{
		AccessToken:  pair.AccessToken,
		RefreshToken: pair.RefreshToken,
		ExpiresIn:    pair.ExpiresIn,
	})
}

func (h *AuthHandler) Logout(w http.ResponseWriter, r *http.Request) {
	var req struct {
		RefreshToken string `json:"refresh_token"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}

	if token := strings.TrimSpace(req.RefreshToken); token != "" {
		if err := h.authService.RevokeRefreshToken(r.Context(), token); err != nil {
			writeError(w, r, http.StatusServiceUnavailable, "failed to revoke refresh token")
			return
		}
	}

	jti := ctxkey.String(r.Context(), ctxkey.JTI)
	rawToken := bearerToken(r.Header.Get("Authorization"))
	if jti != "" && rawToken != "" {
		ttl, err := h.authService.RemainingTokenTTL(rawToken)
		if err != nil {
			writeError(w, r, http.StatusUnauthorized, "invalid access token")
			return
		}
		if err := h.authService.BlacklistAccessToken(r.Context(), jti, ttl); err != nil {
			writeError(w, r, http.StatusServiceUnavailable, "failed to blacklist access token")
			return
		}
	}

	respond.NoContent(w)
}

func (h *AuthHandler) Me(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	user, err := h.usersRepo.GetUserByID(r.Context(), userID)
	if err != nil {
		writeError(w, r, http.StatusNotFound, "user not found")
		return
	}

	respond.JSON(w, http.StatusOK, userPayload(user))
}

func bearerToken(header string) string {
	if !strings.HasPrefix(strings.ToLower(header), "bearer ") {
		return ""
	}
	return strings.TrimSpace(header[7:])
}

func parseUserIDFromModel(user *models.User) (uuid.UUID, error) {
	if user == nil || !user.ID.Valid {
		return uuid.Nil, errors.New("invalid user")
	}
	return uuid.UUID(user.ID.Bytes), nil
}
