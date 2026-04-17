package handler

import (
	"net/http"

	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
)

type ReferenceHandler struct {
	repo *repository.ReferenceRepo
}

func NewReferenceHandler(repo *repository.ReferenceRepo) *ReferenceHandler {
	return &ReferenceHandler{repo: repo}
}

func (h *ReferenceHandler) Countries(w http.ResponseWriter, r *http.Request) {
	items, err := h.repo.ListCountries(r.Context())
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load countries")
		return
	}

	payload := make([]countryPayload, 0, len(items))
	for i := range items {
		payload = append(payload, countryFromSummary(&items[i]))
	}

	respond.JSON(w, http.StatusOK, listEnvelope(payload, "", false, int64(len(payload)), ""))
}

func (h *ReferenceHandler) Portals(w http.ResponseWriter, r *http.Request) {
	items, err := h.repo.ListPortals(r.Context())
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load portals")
		return
	}

	payload := make([]portalPayload, 0, len(items))
	for i := range items {
		payload = append(payload, portalFromModel(&items[i]))
	}

	respond.JSON(w, http.StatusOK, listEnvelope(payload, "", false, int64(len(payload)), ""))
}
