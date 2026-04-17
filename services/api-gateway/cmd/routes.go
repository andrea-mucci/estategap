package main

import (
	"github.com/estategap/services/api-gateway/internal/handler"
	"github.com/go-chi/chi/v5"
)

func mountZoneRoutes(r chi.Router, zonesHandler *handler.ZonesHandler) {
	r.Get("/zones/compare", zonesHandler.Compare)
	r.Get("/zones", zonesHandler.List)
	r.Get("/zones/{id}", zonesHandler.Get)
	r.Get("/zones/{id}/analytics", zonesHandler.Analytics)
}

func mountAuthenticatedV1Routes(
	r chi.Router,
	listingsHandler *handler.ListingsHandler,
	zonesHandler *handler.ZonesHandler,
	referenceHandler *handler.ReferenceHandler,
	alertsHandler *handler.AlertsHandler,
	subscriptionsHandler *handler.SubscriptionsHandler,
) {
	r.Get("/listings", listingsHandler.List)
	r.Get("/listings/{id}", listingsHandler.Get)
	mountZoneRoutes(r, zonesHandler)
	r.Get("/countries", referenceHandler.Countries)
	r.Get("/portals", referenceHandler.Portals)
	r.Get("/alerts", alertsHandler.List)
	r.Post("/alerts", alertsHandler.Create)
	r.Get("/alerts/{id}", alertsHandler.Get)
	r.Put("/alerts/{id}", alertsHandler.Update)
	r.Delete("/alerts/{id}", alertsHandler.Delete)
	r.Get("/alerts/{id}/history", alertsHandler.History)
	r.Post("/subscriptions/checkout", subscriptionsHandler.Checkout)
}
