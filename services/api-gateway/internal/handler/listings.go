package handler

import (
	"errors"
	"net/http"
	"strings"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type ListingsHandler struct {
	repo      *repository.ListingsRepo
	usersRepo *repository.UsersRepo
}

func NewListingsHandler(repo *repository.ListingsRepo, usersRepo *repository.UsersRepo) *ListingsHandler {
	return &ListingsHandler{repo: repo, usersRepo: usersRepo}
}

func (h *ListingsHandler) List(w http.ResponseWriter, r *http.Request) {
	filter, err := buildListingFilter(r)
	if err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}

	switch models.SubscriptionTier(ctxkey.String(r.Context(), ctxkey.UserTier)) {
	case models.SubscriptionTierFree:
		filter.FreeTierGate = true
	case models.SubscriptionTierBasic:
		userID, err := parseUserID(r.Context())
		if err != nil {
			writeError(w, r, http.StatusUnauthorized, "missing user id")
			return
		}

		user, err := h.usersRepo.GetUserByID(r.Context(), userID)
		if err != nil {
			writeError(w, r, http.StatusServiceUnavailable, "failed to load user subscription")
			return
		}
		filter.AllowedCountries = user.AllowedCountries
	}

	items, cursor, totalCount, rateDate, err := h.repo.SearchListings(r.Context(), filter)
	if err != nil {
		if errors.Is(err, repository.ErrInvalidInput) {
			writeError(w, r, http.StatusBadRequest, err.Error())
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load listings")
		return
	}

	targetCurrency := strings.ToUpper(filter.Currency)
	if targetCurrency == "" {
		targetCurrency = "EUR"
	}

	w.Header().Set("X-Currency", targetCurrency)
	if rateDate != "" {
		w.Header().Set("X-Exchange-Rate-Date", rateDate)
	}

	payload := make([]listingSummaryPayload, 0, len(items))
	for i := range items {
		payload = append(payload, listingSummaryFromModel(&items[i], items[i].PriceConverted, targetCurrency))
	}

	respond.JSON(w, http.StatusOK, listEnvelope(payload, cursor, cursor != "", totalCount, targetCurrency))
}

func (h *ListingsHandler) Get(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid listing id")
		return
	}

	item, err := h.repo.GetListingDetail(r.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeError(w, r, http.StatusNotFound, "listing not found")
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to load listing detail")
		return
	}

	respond.JSON(w, http.StatusOK, listingDetailFromResult(item))
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
	zoneID, err := parseUUID(values.Get("zone_id"))
	if err != nil {
		return repository.ListingFilter{}, errors.New("invalid zone_id")
	}
	portalID, err := parseUUID(values.Get("portal_id"))
	if err != nil {
		return repository.ListingFilter{}, errors.New("invalid portal_id")
	}
	minBedrooms, err := parseOptionalInt(values.Get("min_bedrooms"))
	if err != nil {
		return repository.ListingFilter{}, errors.New("invalid min_bedrooms")
	}
	minBathrooms, err := parseOptionalInt(values.Get("min_bathrooms"))
	if err != nil {
		return repository.ListingFilter{}, errors.New("invalid min_bathrooms")
	}
	minDaysOnMarket, err := parseOptionalInt(values.Get("min_days_on_market"))
	if err != nil {
		return repository.ListingFilter{}, errors.New("invalid min_days_on_market")
	}
	maxDaysOnMarket, err := parseOptionalInt(values.Get("max_days_on_market"))
	if err != nil {
		return repository.ListingFilter{}, errors.New("invalid max_days_on_market")
	}
	sortBy, err := parseSortBy(values.Get("sort_by"))
	if err != nil {
		return repository.ListingFilter{}, err
	}

	country := strings.ToUpper(values.Get("country"))
	if country == "" {
		return repository.ListingFilter{}, errors.New("country is required")
	}

	return repository.ListingFilter{
		Country:          country,
		City:             values.Get("city"),
		ZoneID:           zoneID,
		PropertyType:     values.Get("property_type"),
		MinPriceEUR:      minPrice,
		MaxPriceEUR:      maxPrice,
		MinAreaM2:        minArea,
		MaxAreaM2:        maxArea,
		PropertyCategory: propertyCategory,
		MinBedrooms:      minBedrooms,
		MinBathrooms:     minBathrooms,
		DealTier:         dealTier,
		Status:           status,
		PortalID:         portalID,
		MinDaysOnMarket:  minDaysOnMarket,
		MaxDaysOnMarket:  maxDaysOnMarket,
		SortBy:           sortBy,
		SortDir:          parseSortDir(values.Get("sort_dir")),
		Currency:         strings.ToUpper(values.Get("currency")),
		Cursor:           values.Get("cursor"),
		Limit:            parseLimit(values.Get("limit")),
	}, nil
}
