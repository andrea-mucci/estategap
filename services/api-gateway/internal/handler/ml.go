package handler

import (
	"context"
	"errors"
	"net/http"
	"time"

	"github.com/estategap/libs/models"
	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type MLScorer interface {
	ScoreListing(ctx context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error)
}

type ListingReader interface {
	GetListingByID(ctx context.Context, id uuid.UUID) (*models.Listing, error)
}

type MLHandler struct {
	mlClient     MLScorer
	listingsRepo ListingReader
	timeout      time.Duration
}

func NewMLHandler(mlClient MLScorer, listingsRepo ListingReader, timeout time.Duration) *MLHandler {
	return &MLHandler{
		mlClient:     mlClient,
		listingsRepo: listingsRepo,
		timeout:      timeout,
	}
}

func (h *MLHandler) Estimate(w http.ResponseWriter, r *http.Request) {
	listingIDRaw := r.URL.Query().Get("listing_id")
	if listingIDRaw == "" {
		writeFeatureError(w, http.StatusBadRequest, "listing_id is required", "INVALID_LISTING_ID", nil)
		return
	}

	listingID, err := uuid.Parse(listingIDRaw)
	if err != nil {
		writeFeatureError(w, http.StatusBadRequest, "listing_id must be a UUID", "INVALID_LISTING_ID", nil)
		return
	}

	listing, err := h.listingsRepo.GetListingByID(r.Context(), listingID)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			writeFeatureError(w, http.StatusNotFound, "listing not found", "LISTING_NOT_FOUND", nil)
			return
		}
		writeFeatureError(w, http.StatusServiceUnavailable, "failed to load listing", "LISTING_LOOKUP_UNAVAILABLE", nil)
		return
	}

	ctx := r.Context()
	if h.timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, h.timeout)
		defer cancel()
	}

	resp, err := h.mlClient.ScoreListing(ctx, &estategapv1.ScoreListingRequest{
		ListingId:   listingID.String(),
		CountryCode: listing.Country,
	})
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) {
			writeFeatureError(w, http.StatusServiceUnavailable, "ML scoring service is temporarily unavailable", "ML_SCORER_UNAVAILABLE", nil)
			return
		}

		switch status.Code(err) {
		case codes.NotFound:
			writeFeatureError(w, http.StatusNotFound, "listing not found", "LISTING_NOT_FOUND", nil)
		case codes.Unavailable, codes.DeadlineExceeded:
			writeFeatureError(w, http.StatusServiceUnavailable, "ML scoring service is temporarily unavailable", "ML_SCORER_UNAVAILABLE", nil)
		default:
			writeFeatureError(w, http.StatusServiceUnavailable, "ML scoring service is temporarily unavailable", "ML_SCORER_UNAVAILABLE", nil)
		}
		return
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"listing_id":      resp.GetListingId(),
		"estimated_value": estimateValue(listing),
		"currency":        "EUR",
		"confidence":      estimateConfidence(listing, resp),
		"shap_values":     shapValuesMap(resp.GetShapValues()),
		"model_version":   modelVersion(listing, resp),
	})
}

func estimateValue(listing *models.Listing) float64 {
	if listing != nil && listing.EstimatedPrice != nil {
		value, _ := listing.EstimatedPrice.Float64()
		return value
	}
	if listing != nil && listing.AskingPriceEUR != nil {
		value, _ := listing.AskingPriceEUR.Float64()
		return value
	}
	return 0
}

func estimateConfidence(listing *models.Listing, resp *estategapv1.ScoreListingResponse) float64 {
	if resp == nil {
		return 0
	}
	score := float64(resp.GetDealScore())
	if score > 1 {
		score = score / 100
	}
	if score < 0 {
		score = 0
	}
	if score > 1 {
		score = 1
	}
	return score
}

func shapValuesMap(values []*estategapv1.ShapValue) map[string]float64 {
	out := make(map[string]float64, len(values))
	for _, item := range values {
		if item == nil || item.GetFeatureName() == "" {
			continue
		}
		value := item.GetContribution()
		if value == 0 {
			value = item.GetValue()
		}
		out[item.GetFeatureName()] = float64(value)
	}
	return out
}

func modelVersion(listing *models.Listing, resp *estategapv1.ScoreListingResponse) string {
	if resp != nil && resp.GetModelVersion() != "" {
		return resp.GetModelVersion()
	}
	if listing != nil && listing.ModelVersion != nil {
		return *listing.ModelVersion
	}
	return ""
}
