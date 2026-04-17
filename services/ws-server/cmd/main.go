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

	sharedbroker "github.com/estategap/libs/broker"
	"github.com/estategap/services/ws-server/internal/config"
	grpcclient "github.com/estategap/services/ws-server/internal/grpc"
	"github.com/estategap/services/ws-server/internal/handler"
	"github.com/estategap/services/ws-server/internal/hub"
	wskafka "github.com/estategap/services/ws-server/internal/kafka"
	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
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

	kafkaBroker, err := sharedbroker.NewKafkaBroker(sharedbroker.KafkaConfig{
		Brokers:     splitCSV(cfg.KafkaBrokers),
		TopicPrefix: cfg.KafkaTopicPrefix,
	})
	if err != nil {
		return err
	}
	defer func() { _ = kafkaBroker.Close() }()

	h := hub.New(cfg.MaxConnections)
	chatClient := grpcclient.New(grpcConn)
	consumer := wskafka.New(kafkaBroker, h, cfg)

	wsHandler := handler.NewWSHandler(h, chatClient, cfg, redisClient)
	healthHandler := handler.NewHealthHandler(redisClient, &kafkaHealthChecker{
		dialer:  kafkaBroker.Dialer(),
		brokers: splitCSV(cfg.KafkaBrokers),
	}, grpcConn)

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

type kafkaHealthChecker struct {
	dialer  *kafka.Dialer
	brokers []string
}

func (k *kafkaHealthChecker) Ping(ctx context.Context) error {
	if k == nil || k.dialer == nil || len(k.brokers) == 0 {
		return errors.New("kafka broker not configured")
	}

	conn, err := k.dialer.DialContext(ctx, "tcp", k.brokers[0])
	if err != nil {
		return err
	}
	return conn.Close()
}

func splitCSV(raw string) []string {
	parts := strings.Split(raw, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			values = append(values, trimmed)
		}
	}
	return values
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
