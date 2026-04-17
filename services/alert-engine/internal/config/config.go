package config

import (
	"fmt"
	"strings"
	"time"

	"github.com/spf13/viper"
)

type Config struct {
	DatabaseURL              string
	DatabaseReplicaURL       string
	RedisURL                 string
	KafkaBrokers             string
	KafkaTopicPrefix         string
	KafkaSASLUsername        string
	KafkaSASLPassword        string
	KafkaTLSEnabled          bool
	RuleCacheRefreshInterval time.Duration
	WorkerPoolSize           int
	BatchSize                int
	HealthPort               int
	LogLevel                 string
}

func Load() (*Config, error) {
	v := viper.New()
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	v.SetDefault("REDIS_URL", "redis://localhost:6379")
	v.SetDefault("KAFKA_BROKERS", "localhost:9092")
	v.SetDefault("KAFKA_TOPIC_PREFIX", "estategap.")
	v.SetDefault("RULE_CACHE_REFRESH_INTERVAL", "60s")
	v.SetDefault("WORKER_POOL_SIZE", 0)
	v.SetDefault("BATCH_SIZE", 100)
	v.SetDefault("HEALTH_PORT", 8080)
	v.SetDefault("LOG_LEVEL", "info")

	cfg := &Config{
		DatabaseURL:        strings.TrimSpace(v.GetString("DATABASE_URL")),
		DatabaseReplicaURL: strings.TrimSpace(v.GetString("DATABASE_REPLICA_URL")),
		RedisURL:           strings.TrimSpace(v.GetString("REDIS_URL")),
		KafkaBrokers:       strings.TrimSpace(v.GetString("KAFKA_BROKERS")),
		KafkaTopicPrefix:   strings.TrimSpace(v.GetString("KAFKA_TOPIC_PREFIX")),
		KafkaSASLUsername:  strings.TrimSpace(v.GetString("KAFKA_SASL_USERNAME")),
		KafkaSASLPassword:  v.GetString("KAFKA_SASL_PASSWORD"),
		KafkaTLSEnabled:    v.GetBool("KAFKA_TLS_ENABLED"),
		WorkerPoolSize:     v.GetInt("WORKER_POOL_SIZE"),
		BatchSize:          v.GetInt("BATCH_SIZE"),
		HealthPort:         v.GetInt("HEALTH_PORT"),
		LogLevel:           strings.TrimSpace(v.GetString("LOG_LEVEL")),
	}

	if cfg.DatabaseURL == "" {
		return nil, fmt.Errorf("DATABASE_URL is required")
	}
	if cfg.KafkaBrokers == "" {
		return nil, fmt.Errorf("KAFKA_BROKERS is required")
	}
	if cfg.DatabaseReplicaURL == "" {
		cfg.DatabaseReplicaURL = cfg.DatabaseURL
	}
	if cfg.KafkaTopicPrefix == "" {
		cfg.KafkaTopicPrefix = "estategap."
	}

	interval, err := time.ParseDuration(v.GetString("RULE_CACHE_REFRESH_INTERVAL"))
	if err != nil {
		return nil, fmt.Errorf("parse RULE_CACHE_REFRESH_INTERVAL: %w", err)
	}
	cfg.RuleCacheRefreshInterval = interval

	if cfg.BatchSize <= 0 {
		cfg.BatchSize = 100
	}
	if cfg.HealthPort <= 0 {
		cfg.HealthPort = 8080
	}
	if cfg.LogLevel == "" {
		cfg.LogLevel = "info"
	}

	return cfg, nil
}
