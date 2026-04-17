package middleware

import (
	"log/slog"
	"math"
	"net/http"
	"strconv"
	"time"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/redis/go-redis/v9"
)

func RateLimiter(redisClient *redis.Client) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			userID := ctxkey.String(r.Context(), ctxkey.UserID)
			if userID == "" {
				next.ServeHTTP(w, r)
				return
			}

			tier := models.SubscriptionTier(ctxkey.String(r.Context(), ctxkey.UserTier))
			limit := requestLimit(tier)
			key := "ratelimit:" + userID

			count, err := redisClient.Incr(r.Context(), key).Result()
			if err != nil {
				slog.Error("rate limit lookup failed", "user_id", userID, "error", err)
				next.ServeHTTP(w, r)
				return
			}
			if count == 1 {
				if err := redisClient.Expire(r.Context(), key, time.Minute).Err(); err != nil {
					slog.Error("rate limit expire failed", "user_id", userID, "error", err)
				}
			}
			if count <= int64(limit) {
				next.ServeHTTP(w, r)
				return
			}

			ttl, err := redisClient.PTTL(r.Context(), key).Result()
			if err != nil {
				slog.Error("rate limit ttl failed", "user_id", userID, "error", err)
				ttl = time.Minute
			}
			retryAfter := int(math.Ceil(ttl.Seconds()))
			if retryAfter < 1 {
				retryAfter = 1
			}

			w.Header().Set("Retry-After", strconv.Itoa(retryAfter))
			respond.Error(w, http.StatusTooManyRequests, "rate limit exceeded", respond.RequestIDFromContext(r.Context()))
		})
	}
}

func requestLimit(tier models.SubscriptionTier) int {
	switch tier {
	case models.SubscriptionTierBasic:
		return 120
	case models.SubscriptionTierPro:
		return 300
	case models.SubscriptionTierGlobal:
		return 600
	case models.SubscriptionTierAPI:
		return 1200
	default:
		return 30
	}
}
