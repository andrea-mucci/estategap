package handler

import (
	"net/http"
	"strings"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
)

type DashboardHandler struct {
	repo      *repository.DashboardRepo
	usersRepo *repository.UsersRepo
}

func NewDashboardHandler(repo *repository.DashboardRepo, usersRepo *repository.UsersRepo) *DashboardHandler {
	return &DashboardHandler{
		repo:      repo,
		usersRepo: usersRepo,
	}
}

func (h *DashboardHandler) Summary(w http.ResponseWriter, r *http.Request) {
	country := strings.ToUpper(strings.TrimSpace(r.URL.Query().Get("country")))
	if country == "" {
		writeError(w, r, http.StatusBadRequest, "country is required")
		return
	}

	allowed, err := h.countryAllowed(r, country)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to validate country access")
		return
	}
	if !allowed {
		writeError(w, r, http.StatusForbidden, "country not accessible under current subscription tier")
		return
	}

	summary, err := h.repo.GetDashboardSummary(r.Context(), country)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load dashboard summary")
		return
	}

	respond.JSON(w, http.StatusOK, summary)
}

func (h *DashboardHandler) countryAllowed(r *http.Request, country string) (bool, error) {
	tier := models.SubscriptionTier(ctxkey.String(r.Context(), ctxkey.UserTier))
	switch tier {
	case models.SubscriptionTierPro, models.SubscriptionTierGlobal, models.SubscriptionTierAPI:
		return true, nil
	case models.SubscriptionTierBasic, models.SubscriptionTierFree:
		userID, err := parseUserID(r.Context())
		if err != nil {
			return false, err
		}

		user, err := h.usersRepo.GetUserByID(r.Context(), userID)
		if err != nil {
			return false, err
		}

		if len(user.AllowedCountries) == 0 {
			return tier != models.SubscriptionTierFree || country == "ES", nil
		}

		for _, allowedCountry := range user.AllowedCountries {
			if strings.EqualFold(allowedCountry, country) {
				return true, nil
			}
		}

		return false, nil
	default:
		return false, nil
	}
}
