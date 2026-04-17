package repository

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

type ScrapingPortalStat struct {
	PortalID     string  `json:"portal_id"`
	PortalName   string  `json:"portal_name"`
	Country      string  `json:"country"`
	Status       string  `json:"status"`
	LastScrapeAt *string `json:"last_scrape_at,omitempty"`
	Listings24h  int64   `json:"listings_24h"`
	SuccessRate  float64 `json:"success_rate"`
	Blocks24h    int64   `json:"blocks_24h"`
}

type MLModelVersion struct {
	ID          string  `json:"id"`
	Country     string  `json:"country"`
	Version     string  `json:"version"`
	MAPE        float64 `json:"mape"`
	MAE         float64 `json:"mae"`
	R2          float64 `json:"r2"`
	TrainedAt   string  `json:"trained_at"`
	IsActive    bool    `json:"is_active"`
	TrainStatus string  `json:"train_status"`
}

type AdminUser struct {
	ID               string  `json:"id"`
	Email            string  `json:"email"`
	Name             *string `json:"name,omitempty"`
	Role             string  `json:"role"`
	SubscriptionTier string  `json:"subscription_tier"`
	LastActiveAt     *string `json:"last_active_at,omitempty"`
	CreatedAt        string  `json:"created_at"`
}

type PortalConfig struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Enabled bool   `json:"enabled"`
	Config  any    `json:"config"`
}

type CountryConfig struct {
	Code    string         `json:"code"`
	Name    string         `json:"name"`
	Enabled bool           `json:"enabled"`
	Portals []PortalConfig `json:"portals"`
}

type SystemHealth struct {
	NATS     NATSHealth     `json:"nats"`
	Database DatabaseHealth `json:"database"`
	Redis    RedisHealth    `json:"redis"`
}

type NATSHealth struct {
	Subjects []NATSSubjectStat `json:"subjects"`
}

type NATSSubjectStat struct {
	Subject      string `json:"subject"`
	ConsumerLag  int64  `json:"consumer_lag"`
	MessageCount int64  `json:"message_count"`
}

type DatabaseHealth struct {
	SizeBytes    int64 `json:"size_bytes"`
	ActiveConns  int   `json:"active_connections"`
	MaxConns     int   `json:"max_connections"`
	WaitingConns int   `json:"waiting_connections"`
}

type RedisHealth struct {
	UsedMemoryBytes  int64   `json:"used_memory_bytes"`
	MaxMemoryBytes   int64   `json:"max_memory_bytes"`
	HitRate          float64 `json:"hit_rate"`
	ConnectedClients int     `json:"connected_clients"`
}

type AdminRepo struct {
	primary        *pgxpool.Pool
	replica        *pgxpool.Pool
	redisClient    *redis.Client
	natsMonitorURL string
	httpClient     *http.Client
}

