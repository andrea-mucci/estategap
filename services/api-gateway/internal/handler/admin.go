package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"
)

type AdminHandler struct {
	repo        *repository.AdminRepo
	natsConn    *nats.Conn
	redisClient *redis.Client
}

func NewAdminHandler(repo *repository.AdminRepo, natsConn *nats.Conn, redisClient *redis.Client) *AdminHandler {
	return &AdminHandler{
		repo:        repo,
		natsConn:    natsConn,
		redisClient: redisClient,
	}
}

func (h *AdminHandler) ScrapingStats(w http.ResponseWriter, r *http.Request) {
	portals, err := h.repo.GetScrapingStats(r.Context())
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load scraping stats")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]any{"portals": portals})
}

func (h *AdminHandler) MLModels(w http.ResponseWriter, r *http.Request) {
	models, err := h.repo.GetMLModels(r.Context())
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load ML models")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]any{"models": models})
}

func (h *AdminHandler) TriggerRetrain(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Country string `json:"country"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}

	country := strings.ToUpper(strings.TrimSpace(req.Country))
	if len(country) != 2 {
		writeError(w, r, http.StatusBadRequest, "country must be a valid ISO code")
		return
	}

	inProgress, err := h.repo.IsRetrainingInProgress(r.Context(), country)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to check retrain status")
		return
	}
	if inProgress {
		writeError(w, r, http.StatusConflict, "retraining is already in progress for this country")
		return
	}

	jobID := uuid.NewString()
	payload, err := json.Marshal(map[string]string{
		"country":      country,
		"requested_by": ctxkey.String(r.Context(), ctxkey.UserEmail),
		"job_id":       jobID,
	})
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to queue retrain job")
		return
	}

	if err := h.natsConn.Publish("ml.retrain.requested", payload); err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to queue retrain job")
		return
	}
	if err := h.redisClient.Set(r.Context(), "ml:retrain:in_progress:"+country, jobID, 2*time.Hour).Err(); err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to track retrain job")
		return
	}

	respond.JSON(w, http.StatusAccepted, map[string]string{
		"job_id": jobID,
		"status": "queued",
	})
}

func (h *AdminHandler) ListUsers(w http.ResponseWriter, r *http.Request) {
	page := parseAdminInt(r.URL.Query().Get("page"), 1)
	limit := parseAdminInt(r.URL.Query().Get("limit"), 50)
	q := r.URL.Query().Get("q")
	tier := r.URL.Query().Get("tier")

	users, total, err := h.repo.ListUsers(r.Context(), page, limit, q, tier)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load users")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"users": users,
		"total": total,
		"page":  page,
		"limit": limit,
	})
}

func (h *AdminHandler) ListCountries(w http.ResponseWriter, r *http.Request) {
	countries, err := h.repo.GetCountries(r.Context())
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load countries")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]any{"countries": countries})
}

func (h *AdminHandler) UpdateCountry(w http.ResponseWriter, r *http.Request) {
	code := strings.ToUpper(strings.TrimSpace(chi.URLParam(r, "code")))
	if len(code) != 2 {
		writeError(w, r, http.StatusBadRequest, "invalid country code")
		return
	}

	var req struct {
		Enabled *bool                     `json:"enabled"`
		Portals []repository.PortalConfig `json:"portals"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.Enabled == nil {
		writeError(w, r, http.StatusBadRequest, "enabled is required")
		return
	}

	country, err := h.repo.UpdateCountry(r.Context(), code, *req.Enabled, req.Portals)
	if err != nil {
		switch {
		case errors.Is(err, repository.ErrNotFound):
			writeError(w, r, http.StatusNotFound, "country not found")
		default:
			writeError(w, r, http.StatusServiceUnavailable, "failed to update country")
		}
		return
	}

	respond.JSON(w, http.StatusOK, country)
}

func (h *AdminHandler) SystemHealth(w http.ResponseWriter, r *http.Request) {
	health, err := h.repo.GetSystemHealth(r.Context())
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load system health")
		return
	}

	respond.JSON(w, http.StatusOK, health)
}

func parseAdminInt(raw string, fallback int) int {
	value, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil || value <= 0 {
		return fallback
	}
	return value
}
