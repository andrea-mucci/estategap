package handler

import (
	"net/http"

	"github.com/estategap/services/api-gateway/internal/respond"
)

type SubscriptionsHandler struct{}

func NewSubscriptionsHandler() *SubscriptionsHandler {
	return &SubscriptionsHandler{}
}

func (h *SubscriptionsHandler) Checkout(w http.ResponseWriter, _ *http.Request) {
	respond.JSON(w, http.StatusNotImplemented, map[string]string{"error": "stripe integration coming soon"})
}

func (h *SubscriptionsHandler) StripeWebhook(w http.ResponseWriter, _ *http.Request) {
	respond.JSON(w, http.StatusNotImplemented, map[string]string{"error": "stripe integration coming soon"})
}
