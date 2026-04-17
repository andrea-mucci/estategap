package main

import (
	"net/http"

	"github.com/estategap/services/api-gateway/internal/handler"
	gatewaymw "github.com/estategap/services/api-gateway/internal/middleware"
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
	mlHandler *handler.MLHandler,
	alertRulesHandler *handler.AlertRulesHandler,
	subscriptionsHandler *handler.SubscriptionsHandler,
) {
	r.Get("/listings", listingsHandler.List)
	r.Get("/listings/{id}", listingsHandler.Get)
	mountZoneRoutes(r, zonesHandler)
	r.Get("/countries", referenceHandler.Countries)
	r.Get("/portals", referenceHandler.Portals)
	r.Get("/model/estimate", mlHandler.Estimate)
	r.Route("/alerts", func(r chi.Router) {
		r.Get("/rules", alertRulesHandler.ListAlertRules)
		r.Post("/rules", alertRulesHandler.CreateAlertRule)
		r.Put("/rules/{id}", alertRulesHandler.UpdateAlertRule)
		r.Delete("/rules/{id}", alertRulesHandler.DeleteAlertRule)
		r.Get("/history", alertRulesHandler.ListAlertHistory)
	})
	r.Post("/subscriptions/checkout", subscriptionsHandler.Checkout)
	r.Post("/subscriptions/portal", subscriptionsHandler.Portal)
	r.Get("/subscriptions/me", subscriptionsHandler.Me)
}

func mountAuthRoutes(
	r chi.Router,
	authHandler *handler.AuthHandler,
	googleOAuthHandler *handler.GoogleOAuthHandler,
	authenticator func(http.Handler) http.Handler,
	rateLimiter func(http.Handler) http.Handler,
) {
	r.Post("/register", authHandler.Register)
	r.Post("/login", authHandler.Login)
	r.Post("/refresh", authHandler.Refresh)
	r.Get("/google", googleOAuthHandler.Redirect)
	r.Get("/google/callback", googleOAuthHandler.Callback)

	r.Group(func(r chi.Router) {
		r.Use(authenticator)
		r.Use(gatewaymw.RequireAuth)
		r.Use(rateLimiter)
		r.Post("/logout", authHandler.Logout)
		r.Get("/me", authHandler.Me)
	})
}
