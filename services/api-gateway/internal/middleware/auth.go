package middleware

import (
	"context"
	"errors"
	"net/http"
	"strings"

	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/estategap/services/api-gateway/internal/service"
	"github.com/golang-jwt/jwt/v5"
	"github.com/redis/go-redis/v9"
)

func Authenticator(jwtSecret string, redisClient *redis.Client) func(http.Handler) http.Handler {
	secret := []byte(jwtSecret)

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			token := bearerToken(r.Header.Get("Authorization"))
			if token == "" {
				respond.Error(w, http.StatusUnauthorized, "missing bearer token", respond.RequestIDFromContext(r.Context()))
				return
			}

			claims := &service.AccessTokenClaims{}
			parsed, err := jwt.ParseWithClaims(token, claims, func(t *jwt.Token) (any, error) {
				if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
					return nil, errors.New("unexpected signing method")
				}
				return secret, nil
			})
			if err != nil || !parsed.Valid {
				respond.Error(w, http.StatusUnauthorized, "invalid token", respond.RequestIDFromContext(r.Context()))
				return
			}

			if claims.ID != "" {
				blacklisted, err := redisClient.Exists(r.Context(), "blacklist:"+claims.ID).Result()
				if err != nil || blacklisted > 0 {
					respond.Error(w, http.StatusUnauthorized, "invalid token", respond.RequestIDFromContext(r.Context()))
					return
				}
			}

			ctx := context.WithValue(r.Context(), ctxkey.UserID, claims.Subject)
			ctx = context.WithValue(ctx, ctxkey.UserEmail, claims.Email)
			ctx = context.WithValue(ctx, ctxkey.UserTier, claims.Tier)
			ctx = context.WithValue(ctx, ctxkey.UserRole, claims.Role)
			ctx = context.WithValue(ctx, ctxkey.JTI, claims.ID)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

func RequireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if ctxkey.String(r.Context(), ctxkey.UserID) == "" {
			respond.Error(w, http.StatusUnauthorized, "authentication required", respond.RequestIDFromContext(r.Context()))
			return
		}
		next.ServeHTTP(w, r)
	})
}

func bearerToken(header string) string {
	if !strings.HasPrefix(strings.ToLower(header), "bearer ") {
		return ""
	}
	return strings.TrimSpace(header[7:])
}
