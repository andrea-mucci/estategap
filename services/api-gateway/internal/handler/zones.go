package handler

import (
	"errors"
	"net/http"
	"strings"

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
	level, err := parseOptionalInt(r.URL.Query().Get("level"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid level")
		return
	}
	parentID, err := parseUUID(r.URL.Query().Get("parent_id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid parent_id")
		return
	}

	items, cursor, totalCount, err := h.repo.ListZones(
		r.Context(),
		strings.ToUpper(r.URL.Query().Get("country")),
		level,
		parentID,
		r.URL.Query().Get("cursor"),
		parseLimit(r.URL.Query().Get("limit")),
	)
	if err != nil {
		if errors.Is(err, repository.ErrInvalidInput) {
			writeError(w, r, http.StatusBadRequest, err.Error())
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load zones")
		return
	}

	payload := make([]zoneDetailPayload, 0, len(items))
	for i := range items {
		payload = append(payload, zoneDetailFromModel(&items[i]))
	}

	respond.JSON(w, http.StatusOK, listEnvelope(payload, cursor, cursor != "", totalCount, ""))
}

func (h *ZonesHandler) Get(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid zone id")
		return
	}

	item, err := h.repo.GetZoneByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "zone not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load zone")
		return
	}

	respond.JSON(w, http.StatusOK, zoneDetailFromModel(item))
}

func (h *ZonesHandler) Analytics(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid zone id")
		return
	}

	months, err := h.repo.GetZoneAnalytics(r.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "zone not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load analytics")
		return
	}

	respond.JSON(w, http.StatusOK, zoneAnalyticsFromMonths(id, months))
}

func (h *ZonesHandler) Compare(w http.ResponseWriter, r *http.Request) {
	rawIDs := strings.TrimSpace(r.URL.Query().Get("ids"))
	if rawIDs == "" {
		writeError(w, r, http.StatusBadRequest, "ids query param is required")
		return
	}

	parts := strings.Split(rawIDs, ",")
	ids := make([]uuid.UUID, 0, len(parts))
	for _, part := range parts {
		value, err := uuid.Parse(strings.TrimSpace(part))
		if err != nil {
			writeError(w, r, http.StatusBadRequest, "invalid zone id")
			return
		}
		ids = append(ids, value)
	}

	items, err := h.repo.CompareZones(r.Context(), ids)
	if err != nil {
		switch {
		case errors.Is(err, repository.ErrInvalidInput):
			writeError(w, r, http.StatusBadRequest, err.Error())
		case errors.Is(err, repository.ErrNotFound):
			writeError(w, r, http.StatusNotFound, "zone not found")
		default:
			writeError(w, r, http.StatusServiceUnavailable, "failed to compare zones")
		}
		return
	}

	respond.JSON(w, http.StatusOK, zoneCompareFromItems(items))
}
