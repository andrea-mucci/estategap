package handler

import (
	"net/http"
	"time"

	"github.com/estategap/libs/s3client"
	"github.com/estategap/services/api-gateway/internal/respond"
)

type PhotoPresignHandler struct {
	s3 s3client.S3Operations
}

func NewPhotoPresignHandler(s3 s3client.S3Operations) *PhotoPresignHandler {
	return &PhotoPresignHandler{s3: s3}
}

func (h *PhotoPresignHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	key := r.URL.Query().Get("key")
	if key == "" {
		writeError(w, r, http.StatusBadRequest, "key is required")
		return
	}

	url, err := h.s3.PresignGetObject(r.Context(), h.s3.BucketName("listing-photos"), key, time.Hour)
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to generate presigned URL")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]any{
		"bucket": h.s3.BucketName("listing-photos"),
		"key":    key,
		"url":    url,
	})
}
