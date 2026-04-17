package main

import (
	"net/http"

	"github.com/estategap/services/ws-server/internal/handler"
	"github.com/go-chi/chi/v5"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func newRouter(wsHandler *handler.WSHandler, healthHandler *handler.HealthHandler) http.Handler {
	router := chi.NewRouter()
	router.Handle("/ws/chat", wsHandler)
	router.Get("/healthz", healthHandler.Liveness)
	router.Get("/readyz", healthHandler.Readiness)
	router.Handle("/metrics", promhttp.Handler())
	return router
}
