package config

import (
	"fmt"
	"strings"
	"time"

	"github.com/spf13/viper"
)

type Config struct {
	Port            int
	JWTSecret       string
	RedisAddr       string
	AIChatGRPCAddr  string
	KafkaBrokers    string
	KafkaTopicPrefix string
	MaxConnections  int
	PingInterval    time.Duration
	PongTimeout     time.Duration
	IdleTimeout     time.Duration
	ShutdownTimeout time.Duration
	KafkaWorkers    int
	LogLevel        string
}

func Load() (*Config, error) {
	v := viper.New()
	v.SetConfigName(".env")
	v.SetConfigType("env")
	v.AddConfigPath(".")
	v.AddConfigPath("services/ws-server")
	v.AutomaticEnv()

	v.SetDefault("PORT", 8081)
	v.SetDefault("REDIS_ADDR", "localhost:6379")
	v.SetDefault("AI_CHAT_GRPC_ADDR", "ai-chat:50053")
	v.SetDefault("KAFKA_BROKERS", "localhost:9092")
	v.SetDefault("KAFKA_TOPIC_PREFIX", "estategap.")
	v.SetDefault("MAX_CONNECTIONS", 10000)
	v.SetDefault("PING_INTERVAL", "30s")
	v.SetDefault("PONG_TIMEOUT", "10s")
	v.SetDefault("IDLE_TIMEOUT", "30m")
	v.SetDefault("SHUTDOWN_TIMEOUT", "5s")
	v.SetDefault("KAFKA_WORKERS", 4)
	v.SetDefault("LOG_LEVEL", "INFO")

	_ = v.ReadInConfig()

	pingInterval, err := time.ParseDuration(strings.TrimSpace(v.GetString("PING_INTERVAL")))
	if err != nil {
		return nil, fmt.Errorf("parse PING_INTERVAL: %w", err)
	}
	pongTimeout, err := time.ParseDuration(strings.TrimSpace(v.GetString("PONG_TIMEOUT")))
	if err != nil {
		return nil, fmt.Errorf("parse PONG_TIMEOUT: %w", err)
	}
	idleTimeout, err := time.ParseDuration(strings.TrimSpace(v.GetString("IDLE_TIMEOUT")))
	if err != nil {
		return nil, fmt.Errorf("parse IDLE_TIMEOUT: %w", err)
	}
	shutdownTimeout, err := time.ParseDuration(strings.TrimSpace(v.GetString("SHUTDOWN_TIMEOUT")))
	if err != nil {
		return nil, fmt.Errorf("parse SHUTDOWN_TIMEOUT: %w", err)
	}

	cfg := &Config{
		Port:            v.GetInt("PORT"),
		JWTSecret:       strings.TrimSpace(v.GetString("JWT_SECRET")),
		RedisAddr:       strings.TrimSpace(v.GetString("REDIS_ADDR")),
		AIChatGRPCAddr:  strings.TrimSpace(v.GetString("AI_CHAT_GRPC_ADDR")),
		KafkaBrokers:    strings.TrimSpace(v.GetString("KAFKA_BROKERS")),
		KafkaTopicPrefix: strings.TrimSpace(v.GetString("KAFKA_TOPIC_PREFIX")),
		MaxConnections:  v.GetInt("MAX_CONNECTIONS"),
		PingInterval:    pingInterval,
		PongTimeout:     pongTimeout,
		IdleTimeout:     idleTimeout,
		ShutdownTimeout: shutdownTimeout,
		KafkaWorkers:    v.GetInt("KAFKA_WORKERS"),
		LogLevel:        strings.ToUpper(strings.TrimSpace(v.GetString("LOG_LEVEL"))),
	}

	if cfg.Port <= 0 {
		cfg.Port = 8081
	}
	if cfg.MaxConnections <= 0 {
		cfg.MaxConnections = 10000
	}
	if cfg.KafkaWorkers <= 0 {
		cfg.KafkaWorkers = 4
	}
	if cfg.LogLevel == "" {
		cfg.LogLevel = "INFO"
	}
	if cfg.KafkaTopicPrefix == "" {
		cfg.KafkaTopicPrefix = "estategap."
	}

	var missing []string
	for _, env := range []struct {
		name  string
		value string
	}{
		{name: "JWT_SECRET", value: cfg.JWTSecret},
		{name: "REDIS_ADDR", value: cfg.RedisAddr},
		{name: "AI_CHAT_GRPC_ADDR", value: cfg.AIChatGRPCAddr},
		{name: "KAFKA_BROKERS", value: cfg.KafkaBrokers},
	} {
		if env.value == "" {
			missing = append(missing, env.name)
		}
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf("missing required environment variables: %s", strings.Join(missing, ", "))
	}

	return cfg, nil
}
