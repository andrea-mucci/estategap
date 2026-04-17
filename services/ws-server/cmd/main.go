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

	"github.com/estategap/services/ws-server/internal/config"
	grpcclient "github.com/estategap/services/ws-server/internal/grpc"
	"github.com/estategap/services/ws-server/internal/handler"
	"github.com/estategap/services/ws-server/internal/hub"
	wsnats "github.com/estategap/services/ws-server/internal/nats"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"
	ggrpc "google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	if err := run(); err != nil {
		slog.Error("ws-server exited", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}

	slog.SetDefault(newLogger(cfg.LogLevel))

	signalCtx, stopSignal := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stopSignal()

	redisClient, err := newRedis(cfg.RedisAddr)
	if err != nil {
		return err
	}
	defer func() { _ = redisClient.Close() }()

	grpcConn, err := ggrpc.NewClient(
		cfg.AIChatGRPCAddr,
		ggrpc.WithTransportCredentials(insecure.NewCredentials()),
		ggrpc.WithDefaultCallOptions(ggrpc.WaitForReady(true)),
	)
	if err != nil {
		return err
	}
	defer func() { _ = grpcConn.Close() }()

	natsConn, js, err := newNATS(cfg.NATSAddr)
	if err != nil {
		return err
	}
	defer natsConn.Close()

	h := hub.New(cfg.MaxConnections)
	chatClient := grpcclient.New(grpcConn)
	consumer := wsnats.New(js, h, cfg)
	if err := consumer.Setup(); err != nil {
		return err
	}

	wsHandler := handler.NewWSHandler(h, chatClient, cfg, redisClient)
	healthHandler := handler.NewHealthHandler(redisClient, natsConn, grpcConn)

	httpSrv := &http.Server{
		Addr:              fmt.Sprintf(":%d", cfg.Port),
		Handler:           newRouter(wsHandler, healthHandler),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	runCtx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errCh := make(chan error, 2)
	go func() {
		errCh <- serveHTTP(httpSrv)
	}()
	go func() {
		errCh <- consumer.Start(runCtx)
	}()

	select {
	case <-signalCtx.Done():
		slog.Info("shutdown signal received")
	case err := <-errCh:
		if err != nil && !errors.Is(err, context.Canceled) {
			cancel()
			consumer.Stop()
			return err
		}
	}

	cancel()

	shutdownCtx, cancelShutdown := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancelShutdown()
	_ = httpSrv.Shutdown(shutdownCtx)

	h.Shutdown(cfg.ShutdownTimeout)
	consumer.Stop()
	_ = natsConn.Drain()
	_ = grpcConn.Close()

	return nil
}

func serveHTTP(server *http.Server) error {
	slog.Info("ws-server HTTP server started", "addr", server.Addr)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

func newRedis(addr string) (*redis.Client, error) {
	client := redis.NewClient(&redis.Options{Addr: addr})
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
		nats.Name("ws-server"),
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
