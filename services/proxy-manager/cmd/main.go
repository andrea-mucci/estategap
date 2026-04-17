package main

import (
	"context"
	"errors"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	sharedlogger "github.com/estategap/libs/logger"
	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"github.com/estategap/services/proxy-manager/internal/blacklist"
	"github.com/estategap/services/proxy-manager/internal/config"
	grpcserver "github.com/estategap/services/proxy-manager/internal/grpc"
	"github.com/estategap/services/proxy-manager/internal/pool"
	"github.com/estategap/services/proxy-manager/internal/provider"
	"github.com/estategap/services/proxy-manager/internal/redisclient"
	"github.com/estategap/services/proxy-manager/internal/sticky"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	grpcpkg "google.golang.org/grpc"
)

func main() {
	if err := run(); err != nil {
		slog.Error("proxy manager exited", "error", err)
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

	redisClient, err := redisclient.New(cfg.RedisURL)
	if err != nil {
		return err
	}
	defer func() { _ = redisClient.Close() }()

	proxyPool := pool.New(cfg.HealthThreshold)
	if err := proxyPool.LoadFromConfig(cfg, provider.Registry{}); err != nil {
		return err
	}

	blacklistStore := blacklist.New(redisClient)
	stickyStore := sticky.New(redisClient, cfg.StickyTTL)
	service := grpcserver.NewServer(redisClient, proxyPool, blacklistStore, stickyStore, cfg.BlacklistTTL)

	grpcListener, err := net.Listen("tcp", ":"+cfg.GRPCPort)
	if err != nil {
		return err
	}
	defer grpcListener.Close()

	grpcServer := grpcpkg.NewServer()
	estategapv1.RegisterProxyServiceServer(grpcServer, service)

	metricsMux := http.NewServeMux()
	metricsMux.Handle("/metrics", promhttp.Handler())
	metricsServer := &http.Server{
		Addr:              ":" + cfg.MetricsPort,
		Handler:           metricsMux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	errCh := make(chan error, 2)
	go func() {
		slog.Info("proxy manager gRPC server started", "addr", grpcListener.Addr().String())
		if serveErr := grpcServer.Serve(grpcListener); serveErr != nil {
			errCh <- serveErr
		}
	}()
	go func() {
		slog.Info("proxy manager metrics server started", "addr", metricsServer.Addr)
		if serveErr := metricsServer.ListenAndServe(); serveErr != nil && !errors.Is(serveErr, http.ErrServerClosed) {
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

	grpcServer.GracefulStop()
	return metricsServer.Shutdown(shutdownCtx)
}
