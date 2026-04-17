package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDocsHandlerServeOpenAPISpec(t *testing.T) {
	t.Parallel()

	handler := NewDocsHandler()
	req := httptest.NewRequest(http.MethodGet, "/api/openapi.json", nil)
	rec := httptest.NewRecorder()

	handler.ServeOpenAPISpec(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
	}
	if got := rec.Header().Get("Content-Type"); got != "application/json" {
		t.Fatalf("Content-Type = %q, want %q", got, "application/json")
	}

	var payload map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("Unmarshal() error = %v", err)
	}

	if got := payload["openapi"]; got != "3.1.0" {
		t.Fatalf("openapi = %v, want %q", got, "3.1.0")
	}

	info, ok := payload["info"].(map[string]any)
	if !ok {
		t.Fatalf("info = %T, want object", payload["info"])
	}
	if title, _ := info["title"].(string); strings.TrimSpace(title) == "" {
		t.Fatalf("info.title = %q, want non-empty title", title)
	}
}

func TestDocsHandlerServeSwaggerUI(t *testing.T) {
	t.Parallel()

	handler := NewDocsHandler()
	req := httptest.NewRequest(http.MethodGet, "/api/docs/index.html", nil)
	rec := httptest.NewRecorder()

	handler.ServeSwaggerUI(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
	}
	if got := rec.Header().Get("Content-Type"); !strings.HasPrefix(got, "text/html") {
		t.Fatalf("Content-Type = %q, want text/html", got)
	}
	if body := rec.Body.String(); !strings.Contains(body, `url: "/api/openapi.json"`) {
		t.Fatalf("body missing OpenAPI URL bootstrap: %s", body)
	}
}
