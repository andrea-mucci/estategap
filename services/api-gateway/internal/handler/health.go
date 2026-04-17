package handler

import (
	"context"
	"net/http"
	"sync"
	"time"

	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

type HealthHandler struct {
	primary *pgxpool.Pool
	redis   *redis.Client
}

type readinessStatus struct {
	Status string            `json:"status"`
	Checks map[string]string `json:"checks"`
}

func NewHealthHandler(primary *pgxpool.Pool, redisClient *redis.Client) *HealthHandler {
	return &HealthHandler{
		primary: primary,
		redis:   redisClient,
	}
}

func (h *HealthHandler) Healthz(w http.ResponseWriter, _ *http.Request) {
	respond.JSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (h *HealthHandler) Readyz(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	checks := map[string]string{
		"postgres": "ok",
		"redis":    "ok",
	}

	var (
		mu       sync.Mutex
		wg       sync.WaitGroup
		hasError bool
	)

	run := func(name string, fn func(context.Context) error) {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := fn(ctx); err != nil {
				mu.Lock()
				checks[name] = "error"
				hasError = true
				mu.Unlock()
			}
		}()
	}

	run("postgres", h.primary.Ping)
	run("redis", func(ctx context.Context) error { return h.redis.Ping(ctx).Err() })
	wg.Wait()

	status := readinessStatus{Status: "ok", Checks: checks}
	if hasError {
		status.Status = "degraded"
		respond.JSON(w, http.StatusServiceUnavailable, status)
		return
	}

	respond.JSON(w, http.StatusOK, status)
}
