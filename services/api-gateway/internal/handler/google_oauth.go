package handler

import (
	"errors"
	"net/http"

	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/estategap/services/api-gateway/internal/service"
)

type GoogleOAuthHandler struct {
	oauthService *service.OAuthService
}

func NewGoogleOAuthHandler(oauthService *service.OAuthService) *GoogleOAuthHandler {
	return &GoogleOAuthHandler{oauthService: oauthService}
}

func (h *GoogleOAuthHandler) Redirect(w http.ResponseWriter, r *http.Request) {
	redirectURL, _, err := h.oauthService.BeginFlow(r.Context())
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to start oauth flow")
		return
	}
	http.Redirect(w, r, redirectURL, http.StatusFound)
}

func (h *GoogleOAuthHandler) Callback(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	state := r.URL.Query().Get("state")
	if code == "" || state == "" {
		writeError(w, r, http.StatusBadRequest, "missing code or state")
		return
	}

	pair, user, err := h.oauthService.HandleCallback(r.Context(), code, state)
	if err != nil {
		if errors.Is(err, service.ErrInvalidOAuthState) {
			writeError(w, r, http.StatusBadRequest, "invalid oauth state")
			return
		}
		writeError(w, r, http.StatusBadRequest, "oauth callback failed")
		return
	}

	respond.JSON(w, http.StatusOK, tokenPairWithUser(pair.AccessToken, pair.RefreshToken, pair.ExpiresIn, user))
}
