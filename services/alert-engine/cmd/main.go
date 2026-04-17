package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/estategap/services/alert-engine/internal/cache"
	"github.com/estategap/services/alert-engine/internal/config"
	"github.com/estategap/services/alert-engine/internal/dedup"
	"github.com/estategap/services/alert-engine/internal/digest"
	"github.com/estategap/services/alert-engine/internal/matcher"
	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/publisher"
	"github.com/estategap/services/alert-engine/internal/repository"
	routepkg "github.com/estategap/services/alert-engine/internal/router"
	"github.com/estategap/services/alert-engine/internal/worker"
	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

func main() {
	if err := run(); err != nil {
		slog.Error("alert engine exited", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}

	slog.SetDefault(newLogger(strings.ToUpper(cfg.LogLevel)))

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	primaryPool, err := newPool(ctx, cfg.DatabaseURL, 20)
	if err != nil {
		return err
	}
	defer primaryPool.Close()

	replicaPool, err := newPool(ctx, cfg.DatabaseReplicaURL, 40)
	if err != nil {
		return err
	}
	defer replicaPool.Close()

	redisClient, err := newRedis(cfg.RedisURL)
	if err != nil {
		return err
	}
	defer func() { _ = redisClient.Close() }()

	natsConn, js, err := newNATS(cfg.NatsURL)
	if err != nil {
		return err
	}
	defer natsConn.Close()

	metricsRegistry := metrics.New()
	ruleRepo := repository.New(primaryPool, replicaPool)
	historyRepo := repository.NewHistoryRepo(primaryPool, replicaPool)
	ruleCache := cache.New(metricsRegistry)
	if err := ruleCache.Load(ctx, ruleRepo); err != nil {
		return err
	}

	dedupStore := dedup.New(redisClient, metricsRegistry)
	buffer := digest.NewBuffer(redisClient, metricsRegistry)
	publisherClient := publisher.New(js, metricsRegistry)
	engine := matcher.New(ruleCache, replicaPool, dedupStore, cfg.WorkerPoolSize, metricsRegistry)
	router := routepkg.New(publisherClient, buffer)
	processor := worker.NewProcessor(engine, router, ruleRepo, historyRepo, dedupStore)
	consumer := worker.NewConsumer(js, metricsRegistry)
	compiler := digest.NewCompiler(redisClient, buffer, ruleRepo, publisherClient, historyRepo, ruleCache)

	httpServer := &http.Server{
		Addr:              fmt.Sprintf(":%d", cfg.HealthPort),
		Handler:           newRouter(primaryPool, redisClient, natsConn),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	errCh := make(chan error, 6)
	go func() {
		errCh <- serveHTTP(ctx, httpServer)
	}()
	go func() {
		ruleCache.StartRefresh(ctx, ruleRepo, cfg.RuleCacheRefreshInterval)
		errCh <- nil
	}()
	go func() {
		errCh <- consumer.StartScoredListings(ctx, cfg.BatchSize, processor.HandleScoredListing)
	}()
	go func() {
		errCh <- consumer.StartPriceChanges(ctx, processor.HandlePriceChange)
	}()
	go func() {
		errCh <- compiler.StartHourly(ctx)
	}()
	go func() {
		errCh <- compiler.StartDaily(ctx)
	}()

	var firstErr error
	for i := 0; i < cap(errCh); i++ {
		if err := <-errCh; err != nil && !errors.Is(err, context.Canceled) && firstErr == nil {
			firstErr = err
			stop()
		}
	}

	if firstErr != nil {
		return firstErr
	}
	return nil
}

func newRouter(primaryPool *pgxpool.Pool, redisClient *redis.Client, natsConn *nats.Conn) http.Handler {
	router := chi.NewRouter()
	router.Get("/health/live", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	router.Get("/health/ready", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()

		if err := primaryPool.Ping(ctx); err != nil {
			http.Error(w, "database not ready", http.StatusServiceUnavailable)
			return
		}
		if err := redisClient.Ping(ctx).Err(); err != nil {
			http.Error(w, "redis not ready", http.StatusServiceUnavailable)
			return
		}
		if natsConn == nil || natsConn.Status() == nats.CLOSED {
			http.Error(w, "nats not ready", http.StatusServiceUnavailable)
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	router.Handle("/metrics", promhttp.Handler())
	return router
}

func serveHTTP(ctx context.Context, server *http.Server) error {
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
	}()

	slog.Info("alert engine HTTP server started", "addr", server.Addr)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

func newPool(ctx context.Context, dsn string, maxConns int32) (*pgxpool.Pool, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, err
	}

	cfg.MaxConns = maxConns
	cfg.MinConns = 2
	cfg.MaxConnIdleTime = 5 * time.Minute
	cfg.HealthCheckPeriod = 30 * time.Second
	cfg.MaxConnLifetime = 30 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}

	return pool, nil
}

func newRedis(url string) (*redis.Client, error) {
	opts, err := redis.ParseURL(url)
	if err != nil {
		return nil, err
	}

	client := redis.NewClient(opts)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		_ = client.Close()
		return nil, err
	}

	return client, nil
}

func newNATS(url string) (*nats.Conn, nats.JetStreamContext, error) {
	conn, err := nats.Connect(
		url,
		nats.Name("alert-engine"),
		nats.Timeout(5*time.Second),
		nats.RetryOnFailedConnect(true),
		nats.MaxReconnects(-1),
		nats.ReconnectWait(2*time.Second),
	)
	if err != nil {
		return nil, nil, err
	}

	js, err := conn.JetStream()
	if err != nil {
		conn.Close()
		return nil, nil, err
	}

	return conn, js, nil
}

func newLogger(level string) *slog.Logger {
	var slogLevel slog.Level
	switch strings.ToUpper(strings.TrimSpace(level)) {
	case "DEBUG":
		slogLevel = slog.LevelDebug
	case "WARN":
		slogLevel = slog.LevelWarn
	case "ERROR":
		slogLevel = slog.LevelError
	default:
		slogLevel = slog.LevelInfo
	}

	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slogLevel}))
}
