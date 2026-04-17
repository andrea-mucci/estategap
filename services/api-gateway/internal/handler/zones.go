package handler

import (
	"errors"
	"net/http"

	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type ZonesHandler struct {
	repo *repository.ZonesRepo
}

func NewZonesHandler(repo *repository.ZonesRepo) *ZonesHandler {
	return &ZonesHandler{repo: repo}
}

func (h *ZonesHandler) List(w http.ResponseWriter, r *http.Request) {
	country := r.URL.Query().Get("country")
	if country == "" {
		writeError(w, r, http.StatusBadRequest, "country is required")
		return
	}

	items, cursor, err := h.repo.ListZones(r.Context(), country, r.URL.Query().Get("cursor"), parseLimit(r.URL.Query().Get("limit")))
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load zones")
		return
	}

	payload := make([]zonePayload, 0, len(items))
	for i := range items {
		payload = append(payload, zoneFromModel(&items[i]))
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"items":  payload,
		"cursor": cursor,
	})
}

func (h *ZonesHandler) Get(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid zone id")
		return
	}

	item, err := h.repo.GetZoneByID(r.Context(), id)
	if err != nil {
		writeError(w, r, http.StatusNotFound, "zone not found")
		return
	}

	respond.JSON(w, http.StatusOK, zoneFromModel(item))
}

func (h *ZonesHandler) Analytics(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid zone id")
		return
	}

	periodDays, err := parsePeriodDays(r.URL.Query().Get("period_days"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}

	item, err := h.repo.GetZoneAnalytics(r.Context(), id, periodDays)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "zone not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load analytics")
		return
	}

	respond.JSON(w, http.StatusOK, zoneAnalyticsFromRepo(item))
}
