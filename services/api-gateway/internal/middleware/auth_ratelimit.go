package middleware

import (
	"math"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/redis/go-redis/v9"
)

func AuthRateLimitMiddleware(redisClient *redis.Client) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if redisClient == nil || !isAuthAttemptRequest(r) {
				next.ServeHTTP(w, r)
				return
			}

			clientIP := requestClientIP(r)
			if clientIP == "" {
				next.ServeHTTP(w, r)
				return
			}

			key := "auth:attempts:" + clientIP
			count, err := redisClient.Incr(r.Context(), key).Result()
			if err != nil {
				next.ServeHTTP(w, r)
				return
			}
			if count == 1 {
				_ = redisClient.Expire(r.Context(), key, time.Minute).Err()
			}
			if count <= 5 {
				next.ServeHTTP(w, r)
				return
			}

			ttl, err := redisClient.TTL(r.Context(), key).Result()
			if err != nil || ttl <= 0 {
				ttl = time.Minute
			}

			retryAfter := int(math.Ceil(ttl.Seconds()))
			if retryAfter < 1 {
				retryAfter = 60
			}

			w.Header().Set("Retry-After", strconv.Itoa(retryAfter))
			respond.Error(w, http.StatusTooManyRequests, "too many auth attempts", respond.RequestIDFromContext(r.Context()))
		})
	}
}

func isAuthAttemptRequest(r *http.Request) bool {
	if r.Method != http.MethodPost {
		return false
	}

	switch r.URL.Path {
	case "/v1/auth/login", "/api/v1/auth/login", "/v1/auth/register", "/api/v1/auth/register", "/v1/auth/refresh", "/api/v1/auth/refresh":
		return true
	default:
		return false
	}
}

func requestClientIP(r *http.Request) string {
	for _, header := range []string{"CF-Connecting-IP", "X-Forwarded-For", "X-Real-IP"} {
		if value := strings.TrimSpace(r.Header.Get(header)); value != "" {
			if header == "X-Forwarded-For" {
				value = strings.TrimSpace(strings.Split(value, ",")[0])
			}
			return value
		}
	}

	host, _, err := net.SplitHostPort(strings.TrimSpace(r.RemoteAddr))
	if err == nil {
		return host
	}
	return strings.TrimSpace(r.RemoteAddr)
}
