package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/estategap/services/api-gateway/internal/handler"
	"github.com/go-chi/chi/v5"
)

func TestMountZoneRoutesPrefersCompareRoute(t *testing.T) {
	t.Parallel()

	router := chi.NewRouter()
	mountZoneRoutes(router, handler.NewZonesHandler(nil))

	req := httptest.NewRequest(http.MethodGet, "/zones/compare", nil)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusBadRequest)
	}

	body, err := io.ReadAll(rec.Body)
	if err != nil {
		t.Fatalf("ReadAll() error = %v", err)
	}

	if !strings.Contains(string(body), "ids query param is required") {
		t.Fatalf("body = %s, want compare-route validation error", string(body))
	}
}
