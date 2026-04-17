package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	sharedlogger "github.com/estategap/libs/logger"
	"github.com/estategap/services/scrape-orchestrator/internal/config"
	"github.com/estategap/services/scrape-orchestrator/internal/db"
	"github.com/estategap/services/scrape-orchestrator/internal/handler"
	"github.com/estategap/services/scrape-orchestrator/internal/middleware"
	"github.com/estategap/services/scrape-orchestrator/internal/natsutil"
	"github.com/estategap/services/scrape-orchestrator/internal/redisclient"
	"github.com/estategap/services/scrape-orchestrator/internal/scheduler"
	"github.com/go-chi/chi/v5"
)

func main() {
	if err := run(); err != nil {
		slog.Error("scrape orchestrator exited", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}

	slog.SetDefault(sharedlogger.New(cfg.LogLevel))

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	dbClient, err := db.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return err
	}
	defer dbClient.Close()

	redisClient, err := redisclient.New(cfg.RedisURL)
	if err != nil {
		return err
	}
	defer func() { _ = redisClient.Close() }()

	natsClient, err := natsutil.New(cfg.NATSURL)
	if err != nil {
		return err
	}
	defer natsClient.Close()

	sched := scheduler.New(cfg.JobTTL)
	if cfg.TestScheduleOverride != "" {
		override, err := scheduler.ParseScheduleOverride(cfg.TestScheduleOverride)
		if err != nil {
			return err
		}
		slog.Info("[test-mode] Using schedule override: " + cfg.TestScheduleOverride)
		sched.SetFrequencyOverride(override)
	}
	if err := sched.Start(ctx, dbClient, natsClient, redisClient); err != nil {
		return err
	}
	defer sched.Stop()
	go sched.WatchReload(ctx, dbClient, cfg.PortalReloadInterval)

	triggerHandler := handler.NewTriggerHandler(sched)
	statusHandler := handler.NewStatusHandler(redisClient)
	statsHandler := handler.NewStatsHandler(redisClient)
	healthHandler := handler.NewHealthHandler(dbClient, natsClient, redisClient)

	router := chi.NewRouter()
	router.Use(middleware.RequestLogger())
	router.Post("/jobs/trigger", triggerHandler.Trigger)
	router.Get("/jobs/{id}/status", statusHandler.Status)
	router.Get("/jobs/stats", statsHandler.Stats)
	router.Get("/health", healthHandler.Health)

	server := &http.Server{
		Addr:              ":" + cfg.HTTPPort,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	errCh := make(chan error, 1)
	go func() {
		slog.Info("scrape orchestrator server started", "addr", server.Addr)
		if serveErr := server.ListenAndServe(); serveErr != nil && !errors.Is(serveErr, http.ErrServerClosed) {
			errCh <- serveErr
		}
	}()

	select {
	case <-ctx.Done():
	case err := <-errCh:
		return err
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := natsClient.Drain(); err != nil {
		slog.Warn("failed to drain nats connection", "error", err)
	}
	return server.Shutdown(shutdownCtx)
}