func NewAdminRepo(primary, replica *pgxpool.Pool, redisClient *redis.Client, natsMonitorURL string) *AdminRepo {
	return &AdminRepo{
		primary:        primary,
		replica:        replica,
		redisClient:    redisClient,
		natsMonitorURL: strings.TrimSpace(natsMonitorURL),
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

func (r *AdminRepo) GetScrapingStats(ctx context.Context) ([]ScrapingPortalStat, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT
			p.id,
			p.name,
			p.country_code,
			p.config,
			COALESCE(ls.listings_24h, 0)::bigint AS listings_24h
		FROM portals p
		LEFT JOIN LATERAL (
			SELECT COUNT(*) AS listings_24h
			FROM listings l
			WHERE l.portal_id = p.id
				AND l.created_at >= NOW() - INTERVAL '24 hours'
		) ls ON TRUE
		ORDER BY p.country_code ASC, p.name ASC`)
	if err != nil {
		return nil, err
	}

	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (ScrapingPortalStat, error) {
		var (
			item      ScrapingPortalStat
			rawID     pgtype.UUID
			configRaw json.RawMessage
		)

		if err := row.Scan(&rawID, &item.PortalName, &item.Country, &configRaw, &item.Listings24h); err != nil {
			return ScrapingPortalStat{}, err
		}

		item.PortalID = uuid.UUID(rawID.Bytes).String()
		item.Country = strings.ToUpper(item.Country)
		item.Status = "active"
		if len(configRaw) > 0 {
			var payload map[string]any
			if err := json.Unmarshal(configRaw, &payload); err == nil {
				if value, ok := payload["status"].(string); ok && strings.TrimSpace(value) != "" {
					item.Status = strings.ToLower(strings.TrimSpace(value))
				}
				if value, ok := payload["last_scrape_at"].(string); ok && strings.TrimSpace(value) != "" {
					timestamp := strings.TrimSpace(value)
					item.LastScrapeAt = &timestamp
				}
				item.SuccessRate = floatValue(payload["success_rate"])
				item.Blocks24h = int64(floatValue(payload["blocks_24h"]))
			}
		}
		if item.SuccessRate == 0 {
			item.SuccessRate = 1
		}

		return item, nil
	})
}

func (r *AdminRepo) GetMLModels(ctx context.Context) ([]MLModelVersion, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT
			id,
			country_code,
			version_tag,
			COALESCE(NULLIF(metrics->>'mape', ''), '0')::double precision AS mape,
			COALESCE(NULLIF(metrics->>'mae', ''), '0')::double precision AS mae,
			COALESCE(NULLIF(metrics->>'r2', ''), '0')::double precision AS r2,
			trained_at,
			status
		FROM model_versions
		ORDER BY trained_at DESC`)
	if err != nil {
		return nil, err
	}

	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (MLModelVersion, error) {
		var (
			item      MLModelVersion
			rawID     pgtype.UUID
			trainedAt time.Time
			status    string
		)

		if err := row.Scan(&rawID, &item.Country, &item.Version, &item.MAPE, &item.MAE, &item.R2, &trainedAt, &status); err != nil {
			return MLModelVersion{}, err
		}

		item.ID = uuid.UUID(rawID.Bytes).String()
		item.Country = strings.ToUpper(item.Country)
		item.TrainedAt = trainedAt.UTC().Format(time.RFC3339)
		item.IsActive = strings.EqualFold(status, "active")
		switch strings.ToLower(strings.TrimSpace(status)) {
		case "training", "failed":
			item.TrainStatus = strings.ToLower(strings.TrimSpace(status))
		default:
			item.TrainStatus = "idle"
		}

		return item, nil
	})
}

func (r *AdminRepo) IsRetrainingInProgress(ctx context.Context, country string) (bool, error) {
	count, err := r.redisClient.Exists(ctx, "ml:retrain:in_progress:"+strings.ToUpper(strings.TrimSpace(country))).Result()
	return count > 0, err
}

func (r *AdminRepo) ListUsers(ctx context.Context, page, limit int, q, tier string) ([]AdminUser, int, error) {
	if page < 1 {
		page = 1
	}
	limit = clampLimit(limit, 50)
	offset := (page - 1) * limit

	args := []any{}
	conditions := []string{"deleted_at IS NULL"}
	if trimmed := strings.TrimSpace(q); trimmed != "" {
		args = append(args, "%"+trimmed+"%")
		conditions = append(conditions, fmt.Sprintf("(email ILIKE $%d OR COALESCE(display_name, '') ILIKE $%d)", len(args), len(args)))
	}
	if trimmed := strings.TrimSpace(tier); trimmed != "" {
		args = append(args, trimmed)
		conditions = append(conditions, fmt.Sprintf("subscription_tier = $%d", len(args)))
	}

	whereClause := "WHERE " + strings.Join(conditions, " AND ")

	countQuery := `SELECT COUNT(*) FROM users ` + whereClause
	var total int
	if err := r.replica.QueryRow(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	args = append(args, limit, offset)
	rows, err := r.replica.Query(ctx, `
		SELECT
			id,
			email,
			display_name,
			subscription_tier,
			last_login_at,
			created_at
		FROM users
		`+whereClause+`
		ORDER BY created_at DESC
		LIMIT $`+strconv.Itoa(len(args)-1)+` OFFSET $`+strconv.Itoa(len(args)),
		args...,
	)
	if err != nil {
		return nil, 0, err
	}

	users, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (AdminUser, error) {
		var (
			item         AdminUser
			rawID        pgtype.UUID
			name         sql.NullString
			lastActiveAt sql.NullTime
			createdAt    time.Time
		)
		if err := row.Scan(&rawID, &item.Email, &name, &item.SubscriptionTier, &lastActiveAt, &createdAt); err != nil {
			return AdminUser{}, err
		}
		item.ID = uuid.UUID(rawID.Bytes).String()
		item.Role = roleFromEmail(item.Email)
		item.CreatedAt = createdAt.UTC().Format(time.RFC3339)
		if name.Valid {
			item.Name = &name.String
		}
		if lastActiveAt.Valid {
			value := lastActiveAt.Time.UTC().Format(time.RFC3339)
			item.LastActiveAt = &value
		}
		return item, nil
	})
	if err != nil {
		return nil, 0, err
	}

	return users, total, nil
}

