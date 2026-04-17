package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	cachepkg "github.com/estategap/services/api-gateway/internal/cache"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type ZonesHandler struct {
	repo           *repository.ZonesRepo
	zoneStatsCache cachepkg.ZoneStatsCache
}

func NewZonesHandler(repo *repository.ZonesRepo, cacheClient ...*cachepkg.Client) *ZonesHandler {
	handler := &ZonesHandler{repo: repo}
	if len(cacheClient) > 0 {
		handler.zoneStatsCache = cachepkg.NewZoneStatsCache(cacheClient[0])
	}
	return handler
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
		r.URL.Query().Get("q"),
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

func (h *ZonesHandler) Stats(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid zone id")
		return
	}

	item, hit, err := cachepkg.GetOrSetRequest(
		r.Context(),
		h.zoneStatsCache.RequestCache,
		r,
		func() (*repository.ZoneWithStats, error) {
			return h.repo.GetZoneByID(r.Context(), id)
		},
	)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "zone not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load zone stats")
		return
	}

	if hit {
		w.Header().Set("X-Cache", "HIT")
	} else {
		w.Header().Set("X-Cache", "MISS")
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

func (h *ZonesHandler) PriceDistribution(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid zone id")
		return
	}

	item, err := h.repo.GetZonePriceDistribution(r.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "zone not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load price distribution")
		return
	}

	respond.JSON(w, http.StatusOK, zonePriceDistributionFromModel(item))
}

func (h *ZonesHandler) Geometry(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid zone id")
		return
	}

	item, err := h.repo.GetZoneGeometry(r.Context(), id)
	if err != nil {
		switch {
		case errors.Is(err, repository.ErrNotFound):
			writeError(w, r, http.StatusNotFound, "zone not found")
		default:
			writeError(w, r, http.StatusServiceUnavailable, "failed to load zone geometry")
		}
		return
	}

	respond.JSON(w, http.StatusOK, item)
}

func (h *ZonesHandler) Create(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name     string          `json:"name"`
		Type     string          `json:"type"`
		Country  string          `json:"country"`
		Geometry json.RawMessage `json:"geometry"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}

	req.Name = strings.TrimSpace(req.Name)
	req.Country = strings.ToUpper(strings.TrimSpace(req.Country))
	if req.Name == "" || len(req.Name) > 100 {
		writeError(w, r, http.StatusBadRequest, "name must be between 1 and 100 characters")
		return
	}
	if req.Type != "custom" {
		writeError(w, r, http.StatusBadRequest, "type must be custom")
		return
	}
	if len(req.Country) != 2 {
		writeError(w, r, http.StatusBadRequest, "country must be a valid ISO code")
		return
	}

	var polygon struct {
		Type        string        `json:"type"`
		Coordinates [][][]float64 `json:"coordinates"`
	}
	if err := json.Unmarshal(req.Geometry, &polygon); err != nil {
		writeError(w, r, http.StatusBadRequest, "geometry must be valid GeoJSON")
		return
	}
	if polygon.Type != "Polygon" || len(polygon.Coordinates) == 0 || len(polygon.Coordinates[0]) < 4 {
		writeError(w, r, http.StatusBadRequest, "geometry must be a polygon with at least four points")
		return
	}

	ring := polygon.Coordinates[0]
	first := ring[0]
	last := ring[len(ring)-1]
	if len(first) != 2 || len(last) != 2 || first[0] != last[0] || first[1] != last[1] {
		writeError(w, r, http.StatusBadRequest, "polygon must be closed")
		return
	}

	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user id")
		return
	}

	item, err := h.repo.CreateCustomZone(r.Context(), repository.CreateCustomZoneRequest{
		Name:     req.Name,
		Type:     req.Type,
		Country:  req.Country,
		Geometry: req.Geometry,
	}, userID)
	if err != nil {
		switch {
		case errors.Is(err, repository.ErrValidation):
			writeError(w, r, http.StatusUnprocessableEntity, "geometry is invalid")
		case errors.Is(err, repository.ErrLimitReached):
			writeError(w, r, http.StatusTooManyRequests, "custom zone limit reached")
		default:
			writeError(w, r, http.StatusServiceUnavailable, "failed to create custom zone")
		}
		return
	}

	respond.JSON(w, http.StatusCreated, zoneDetailFromModel(item))
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
