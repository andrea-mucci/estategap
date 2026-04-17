package respond

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/estategap/services/api-gateway/internal/ctxkey"
)

type ErrorResponse struct {
	Error     string `json:"error"`
	RequestID string `json:"request_id"`
}

func JSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if v == nil {
		return
	}

	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}

func Error(w http.ResponseWriter, status int, message, requestID string) {
	JSON(w, status, ErrorResponse{
		Error:     message,
		RequestID: requestID,
	})
}

func NoContent(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNoContent)
}

func RequestIDFromContext(ctx context.Context) string {
	return ctxkey.String(ctx, ctxkey.RequestID)
}
