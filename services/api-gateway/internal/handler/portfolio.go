package handler

import (
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type PortfolioHandler struct {
	repo *repository.PortfolioRepo
}

func NewPortfolioHandler(repo *repository.PortfolioRepo) *PortfolioHandler {
	return &PortfolioHandler{repo: repo}
}

func (h *PortfolioHandler) List(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	properties, summary, err := h.repo.ListPortfolioProperties(r.Context(), userID)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load portfolio")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"properties": properties,
		"summary":    summary,
	})
}

func (h *PortfolioHandler) Create(w http.ResponseWriter, r *http.Request) {
	req, ok := h.parsePortfolioRequest(w, r)
	if !ok {
		return
	}

	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	property, err := h.repo.CreatePortfolioProperty(r.Context(), userID, req)
	if err != nil {
		if errors.Is(err, repository.ErrInvalidInput) {
			writeError(w, r, http.StatusBadRequest, err.Error())
			return
		}
		writeError(w, r, http.StatusServiceUnavailable, "failed to create portfolio property")
		return
	}

	respond.JSON(w, http.StatusCreated, property)
}

func (h *PortfolioHandler) Update(w http.ResponseWriter, r *http.Request) {
	propertyID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid property id")
		return
	}

	req, ok := h.parsePortfolioRequest(w, r)
	if !ok {
		return
	}

	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	property, err := h.repo.UpdatePortfolioProperty(r.Context(), userID, propertyID, req)
	if err != nil {
		switch {
		case errors.Is(err, repository.ErrInvalidInput):
			writeError(w, r, http.StatusBadRequest, err.Error())
		case errors.Is(err, repository.ErrForbidden):
			writeError(w, r, http.StatusForbidden, "property belongs to another user")
		case errors.Is(err, repository.ErrNotFound):
			writeError(w, r, http.StatusNotFound, "property not found")
		default:
			writeError(w, r, http.StatusServiceUnavailable, "failed to update portfolio property")
		}
		return
	}

	respond.JSON(w, http.StatusOK, property)
}

func (h *PortfolioHandler) Delete(w http.ResponseWriter, r *http.Request) {
	propertyID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid property id")
		return
	}

	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	err = h.repo.DeletePortfolioProperty(r.Context(), userID, propertyID)
	if err != nil {
		switch {
		case errors.Is(err, repository.ErrForbidden):
			writeError(w, r, http.StatusForbidden, "property belongs to another user")
		case errors.Is(err, repository.ErrNotFound):
			writeError(w, r, http.StatusNotFound, "property not found")
		default:
			writeError(w, r, http.StatusServiceUnavailable, "failed to delete portfolio property")
		}
		return
	}

	respond.NoContent(w)
}

func (h *PortfolioHandler) parsePortfolioRequest(w http.ResponseWriter, r *http.Request) (repository.CreatePortfolioPropertyRequest, bool) {
	var req struct {
		Address             string   `json:"address"`
		Country             string   `json:"country"`
		PurchasePrice       float64  `json:"purchase_price"`
		PurchaseCurrency    string   `json:"purchase_currency"`
		PurchaseDate        string   `json:"purchase_date"`
		MonthlyRentalIncome float64  `json:"monthly_rental_income"`
		AreaM2              *float64 `json:"area_m2"`
		PropertyType        string   `json:"property_type"`
		Notes               *string  `json:"notes"`
	}

	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return repository.CreatePortfolioPropertyRequest{}, false
	}

	purchaseDate, err := time.Parse("2006-01-02", strings.TrimSpace(req.PurchaseDate))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "purchase_date must be a valid YYYY-MM-DD date")
		return repository.CreatePortfolioPropertyRequest{}, false
	}
	if purchaseDate.After(time.Now().UTC()) {
		writeError(w, r, http.StatusBadRequest, "purchase_date cannot be in the future")
		return repository.CreatePortfolioPropertyRequest{}, false
	}

	address := strings.TrimSpace(req.Address)
	country := strings.ToUpper(strings.TrimSpace(req.Country))
	purchaseCurrency := strings.ToUpper(strings.TrimSpace(req.PurchaseCurrency))
	propertyType := strings.ToLower(strings.TrimSpace(req.PropertyType))
	if propertyType == "" {
		propertyType = "residential"
	}

	if address == "" || len(country) != 2 {
		writeError(w, r, http.StatusBadRequest, "address and country are required")
		return repository.CreatePortfolioPropertyRequest{}, false
	}
	if req.PurchasePrice <= 0 {
		writeError(w, r, http.StatusBadRequest, "purchase_price must be greater than 0")
		return repository.CreatePortfolioPropertyRequest{}, false
	}
	if len(purchaseCurrency) != 3 {
		writeError(w, r, http.StatusBadRequest, "purchase_currency must be a valid ISO 4217 code")
		return repository.CreatePortfolioPropertyRequest{}, false
	}
	if req.MonthlyRentalIncome < 0 {
		writeError(w, r, http.StatusBadRequest, "monthly_rental_income must be 0 or greater")
		return repository.CreatePortfolioPropertyRequest{}, false
	}
	if req.AreaM2 != nil && *req.AreaM2 <= 0 {
		writeError(w, r, http.StatusBadRequest, "area_m2 must be greater than 0")
		return repository.CreatePortfolioPropertyRequest{}, false
	}
	switch propertyType {
	case "residential", "commercial", "industrial", "land":
	default:
		writeError(w, r, http.StatusBadRequest, "property_type must be residential, commercial, industrial, or land")
		return repository.CreatePortfolioPropertyRequest{}, false
	}

	return repository.CreatePortfolioPropertyRequest{
		Address:             address,
		Country:             country,
		PurchasePrice:       req.PurchasePrice,
		PurchaseCurrency:    purchaseCurrency,
		PurchaseDate:        purchaseDate,
		MonthlyRentalIncome: req.MonthlyRentalIncome,
		AreaM2:              req.AreaM2,
		PropertyType:        propertyType,
		Notes:               req.Notes,
	}, true
}
