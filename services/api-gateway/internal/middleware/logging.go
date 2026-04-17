package middleware

import (
	"context"
	"log/slog"
	"net/http"
	"time"

	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/google/uuid"
)

func RequestLogger() func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			requestID := uuid.NewString()
			ctx := context.WithValue(r.Context(), ctxkey.RequestID, requestID)
			w.Header().Set("X-Request-ID", requestID)

			ww := &responseWriter{ResponseWriter: w, status: http.StatusOK}
			started := time.Now()
			next.ServeHTTP(ww, r.WithContext(ctx))

			slog.Default().InfoContext(ctx, "request",
				"request_id", requestID,
				"user_id", ctxkey.String(ctx, ctxkey.UserID),
				"method", r.Method,
				"path", r.URL.Path,
				"status", ww.status,
				"duration_ms", time.Since(started).Milliseconds(),
			)
		})
	}
}

type responseWriter struct {
	http.ResponseWriter
	status int
}

func (w *responseWriter) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}
