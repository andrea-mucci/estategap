package config

import (
	"errors"
	"fmt"
	"strings"

	"github.com/spf13/viper"
)

type Config struct {
	DBPrimaryURL             string
	DBReplicaURL             string
	RedisURL                 string
	JWTSecret                string
	GoogleClientID           string
	GoogleClientSecret       string
	GoogleRedirectURL        string
	AllowedOrigins           []string
	Port                     string
	NATSURL                  string
	LogLevel                 string
	GRPCMLScorerAddr         string
	GRPCChatAddr             string
	GRPCTimeoutSeconds       int
	GRPCCBThreshold          int
	GRPCCBWindowSeconds      int64
	GRPCCBCooldownSeconds    int64
	StripeSecretKey          string
	StripeWebhookSecret      string
	StripeSuccessURL         string
	StripeCancelURL          string
	StripePortalReturnURL    string
	StripePriceBasicMonthly  string
	StripePriceBasicAnnual   string
	StripePriceProMonthly    string
	StripePriceProAnnual     string
	StripePriceGlobalMonthly string
	StripePriceGlobalAnnual  string
	StripePriceAPIMonthly    string
	StripePriceAPIAnnual     string
}

func Load() (*Config, error) {
	v := viper.New()
	v.AutomaticEnv()
	v.SetDefault("PORT", "8080")
	v.SetDefault("LOG_LEVEL", "INFO")
	v.SetDefault("ALLOWED_ORIGINS", "")
	v.SetDefault("GRPC_ML_SCORER_ADDR", "ml-scorer.estategap-intelligence.svc.cluster.local:50051")
	v.SetDefault("GRPC_AI_CHAT_ADDR", "ai-chat-service.estategap-intelligence.svc.cluster.local:50051")
	v.SetDefault("GRPC_TIMEOUT_SECONDS", 5)
	v.SetDefault("GRPC_CB_THRESHOLD", 5)
	v.SetDefault("GRPC_CB_WINDOW_SECONDS", 30)
	v.SetDefault("GRPC_CB_COOLDOWN_SECONDS", 30)

	cfg := &Config{
		DBPrimaryURL:             strings.TrimSpace(v.GetString("DB_PRIMARY_URL")),
		DBReplicaURL:             strings.TrimSpace(v.GetString("DB_REPLICA_URL")),
		RedisURL:                 strings.TrimSpace(v.GetString("REDIS_URL")),
		JWTSecret:                v.GetString("JWT_SECRET"),
		GoogleClientID:           strings.TrimSpace(v.GetString("GOOGLE_CLIENT_ID")),
		GoogleClientSecret:       strings.TrimSpace(v.GetString("GOOGLE_CLIENT_SECRET")),
		GoogleRedirectURL:        strings.TrimSpace(v.GetString("GOOGLE_REDIRECT_URL")),
		AllowedOrigins:           splitCSV(v.GetString("ALLOWED_ORIGINS")),
		Port:                     strings.TrimSpace(v.GetString("PORT")),
		NATSURL:                  strings.TrimSpace(v.GetString("NATS_URL")),
		LogLevel:                 strings.ToUpper(strings.TrimSpace(v.GetString("LOG_LEVEL"))),
		GRPCMLScorerAddr:         strings.TrimSpace(v.GetString("GRPC_ML_SCORER_ADDR")),
		GRPCChatAddr:             strings.TrimSpace(v.GetString("GRPC_AI_CHAT_ADDR")),
		GRPCTimeoutSeconds:       positiveInt(v.GetInt("GRPC_TIMEOUT_SECONDS"), 5),
		GRPCCBThreshold:          positiveInt(v.GetInt("GRPC_CB_THRESHOLD"), 5),
		GRPCCBWindowSeconds:      int64(positiveInt(v.GetInt("GRPC_CB_WINDOW_SECONDS"), 30)),
		GRPCCBCooldownSeconds:    int64(positiveInt(v.GetInt("GRPC_CB_COOLDOWN_SECONDS"), 30)),
		StripeSecretKey:          strings.TrimSpace(v.GetString("STRIPE_SECRET_KEY")),
		StripeWebhookSecret:      strings.TrimSpace(v.GetString("STRIPE_WEBHOOK_SECRET")),
		StripeSuccessURL:         strings.TrimSpace(v.GetString("STRIPE_SUCCESS_URL")),
		StripeCancelURL:          strings.TrimSpace(v.GetString("STRIPE_CANCEL_URL")),
		StripePortalReturnURL:    strings.TrimSpace(v.GetString("STRIPE_PORTAL_RETURN_URL")),
		StripePriceBasicMonthly:  strings.TrimSpace(v.GetString("STRIPE_PRICE_BASIC_MONTHLY")),
		StripePriceBasicAnnual:   strings.TrimSpace(v.GetString("STRIPE_PRICE_BASIC_ANNUAL")),
		StripePriceProMonthly:    strings.TrimSpace(v.GetString("STRIPE_PRICE_PRO_MONTHLY")),
		StripePriceProAnnual:     strings.TrimSpace(v.GetString("STRIPE_PRICE_PRO_ANNUAL")),
		StripePriceGlobalMonthly: strings.TrimSpace(v.GetString("STRIPE_PRICE_GLOBAL_MONTHLY")),
		StripePriceGlobalAnnual:  strings.TrimSpace(v.GetString("STRIPE_PRICE_GLOBAL_ANNUAL")),
		StripePriceAPIMonthly:    strings.TrimSpace(v.GetString("STRIPE_PRICE_API_MONTHLY")),
		StripePriceAPIAnnual:     strings.TrimSpace(v.GetString("STRIPE_PRICE_API_ANNUAL")),
	}

	if cfg.Port == "" {
		cfg.Port = "8080"
	}

	var missing []string
	for _, req := range []struct {
		name  string
		value string
	}{
		{name: "DB_PRIMARY_URL", value: cfg.DBPrimaryURL},
		{name: "DB_REPLICA_URL", value: cfg.DBReplicaURL},
		{name: "REDIS_URL", value: cfg.RedisURL},
		{name: "JWT_SECRET", value: cfg.JWTSecret},
		{name: "GOOGLE_CLIENT_ID", value: cfg.GoogleClientID},
		{name: "GOOGLE_CLIENT_SECRET", value: cfg.GoogleClientSecret},
		{name: "GOOGLE_REDIRECT_URL", value: cfg.GoogleRedirectURL},
		{name: "NATS_URL", value: cfg.NATSURL},
		{name: "STRIPE_SECRET_KEY", value: cfg.StripeSecretKey},
		{name: "STRIPE_WEBHOOK_SECRET", value: cfg.StripeWebhookSecret},
		{name: "STRIPE_SUCCESS_URL", value: cfg.StripeSuccessURL},
		{name: "STRIPE_CANCEL_URL", value: cfg.StripeCancelURL},
		{name: "STRIPE_PORTAL_RETURN_URL", value: cfg.StripePortalReturnURL},
	} {
		if req.value == "" {
			missing = append(missing, req.name)
		}
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf("missing required environment variables: %s", strings.Join(missing, ", "))
	}
	if len(cfg.JWTSecret) < 32 {
		return nil, errors.New("JWT_SECRET must be at least 32 bytes")
	}

	return cfg, nil
}

func splitCSV(input string) []string {
	if strings.TrimSpace(input) == "" {
		return nil
	}
	parts := strings.Split(input, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		if trimmed := strings.TrimSpace(part); trimmed != "" {
			out = append(out, trimmed)
		}
	}
	return out
}

func positiveInt(value, fallback int) int {
	if value <= 0 {
		return fallback
	}
	return value
}
