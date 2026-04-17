package handler

import (
	"net/http"
	"strings"

	embeddeddocs "github.com/estategap/services/api-gateway/internal/docs"
)

type DocsHandler struct {
	uiHandler http.Handler
}

func NewDocsHandler() *DocsHandler {
	return &DocsHandler{
		uiHandler: http.FileServer(http.FS(embeddeddocs.SwaggerUIFS())),
	}
}

func (h *DocsHandler) ServeOpenAPISpec(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(embeddeddocs.OpenAPIJSON())
}

func (h *DocsHandler) ServeSwaggerUI(w http.ResponseWriter, r *http.Request) {
	request := r.Clone(r.Context())
	request.URL.Path = strings.TrimPrefix(r.URL.Path, "/api/docs")
	if request.URL.Path == "" || request.URL.Path == "/" {
		request.URL.Path = "/index.html"
	}
	h.uiHandler.ServeHTTP(w, request)
}
