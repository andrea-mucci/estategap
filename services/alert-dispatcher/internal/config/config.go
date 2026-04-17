package config

import (
	"fmt"
	"runtime"
	"strings"

	"github.com/spf13/viper"
)

type Config struct {
	DatabaseURL             string
	DatabaseReplicaURL      string
	RedisURL                string
	NATSURL                 string
	NATSConsumerName        string
	AWSRegion               string
	AWSSesFromAddress       string
	AWSSesFromName          string
	TelegramBotToken        string
	TwilioAccountSID        string
	TwilioAuthToken         string
	TwilioWhatsAppFrom      string
	TwilioWhatsAppTemplate  string
	FirebaseCredentialsJSON string
	BaseURL                 string
	HealthPort              int
	WorkerPoolSize          int
	BatchSize               int
	LogLevel                string
}

func Load() (*Config, error) {
	v := viper.New()
	v.AutomaticEnv()

	v.SetDefault("DATABASE_REPLICA_URL", "")
	v.SetDefault("REDIS_URL", "redis://localhost:6379")
	v.SetDefault("NATS_URL", "nats://localhost:4222")
	v.SetDefault("NATS_CONSUMER_NAME", "alert-dispatcher")
	v.SetDefault("AWS_REGION", "eu-west-1")
	v.SetDefault("AWS_SES_FROM_NAME", "EstateGap Alerts")
	v.SetDefault("BASE_URL", "https://api.estategap.com")
	v.SetDefault("HEALTH_PORT", 8081)
	v.SetDefault("WORKER_POOL_SIZE", 0)
	v.SetDefault("BATCH_SIZE", 50)
	v.SetDefault("LOG_LEVEL", "INFO")

	cfg := &Config{
		DatabaseURL:             strings.TrimSpace(v.GetString("DATABASE_URL")),
		DatabaseReplicaURL:      strings.TrimSpace(v.GetString("DATABASE_REPLICA_URL")),
		RedisURL:                strings.TrimSpace(v.GetString("REDIS_URL")),
		NATSURL:                 strings.TrimSpace(v.GetString("NATS_URL")),
		NATSConsumerName:        strings.TrimSpace(v.GetString("NATS_CONSUMER_NAME")),
		AWSRegion:               strings.TrimSpace(v.GetString("AWS_REGION")),
		AWSSesFromAddress:       strings.TrimSpace(v.GetString("AWS_SES_FROM_ADDRESS")),
		AWSSesFromName:          strings.TrimSpace(v.GetString("AWS_SES_FROM_NAME")),
		TelegramBotToken:        strings.TrimSpace(v.GetString("TELEGRAM_BOT_TOKEN")),
		TwilioAccountSID:        strings.TrimSpace(v.GetString("TWILIO_ACCOUNT_SID")),
		TwilioAuthToken:         strings.TrimSpace(v.GetString("TWILIO_AUTH_TOKEN")),
		TwilioWhatsAppFrom:      strings.TrimSpace(v.GetString("TWILIO_WHATSAPP_FROM")),
		TwilioWhatsAppTemplate:  strings.TrimSpace(v.GetString("TWILIO_WHATSAPP_TEMPLATE_SID")),
		FirebaseCredentialsJSON: strings.TrimSpace(v.GetString("FIREBASE_CREDENTIALS_JSON")),
		BaseURL:                 strings.TrimRight(strings.TrimSpace(v.GetString("BASE_URL")), "/"),
		HealthPort:              v.GetInt("HEALTH_PORT"),
		WorkerPoolSize:          v.GetInt("WORKER_POOL_SIZE"),
		BatchSize:               v.GetInt("BATCH_SIZE"),
		LogLevel:                strings.ToUpper(strings.TrimSpace(v.GetString("LOG_LEVEL"))),
	}

	if cfg.DatabaseURL == "" {
		return nil, fmt.Errorf("DATABASE_URL is required")
	}
	if cfg.NATSURL == "" {
		return nil, fmt.Errorf("NATS_URL is required")
	}
	if cfg.DatabaseReplicaURL == "" {
		cfg.DatabaseReplicaURL = cfg.DatabaseURL
	}
	if cfg.HealthPort <= 0 {
		cfg.HealthPort = 8081
	}
	if cfg.WorkerPoolSize <= 0 {
		cfg.WorkerPoolSize = runtime.NumCPU() * 4
		if cfg.WorkerPoolSize <= 0 {
			cfg.WorkerPoolSize = 4
		}
	}
	if cfg.BatchSize <= 0 {
		cfg.BatchSize = 50
	}
	if cfg.NATSConsumerName == "" {
		cfg.NATSConsumerName = "alert-dispatcher"
	}
	if cfg.LogLevel == "" {
		cfg.LogLevel = "INFO"
	}

	return cfg, nil
}