func (r *AdminRepo) GetCountries(ctx context.Context) ([]CountryConfig, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT
			c.code,
			c.name,
			c.active,
			p.id,
			p.name,
			p.enabled,
			p.config
		FROM countries c
		LEFT JOIN portals p ON p.country_code = c.code
		ORDER BY c.name ASC, p.name ASC`)
	if err != nil {
		return nil, err
	}

	type countryRow struct {
		Code          string
		Name          string
		Enabled       bool
		PortalID      pgtype.UUID
		PortalName    sql.NullString
		PortalEnabled sql.NullBool
		PortalConfig  json.RawMessage
	}

	flatRows, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (countryRow, error) {
		var item countryRow
		err := row.Scan(&item.Code, &item.Name, &item.Enabled, &item.PortalID, &item.PortalName, &item.PortalEnabled, &item.PortalConfig)
		return item, err
	})
	if err != nil {
		return nil, err
	}

	grouped := make(map[string]*CountryConfig, len(flatRows))
	order := make([]string, 0, len(flatRows))
	for _, row := range flatRows {
		country, ok := grouped[row.Code]
		if !ok {
			country = &CountryConfig{
				Code:    row.Code,
				Name:    row.Name,
				Enabled: row.Enabled,
				Portals: []PortalConfig{},
			}
			grouped[row.Code] = country
			order = append(order, row.Code)
		}

		if row.PortalID.Valid {
			country.Portals = append(country.Portals, PortalConfig{
				ID:      uuid.UUID(row.PortalID.Bytes).String(),
				Name:    row.PortalName.String,
				Enabled: row.PortalEnabled.Bool,
				Config:  decodeJSONValue(row.PortalConfig),
			})
		}
	}

	result := make([]CountryConfig, 0, len(order))
	for _, code := range order {
		result = append(result, *grouped[code])
	}

	return result, nil
}

func (r *AdminRepo) UpdateCountry(ctx context.Context, code string, enabled bool, portals []PortalConfig) (CountryConfig, error) {
	tx, err := r.primary.Begin(ctx)
	if err != nil {
		return CountryConfig{}, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	tag, err := tx.Exec(ctx, `
		UPDATE countries
		SET active = $2,
			updated_at = NOW()
		WHERE code = $1`,
		strings.ToUpper(strings.TrimSpace(code)),
		enabled,
	)
	if err != nil {
		return CountryConfig{}, err
	}
	if tag.RowsAffected() == 0 {
		return CountryConfig{}, ErrNotFound
	}

	for _, portal := range portals {
		configValue, err := json.Marshal(portal.Config)
		if err != nil {
			return CountryConfig{}, err
		}
		if _, err := tx.Exec(ctx, `
			UPDATE portals
			SET enabled = $2,
				config = COALESCE($3::jsonb, config),
				updated_at = NOW()
			WHERE id = $1
				AND country_code = $4`,
			portal.ID,
			portal.Enabled,
			nullableJSON(configValue),
			strings.ToUpper(strings.TrimSpace(code)),
		); err != nil {
			return CountryConfig{}, err
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return CountryConfig{}, err
	}

	countries, err := r.GetCountries(ctx)
	if err != nil {
		return CountryConfig{}, err
	}
	for _, country := range countries {
		if strings.EqualFold(country.Code, code) {
			return country, nil
		}
	}

	return CountryConfig{}, ErrNotFound
}

func (r *AdminRepo) GetSystemHealth(ctx context.Context) (SystemHealth, error) {
	health := SystemHealth{}

	if err := r.replica.QueryRow(ctx, `
		WITH db_stats AS (
			SELECT
				COUNT(*) FILTER (WHERE state = 'active')::int AS active_connections,
				COUNT(*) FILTER (WHERE wait_event IS NOT NULL)::int AS waiting_connections
			FROM pg_stat_activity
			WHERE datname = current_database()
		)
		SELECT
			pg_database_size(current_database())::bigint AS size_bytes,
			COALESCE((SELECT active_connections FROM db_stats), 0),
			COALESCE((SELECT setting::int FROM pg_settings WHERE name = 'max_connections'), 0),
			COALESCE((SELECT waiting_connections FROM db_stats), 0)`,
	).Scan(
		&health.Database.SizeBytes,
		&health.Database.ActiveConns,
		&health.Database.MaxConns,
		&health.Database.WaitingConns,
	); err != nil {
		return SystemHealth{}, err
	}

	memoryInfo, err := r.redisClient.Info(ctx, "memory").Result()
	if err != nil {
		return SystemHealth{}, err
	}
	statsInfo, err := r.redisClient.Info(ctx, "stats").Result()
	if err != nil {
		return SystemHealth{}, err
	}
	clientsInfo, err := r.redisClient.Info(ctx, "clients").Result()
	if err != nil {
		return SystemHealth{}, err
	}

	health.Redis.UsedMemoryBytes = parseRedisInfoInt(memoryInfo, "used_memory")
	health.Redis.MaxMemoryBytes = parseRedisInfoInt(memoryInfo, "maxmemory")
	health.Redis.ConnectedClients = int(parseRedisInfoInt(clientsInfo, "connected_clients"))
	hits := parseRedisInfoInt(statsInfo, "keyspace_hits")
	misses := parseRedisInfoInt(statsInfo, "keyspace_misses")
	if total := hits + misses; total > 0 {
		health.Redis.HitRate = float64(hits) / float64(total)
	}

	subjects, err := r.fetchNATSSubjects(ctx)
	if err == nil {
		health.NATS.Subjects = subjects
	}

	return health, nil
}

func (r *AdminRepo) fetchNATSSubjects(ctx context.Context) ([]NATSSubjectStat, error) {
	if r.natsMonitorURL == "" {
		return nil, fmt.Errorf("nats monitor url not configured")
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, r.natsMonitorURL, nil)
	if err != nil {
		return nil, err
	}

	resp, err := r.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var payload map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}

	subjects := []NATSSubjectStat{}
	if streams, ok := payload["streams"].([]any); ok {
		for _, stream := range streams {
			item, ok := stream.(map[string]any)
			if !ok {
				continue
			}
			state, _ := item["state"].(map[string]any)
			subjects = append(subjects, NATSSubjectStat{
				Subject:      stringValue(item["name"]),
				MessageCount: int64(floatValue(state["messages"])),
				ConsumerLag:  int64(floatValue(item["consumer_count"])),
			})
		}
	}
	if len(subjects) > 0 {
		return subjects, nil
	}

	if accounts, ok := payload["account_details"].([]any); ok {
		for _, account := range accounts {
			accountItem, ok := account.(map[string]any)
			if !ok {
				continue
			}
			if streams, ok := accountItem["stream_detail"].([]any); ok {
				for _, stream := range streams {
					streamItem, ok := stream.(map[string]any)
					if !ok {
						continue
					}
					state, _ := streamItem["state"].(map[string]any)
					lag := int64(0)
					if consumers, ok := streamItem["consumer_detail"].([]any); ok {
						for _, consumer := range consumers {
							consumerItem, ok := consumer.(map[string]any)
							if !ok {
								continue
							}
							lag += int64(floatValue(consumerItem["num_pending"]))
						}
					}
					subjects = append(subjects, NATSSubjectStat{
						Subject:      stringValue(streamItem["name"]),
						MessageCount: int64(floatValue(state["messages"])),
						ConsumerLag:  lag,
					})
				}
			}
		}
	}

	return subjects, nil
}

func parseRedisInfoInt(payload, key string) int64 {
	scanner := bufio.NewScanner(strings.NewReader(payload))
	prefix := key + ":"
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, prefix) {
			continue
		}
		value, err := strconv.ParseInt(strings.TrimSpace(strings.TrimPrefix(line, prefix)), 10, 64)
		if err == nil {
			return value
		}
	}
	return 0
}

func decodeJSONValue(raw json.RawMessage) any {
	if len(raw) == 0 {
		return map[string]any{}
	}

	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		return map[string]any{}
	}

	return value
}

func nullableJSON(raw []byte) any {
	if len(raw) == 0 || string(raw) == "null" {
		return nil
	}

	return raw
}

func stringValue(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	default:
		return ""
	}
}

func floatValue(value any) float64 {
	switch typed := value.(type) {
	case float64:
		return typed
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case json.Number:
		parsed, _ := typed.Float64()
		return parsed
	case string:
		parsed, _ := strconv.ParseFloat(strings.TrimSpace(typed), 64)
		return parsed
	default:
		return 0
	}
}

func roleFromEmail(email string) string {
	if strings.HasSuffix(strings.ToLower(strings.TrimSpace(email)), "@estategap.com") {
		return "admin"
	}

	return "user"
}
