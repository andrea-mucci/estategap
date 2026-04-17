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
	sharedlogger "github.com/estategap/libs/logger"
	"github.com/estategap/services/alert-dispatcher/internal/config"
	"github.com/estategap/services/alert-dispatcher/internal/consumer"
	"github.com/estategap/services/alert-dispatcher/internal/dispatcher"
	"github.com/estategap/services/alert-dispatcher/internal/metrics"
	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/estategap/services/alert-dispatcher/internal/repository"
	routerpkg "github.com/estategap/services/alert-dispatcher/internal/router"
	senderpkg "github.com/estategap/services/alert-dispatcher/internal/sender"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
	"golang.org/x/sync/errgroup"
)

func main() {
	if err := run(); err != nil {
		slog.Error("alert dispatcher exited", "error", err)
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

	kafkaBroker, err := sharedbroker.NewKafkaBroker(sharedbroker.KafkaConfig{
		Brokers:     splitCSV(cfg.KafkaBrokers),
		TopicPrefix: cfg.KafkaTopicPrefix,
	})
	if err != nil {
		return err
	}
	defer func() { _ = kafkaBroker.Close() }()

	registry := metrics.New()
	userRepo := repository.NewUserRepo(primaryPool, replicaPool)
	historyRepo := repository.NewHistoryRepo(primaryPool, replicaPool)
	senders, err := buildSenders(ctx, cfg, redisClient, userRepo)
	if err != nil {
		return err
	}
	dispatcherSvc := dispatcher.New(senders, historyRepo, userRepo, registry)
	consumerSvc := consumer.New(kafkaBroker, dispatcherSvc, registry, cfg.WorkerPoolSize)

	httpServer := &http.Server{
		Addr:              fmt.Sprintf(":%d", cfg.HealthPort),
		Handler: routerpkg.New(primaryPool, redisClient, &kafkaHealthChecker{
			dialer:  kafkaBroker.Dialer(),
			brokers: splitCSV(cfg.KafkaBrokers),
		}),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	group, groupCtx := errgroup.WithContext(ctx)
	group.Go(func() error {
		return serveHTTP(groupCtx, httpServer)
	})
	group.Go(func() error {
		return consumerSvc.Start(groupCtx, cfg.BatchSize)
	})

	return group.Wait()
}

func serveHTTP(ctx context.Context, server *http.Server) error {
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
	}()

	slog.Info("alert dispatcher HTTP server started", "addr", server.Addr)
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

func buildSenders(
	ctx context.Context,
	cfg *config.Config,
	redisClient *redis.Client,
	userRepo *repository.UserRepo,
) (map[string]senderpkg.Sender, error) {
	senders := make(map[string]senderpkg.Sender)

	emailClient := senderpkg.NewSESEmailClient(cfg.AWSRegion)
	emailSender, err := senderpkg.NewEmailSender(emailClient, cfg.BaseURL, cfg.AWSSesFromAddress, cfg.AWSSesFromName)
	if err != nil {
		return nil, err
	}
	senders[model.ChannelEmail] = emailSender

	if strings.TrimSpace(cfg.TelegramBotToken) != "" {
		telegramAPI := senderpkg.NewTelegramHTTPClient(cfg.TelegramBotToken)
		senders[model.ChannelTelegram] = senderpkg.NewTelegramSender(ctx, telegramAPI, userRepo, cfg.BaseURL)
	}

	if strings.TrimSpace(cfg.TwilioAccountSID) != "" &&
		strings.TrimSpace(cfg.TwilioAuthToken) != "" &&
		strings.TrimSpace(cfg.TwilioWhatsAppFrom) != "" &&
		strings.TrimSpace(cfg.TwilioWhatsAppTemplate) != "" {
		whatsAppAPI := senderpkg.NewWhatsAppHTTPClient(cfg.TwilioAccountSID, cfg.TwilioAuthToken)
		senders[model.ChannelWhatsApp] = senderpkg.NewWhatsAppSender(
			whatsAppAPI,
			cfg.TwilioWhatsAppFrom,
			cfg.TwilioWhatsAppTemplate,
			cfg.BaseURL,
		)
	}

	if strings.TrimSpace(cfg.FirebaseCredentialsJSON) != "" {
		pushClient, err := senderpkg.NewFCMHTTPClient(ctx, cfg.FirebaseCredentialsJSON)
		if err != nil {
			return nil, err
		}
		senders[model.ChannelPush] = senderpkg.NewPushSender(pushClient, userRepo, cfg.BaseURL)
	}

	senders[model.ChannelWebhook] = senderpkg.NewWebhookSender(nil, redisClient)

	return senders, nil
}
