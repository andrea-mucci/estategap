package config

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/spf13/viper"
)

type CountryConfig struct {
	Country   string
	Provider  string
	Endpoints []string
	Username  string
	Password  string
}

type Config struct {
	RedisURL        string
	GRPCPort        string
	MetricsPort     string
	LogLevel        string
	BlacklistTTL    time.Duration
	StickyTTL       time.Duration
	HealthThreshold float64
	Countries       []string
	CountryConfigs  map[string]CountryConfig
}

func Load() (*Config, error) {
	v := viper.New()
	v.AutomaticEnv()
	v.SetDefault("GRPC_PORT", "50052")
	v.SetDefault("METRICS_PORT", "9090")
	v.SetDefault("LOG_LEVEL", "INFO")
	v.SetDefault("BLACKLIST_TTL", "1800")
	v.SetDefault("STICKY_TTL", "600")
	v.SetDefault("HEALTH_THRESHOLD", 0.5)

	blacklistTTL, err := parseSecondsOrDuration(v.GetString("BLACKLIST_TTL"), 30*time.Minute)
	if err != nil {
		return nil, fmt.Errorf("parse BLACKLIST_TTL: %w", err)
	}
	stickyTTL, err := parseSecondsOrDuration(v.GetString("STICKY_TTL"), 10*time.Minute)
	if err != nil {
		return nil, fmt.Errorf("parse STICKY_TTL: %w", err)
	}

	countries := splitCSVUpper(v.GetString("PROXY_COUNTRIES"))
	countryConfigs := make(map[string]CountryConfig, len(countries))
	var missing []string
	for _, country := range countries {
		provider := strings.ToLower(strings.TrimSpace(v.GetString("PROXY_" + country + "_PROVIDER")))
		endpoints := splitCSV(v.GetString("PROXY_" + country + "_ENDPOINT"))
		username := strings.TrimSpace(v.GetString("PROXY_" + country + "_USERNAME"))
		password := strings.TrimSpace(v.GetString("PROXY_" + country + "_PASSWORD"))

		if provider == "" {
			missing = append(missing, "PROXY_"+country+"_PROVIDER")
		}
		if len(endpoints) == 0 {
			missing = append(missing, "PROXY_"+country+"_ENDPOINT")
		}
		if username == "" {
			missing = append(missing, "PROXY_"+country+"_USERNAME")
		}
		if password == "" {
			missing = append(missing, "PROXY_"+country+"_PASSWORD")
		}

		countryConfigs[country] = CountryConfig{
			Country:   country,
			Provider:  provider,
			Endpoints: endpoints,
			Username:  username,
			Password:  password,
		}
	}

	cfg := &Config{
		RedisURL:        strings.TrimSpace(v.GetString("REDIS_URL")),
		GRPCPort:        strings.TrimSpace(v.GetString("GRPC_PORT")),
		MetricsPort:     strings.TrimSpace(v.GetString("METRICS_PORT")),
		LogLevel:        strings.ToUpper(strings.TrimSpace(v.GetString("LOG_LEVEL"))),
		BlacklistTTL:    blacklistTTL,
		StickyTTL:       stickyTTL,
		HealthThreshold: v.GetFloat64("HEALTH_THRESHOLD"),
		Countries:       countries,
		CountryConfigs:  countryConfigs,
	}

	if cfg.GRPCPort == "" {
		cfg.GRPCPort = "50052"
	}
	if cfg.MetricsPort == "" {
		cfg.MetricsPort = "9090"
	}
	if cfg.LogLevel == "" {
		cfg.LogLevel = "INFO"
	}
	if cfg.HealthThreshold <= 0 || cfg.HealthThreshold > 1 {
		cfg.HealthThreshold = 0.5
	}
	if cfg.RedisURL == "" {
		missing = append(missing, "REDIS_URL")
	}
	if len(cfg.Countries) == 0 {
		missing = append(missing, "PROXY_COUNTRIES")
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf("missing required environment variables: %s", strings.Join(missing, ", "))
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

func splitCSVUpper(input string) []string {
	items := splitCSV(input)
	for i, item := range items {
		items[i] = strings.ToUpper(item)
	}
	return items
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
