package handler

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/redis/go-redis/v9"
	ggrpc "google.golang.org/grpc"
	"google.golang.org/grpc/connectivity"
)

type brokerChecker interface {
	Ping(context.Context) error
}

type HealthHandler struct {
	redis *redis.Client
	kafka brokerChecker
	grpc  *ggrpc.ClientConn
}

func NewHealthHandler(redisClient *redis.Client, kafkaClient brokerChecker, grpcConn *ggrpc.ClientConn) *HealthHandler {
	return &HealthHandler{
		redis: redisClient,
		kafka: kafkaClient,
		grpc:  grpcConn,
	}
}

func (h *HealthHandler) Liveness(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func (h *HealthHandler) Readiness(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	failures := make([]string, 0, 3)
	if h.kafka == nil || h.kafka.Ping(ctx) != nil {
		failures = append(failures, "kafka")
	}
	if h.redis == nil || h.redis.Ping(ctx).Err() != nil {
		failures = append(failures, "redis")
	}
	if h.grpc == nil || h.grpc.GetState() == connectivity.Shutdown {
		failures = append(failures, "grpc")
	}

	w.Header().Set("Content-Type", "application/json")
	if len(failures) == 0 {
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
		return
	}

	w.WriteHeader(http.StatusServiceUnavailable)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"status":   "degraded",
		"failures": failures,
	})
}
