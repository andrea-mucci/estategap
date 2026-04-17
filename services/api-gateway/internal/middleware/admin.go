package middleware

import (
	"net/http"
	"strings"

	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/respond"
)

func RequireAdmin(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.EqualFold(ctxkey.String(r.Context(), ctxkey.UserRole), "admin") {
			next.ServeHTTP(w, r)
			return
		}

		respond.Error(w, http.StatusForbidden, "admin access required", respond.RequestIDFromContext(r.Context()))
	})
}
