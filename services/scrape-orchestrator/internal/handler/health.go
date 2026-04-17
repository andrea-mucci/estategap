package handler

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/estategap/services/scrape-orchestrator/internal/db"
	"github.com/estategap/services/scrape-orchestrator/internal/redisclient"
)

type pinger interface {
	Ping(context.Context) error
}

type HealthHandler struct {
	db    db.Querier
	kafka pinger
	redis *redisclient.Client
}

func NewHealthHandler(dbClient db.Querier, kafkaClient pinger, redisClient *redisclient.Client) *HealthHandler {
	return &HealthHandler{
		db:    dbClient,
		kafka: kafkaClient,
		redis: redisClient,
	}
}

func (h *HealthHandler) Health(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	response := map[string]string{
		"status": "ok",
		"db":     "ok",
		"kafka":  "ok",
		"redis":  "ok",
	}
	statusCode := http.StatusOK

	if err := h.db.Ping(ctx); err != nil {
		response["db"] = "error"
		response["status"] = "error"
		statusCode = http.StatusServiceUnavailable
	}
	if err := h.kafka.Ping(ctx); err != nil {
		response["kafka"] = "error"
		response["status"] = "error"
		statusCode = http.StatusServiceUnavailable
	}
	if err := h.redis.Ping(ctx).Err(); err != nil {
		response["redis"] = "error"
		response["status"] = "error"
		statusCode = http.StatusServiceUnavailable
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(response)
}
