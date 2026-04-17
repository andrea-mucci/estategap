package router

import (
	"context"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/nats-io/nats.go"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

type dbPinger interface {
	Ping(context.Context) error
}

type Router struct {
	db    dbPinger
	redis *redis.Client
	nats  *nats.Conn
}

func New(db dbPinger, redisClient *redis.Client, natsConn *nats.Conn) http.Handler {
	r := &Router{
		db:    db,
		redis: redisClient,
		nats:  natsConn,
	}

	router := chi.NewRouter()
	router.Get("/healthz", r.healthz)
	router.Get("/readyz", r.readyz)
	router.Handle("/metrics", promhttp.Handler())
	return router
}

func (r *Router) healthz(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}

func (r *Router) readyz(w http.ResponseWriter, req *http.Request) {
	ctx, cancel := context.WithTimeout(req.Context(), 2*time.Second)
	defer cancel()

	if r.db != nil {
		if err := r.db.Ping(ctx); err != nil {
			http.Error(w, "database not ready", http.StatusServiceUnavailable)
			return
		}
	}
	if r.redis != nil {
		if err := r.redis.Ping(ctx).Err(); err != nil {
			http.Error(w, "redis not ready", http.StatusServiceUnavailable)
			return
		}
	}
	if r.nats != nil && r.nats.Status() == nats.CLOSED {
		http.Error(w, "nats not ready", http.StatusServiceUnavailable)
		return
	}

	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}
