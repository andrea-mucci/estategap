package handler

import (
	"net/http"
	"strings"
	"time"

	"github.com/estategap/libs/s3client"
	"github.com/estategap/services/api-gateway/internal/respond"
)

type ExportPresignHandler struct {
	s3 s3client.S3Operations
}

func NewExportPresignHandler(s3 s3client.S3Operations) *ExportPresignHandler {
	return &ExportPresignHandler{s3: s3}
}

func (h *ExportPresignHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	key := r.URL.Query().Get("key")
	if key == "" {
		writeError(w, r, http.StatusBadRequest, "key is required")
		return
	}

	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}
	if !strings.HasPrefix(key, userID.String()+"/") {
		writeError(w, r, http.StatusForbidden, "key does not belong to the authenticated user")
		return
	}

	url, err := h.s3.PresignGetObject(r.Context(), h.s3.BucketName("exports"), key, time.Hour)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to generate export download URL")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"bucket": h.s3.BucketName("exports"),
		"key":    key,
		"url":    url,
	})
}
