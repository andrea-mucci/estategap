package handler

import (
	"errors"
	"net/http"

	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type ListingsHandler struct {
	repo *repository.ListingsRepo
}

func NewListingsHandler(repo *repository.ListingsRepo) *ListingsHandler {
	return &ListingsHandler{repo: repo}
}

func (h *ListingsHandler) List(w http.ResponseWriter, r *http.Request) {
	filter, err := buildListingFilter(r)
	if err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}

	items, cursor, err := h.repo.SearchListings(r.Context(), filter)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load listings")
		return
	}

	payload := make([]listingPayload, 0, len(items))
	for i := range items {
		payload = append(payload, listingFromModel(&items[i]))
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"items":  payload,
		"total":  len(payload),
		"cursor": cursor,
	})
}

func (h *ListingsHandler) Get(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid listing id")
		return
	}

	item, err := h.repo.GetListingByID(r.Context(), id)
	if err != nil {
		writeError(w, r, http.StatusNotFound, "listing not found")
		return
	}

	respond.JSON(w, http.StatusOK, listingFromModel(item))
}

func buildListingFilter(r *http.Request) (repository.ListingFilter, error) {
	values := r.URL.Query()
	minPrice, err := parseOptionalFloat(values.Get("min_price_eur"))
	if err != nil {
		return repository.ListingFilter{}, err
	}
	maxPrice, err := parseOptionalFloat(values.Get("max_price_eur"))
	if err != nil {
		return repository.ListingFilter{}, err
	}
	minArea, err := parseOptionalFloat(values.Get("min_area_m2"))
	if err != nil {
		return repository.ListingFilter{}, err
	}
	maxArea, err := parseOptionalFloat(values.Get("max_area_m2"))
	if err != nil {
		return repository.ListingFilter{}, err
	}
	propertyCategory, err := parsePropertyCategory(values.Get("property_category"))
	if err != nil {
		return repository.ListingFilter{}, err
	}
	dealTier, err := parseDealTier(values.Get("deal_tier"))
	if err != nil {
		return repository.ListingFilter{}, err
	}
	status, err := parseListingStatus(values.Get("status"))
	if err != nil {
		return repository.ListingFilter{}, err
	}

	country := values.Get("country")
	if country == "" {
		return repository.ListingFilter{}, errors.New("country is required")
	}

	return repository.ListingFilter{
		Country:          country,
		City:             values.Get("city"),
		MinPriceEUR:      minPrice,
		MaxPriceEUR:      maxPrice,
		MinAreaM2:        minArea,
		MaxAreaM2:        maxArea,
		PropertyCategory: propertyCategory,
		DealTier:         dealTier,
		Status:           status,
		Cursor:           values.Get("cursor"),
		Limit:            parseLimit(values.Get("limit")),
	}, nil
}
