package config

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/spf13/viper"
)

type Config struct {
	DatabaseURL          string
	RedisURL             string
	NATSURL              string
	HTTPPort             string
	LogLevel             string
	PortalReloadInterval time.Duration
	JobTTL               time.Duration
}

func Load() (*Config, error) {
	v := viper.New()
	v.AutomaticEnv()
	v.SetDefault("HTTP_PORT", "8082")
	v.SetDefault("LOG_LEVEL", "INFO")
	v.SetDefault("PORTAL_RELOAD_INTERVAL", "5m")
	v.SetDefault("JOB_TTL", "86400")

	reloadInterval, err := time.ParseDuration(strings.TrimSpace(v.GetString("PORTAL_RELOAD_INTERVAL")))
	if err != nil {
		return nil, fmt.Errorf("parse PORTAL_RELOAD_INTERVAL: %w", err)
	}

	jobTTL, err := parseSecondsOrDuration(v.GetString("JOB_TTL"), 24*time.Hour)
	if err != nil {
		return nil, fmt.Errorf("parse JOB_TTL: %w", err)
	}

	cfg := &Config{
		DatabaseURL:          strings.TrimSpace(v.GetString("DATABASE_URL")),
		RedisURL:             strings.TrimSpace(v.GetString("REDIS_URL")),
		NATSURL:              strings.TrimSpace(v.GetString("NATS_URL")),
		HTTPPort:             strings.TrimSpace(v.GetString("HTTP_PORT")),
		LogLevel:             strings.ToUpper(strings.TrimSpace(v.GetString("LOG_LEVEL"))),
		PortalReloadInterval: reloadInterval,
		JobTTL:               jobTTL,
	}

	if cfg.HTTPPort == "" {
		cfg.HTTPPort = "8082"
	}
	if cfg.LogLevel == "" {
		cfg.LogLevel = "INFO"
	}

	var missing []string
	for _, env := range []struct {
		name  string
		value string
	}{
		{name: "DATABASE_URL", value: cfg.DatabaseURL},
		{name: "REDIS_URL", value: cfg.RedisURL},
		{name: "NATS_URL", value: cfg.NATSURL},
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

func parseSecondsOrDuration(raw string, fallback time.Duration) (time.Duration, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return fallback, nil
	}
	if seconds, err := strconv.Atoi(raw); err == nil {
		if seconds <= 0 {
			return fallback, nil
		}
		return time.Duration(seconds) * time.Second, nil
	}
	duration, err := time.ParseDuration(raw)
	if err != nil {
		return 0, err
	}
	if duration <= 0 {
		return fallback, nil
	}
	return duration, nil
}
