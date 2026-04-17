package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type AlertsHandler struct {
	repo *repository.AlertsRepo
}

func NewAlertsHandler(repo *repository.AlertsRepo) *AlertsHandler {
	return &AlertsHandler{repo: repo}
}

func (h *AlertsHandler) List(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	items, cursor, err := h.repo.ListAlerts(r.Context(), userID, r.URL.Query().Get("cursor"), parseLimit(r.URL.Query().Get("limit")))
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load alerts")
		return
	}

	payload := make([]alertRulePayload, 0, len(items))
	for i := range items {
		payload = append(payload, alertFromModel(&items[i]))
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"items":  payload,
		"cursor": cursor,
	})
}

func (h *AlertsHandler) Create(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	input, ok := decodeAlertInput(w, r)
	if !ok {
		return
	}

	item, err := h.repo.CreateAlert(r.Context(), userID, input)
	if err != nil {
		if errors.Is(err, repository.ErrAlertLimitReached) {
			writeError(w, r, http.StatusUnprocessableEntity, "alert limit reached")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to create alert")
		return
	}

	respond.JSON(w, http.StatusCreated, alertFromModel(item))
}

func (h *AlertsHandler) Get(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}
	alertID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid alert id")
		return
	}

	item, err := h.repo.GetAlertByID(r.Context(), alertID, userID)
	if err != nil {
		writeError(w, r, http.StatusNotFound, "alert not found")
		return
	}

	respond.JSON(w, http.StatusOK, alertFromModel(item))
}

func (h *AlertsHandler) Update(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}
	alertID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid alert id")
		return
	}

	input, ok := decodeAlertInput(w, r)
	if !ok {
		return
	}

	item, err := h.repo.UpdateAlert(r.Context(), alertID, userID, input)
	if err != nil {
		if errors.Is(err, repository.ErrAlertLimitReached) {
			writeError(w, r, http.StatusUnprocessableEntity, "alert limit reached")
			return
		}
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "alert not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to update alert")
		return
	}

	respond.JSON(w, http.StatusOK, alertFromModel(item))
}

func (h *AlertsHandler) Delete(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}
	alertID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid alert id")
		return
	}

	if err := h.repo.DeleteAlert(r.Context(), alertID, userID); err != nil {
		writeError(w, r, http.StatusNotFound, "alert not found")
		return
	}

	respond.NoContent(w)
}

func (h *AlertsHandler) History(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}
	alertID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid alert id")
		return
	}

	items, cursor, err := h.repo.ListAlertHistory(r.Context(), alertID, userID, r.URL.Query().Get("cursor"), parseLimit(r.URL.Query().Get("limit")))
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load alert history")
		return
	}

	payload := make([]alertEventPayload, 0, len(items))
	for _, item := range items {
		payload = append(payload, alertEventFromRepo(item))
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"items":  payload,
		"cursor": cursor,
	})
}

func decodeAlertInput(w http.ResponseWriter, r *http.Request) (repository.AlertInput, bool) {
	var req struct {
		Name     string          `json:"name"`
		Filters  json.RawMessage `json:"filters"`
		Channels json.RawMessage `json:"channels"`
		Active   *bool           `json:"active"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return repository.AlertInput{}, false
	}
	if strings.TrimSpace(req.Name) == "" {
		writeError(w, r, http.StatusUnprocessableEntity, "name is required")
		return repository.AlertInput{}, false
	}
	active := true
	if req.Active != nil {
		active = *req.Active
	}
	return repository.AlertInput{
		Name:     strings.TrimSpace(req.Name),
		Filters:  req.Filters,
		Channels: req.Channels,
		Active:   active,
	}, true
}
