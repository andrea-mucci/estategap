package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type AlertRule struct {
	ID        uuid.UUID       `json:"id"`
	UserID    uuid.UUID       `json:"user_id"`
	Name      string          `json:"name"`
	ZoneIDs   []string        `json:"zone_ids"`
	Category  string          `json:"category"`
	Filter    json.RawMessage `json:"filter"`
	Channels  json.RawMessage `json:"channels"`
	IsActive  bool            `json:"is_active"`
	CreatedAt time.Time       `json:"created_at"`
	UpdatedAt time.Time       `json:"updated_at"`
}

type AlertRuleInput struct {
	UserID   uuid.UUID
	Name     string
	ZoneIDs  []string
	Category string
	Filter   json.RawMessage
	Channels json.RawMessage
	IsActive bool
}

type UpdateRuleInput struct {
	Name     *string
	ZoneIDs  *[]string
	Filter   *json.RawMessage
	Channels *json.RawMessage
	IsActive *bool
}

type AlertHistoryEntry struct {
	ID             uuid.UUID  `json:"id"`
	RuleID         uuid.UUID  `json:"rule_id"`
	RuleName       string     `json:"rule_name"`
	ListingID      uuid.UUID  `json:"listing_id"`
	TriggeredAt    time.Time  `json:"triggered_at"`
	Channel        string     `json:"channel"`
	DeliveryStatus string     `json:"delivery_status"`
	DeliveredAt    *time.Time `json:"delivered_at"`
	ErrorDetail    *string    `json:"error_detail"`
}

type HistoryFilter struct {
	RuleID         *uuid.UUID
	DeliveryStatus *string
	Since          *time.Time
}

type AlertRulesRepo struct {
	primary *pgxpool.Pool
	replica *pgxpool.Pool
}

func NewAlertRulesRepo(primary, replica *pgxpool.Pool) *AlertRulesRepo {
	return &AlertRulesRepo{
		primary: primary,
		replica: replica,
	}
}

func (r *AlertRulesRepo) CountActiveRules(ctx context.Context, userID uuid.UUID) (int, error) {
	var count int
	if err := r.primary.QueryRow(ctx, `
		SELECT COUNT(*)
		FROM alert_rules
		WHERE user_id = $1 AND is_active = TRUE`,
		pgUUID(userID),
	).Scan(&count); err != nil {
		return 0, err
	}
	return count, nil
}

func (r *AlertRulesRepo) CreateRule(ctx context.Context, input AlertRuleInput) (*AlertRule, error) {
	rows, err := r.primary.Query(ctx, `
		INSERT INTO alert_rules (user_id, name, zone_ids, category, filter, channels, is_active)
		VALUES ($1, $2, $3::uuid[], $4, $5::jsonb, $6::jsonb, $7)
		RETURNING id, user_id, name, to_json(zone_ids), category, filter, channels, is_active, created_at, updated_at`,
		pgUUID(input.UserID),
		input.Name,
		input.ZoneIDs,
		input.Category,
		jsonObjectOrDefault(input.Filter),
		jsonArrayOrDefault(input.Channels),
		input.IsActive,
	)
	if err != nil {
		return nil, err
	}

	rule, err := pgx.CollectOneRow(rows, scanAlertRule)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &rule, err
}

func (r *AlertRulesRepo) ListRules(ctx context.Context, userID uuid.UUID, page, pageSize int, isActive *bool) ([]AlertRule, int, error) {
	page, pageSize = normalizePage(page, pageSize)
	args := []any{pgUUID(userID)}
	query := `
		SELECT
			id,
			user_id,
			name,
			to_json(zone_ids),
			category,
			filter,
			channels,
			is_active,
			created_at,
			updated_at,
			COUNT(*) OVER()
		FROM alert_rules
		WHERE user_id = $1`
	if isActive != nil {
		args = append(args, *isActive)
		query += fmt.Sprintf(" AND is_active = $%d", len(args))
	}

	args = append(args, pageSize, (page-1)*pageSize)
	query += fmt.Sprintf(`
		ORDER BY created_at DESC, id DESC
		LIMIT $%d OFFSET $%d`, len(args)-1, len(args))

	rows, err := r.replica.Query(ctx, query, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	return collectAlertRules(rows)
}

func (r *AlertRulesRepo) GetRule(ctx context.Context, id, userID uuid.UUID) (*AlertRule, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT id, user_id, name, to_json(zone_ids), category, filter, channels, is_active, created_at, updated_at
		FROM alert_rules
		WHERE id = $1 AND user_id = $2
		LIMIT 1`,
		pgUUID(id),
		pgUUID(userID),
	)
	if err != nil {
		return nil, err
	}

	rule, err := pgx.CollectOneRow(rows, scanAlertRule)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &rule, err
}

func (r *AlertRulesRepo) UpdateRule(ctx context.Context, id, userID uuid.UUID, input UpdateRuleInput) (*AlertRule, error) {
	setClauses := make([]string, 0, 5)
	args := []any{pgUUID(id), pgUUID(userID)}

	if input.Name != nil {
		args = append(args, *input.Name)
		setClauses = append(setClauses, fmt.Sprintf("name = $%d", len(args)))
	}
	if input.ZoneIDs != nil {
		args = append(args, *input.ZoneIDs)
		setClauses = append(setClauses, fmt.Sprintf("zone_ids = $%d::uuid[]", len(args)))
	}
	if input.Filter != nil {
		args = append(args, jsonObjectOrDefault(*input.Filter))
		setClauses = append(setClauses, fmt.Sprintf("filter = $%d::jsonb", len(args)))
	}
	if input.Channels != nil {
		args = append(args, jsonArrayOrDefault(*input.Channels))
		setClauses = append(setClauses, fmt.Sprintf("channels = $%d::jsonb", len(args)))
	}
	if input.IsActive != nil {
		args = append(args, *input.IsActive)
		setClauses = append(setClauses, fmt.Sprintf("is_active = $%d", len(args)))
	}

	if len(setClauses) == 0 {
		return r.GetRule(ctx, id, userID)
	}

	setClauses = append(setClauses, "updated_at = NOW()")
	query := `
		UPDATE alert_rules
		SET ` + strings.Join(setClauses, ", ") + `
		WHERE id = $1 AND user_id = $2
		RETURNING id, user_id, name, to_json(zone_ids), category, filter, channels, is_active, created_at, updated_at`
	rows, err := r.primary.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}

	rule, err := pgx.CollectOneRow(rows, scanAlertRule)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &rule, err
}

func (r *AlertRulesRepo) DeleteRule(ctx context.Context, id, userID uuid.UUID) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE alert_rules
		SET is_active = FALSE, updated_at = NOW()
		WHERE id = $1 AND user_id = $2`,
		pgUUID(id),
		pgUUID(userID),
	)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *AlertRulesRepo) ValidateZoneIDs(ctx context.Context, zoneIDs []uuid.UUID) ([]uuid.UUID, error) {
	if len(zoneIDs) == 0 {
		return nil, nil
	}

	values := make([]string, 0, len(zoneIDs))
	expected := make(map[uuid.UUID]struct{}, len(zoneIDs))
	for _, zoneID := range zoneIDs {
		values = append(values, zoneID.String())
		expected[zoneID] = struct{}{}
	}

	rows, err := r.replica.Query(ctx, `
		SELECT id
		FROM zones
		WHERE id = ANY($1::uuid[])`,
		values,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var id uuid.UUID
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		delete(expected, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	invalid := make([]uuid.UUID, 0, len(expected))
	for _, zoneID := range zoneIDs {
		if _, ok := expected[zoneID]; ok {
			invalid = append(invalid, zoneID)
		}
	}
	return invalid, nil
}

func (r *AlertRulesRepo) ListHistory(ctx context.Context, dbUserID uuid.UUID, filter HistoryFilter, page, pageSize int) ([]AlertHistoryEntry, int, error) {
	page, pageSize = normalizePage(page, pageSize)
	args := []any{pgUUID(dbUserID)}
	query := `
		SELECT
			h.id,
			h.rule_id,
			r.name,
			h.listing_id,
			h.triggered_at,
			h.channel,
			h.delivery_status,
			h.delivered_at,
			h.error_detail,
			COUNT(*) OVER()
		FROM alert_history h
		JOIN alert_rules r ON r.id = h.rule_id
		WHERE r.user_id = $1`
	if filter.RuleID != nil {
		args = append(args, pgUUID(*filter.RuleID))
		query += fmt.Sprintf(" AND h.rule_id = $%d", len(args))
	}
	if filter.DeliveryStatus != nil {
		args = append(args, *filter.DeliveryStatus)
		query += fmt.Sprintf(" AND h.delivery_status = $%d", len(args))
	}
	if filter.Since != nil {
		args = append(args, *filter.Since)
		query += fmt.Sprintf(" AND h.triggered_at >= $%d", len(args))
	}

	args = append(args, pageSize, (page-1)*pageSize)
	query += fmt.Sprintf(`
		ORDER BY h.triggered_at DESC, h.id DESC
		LIMIT $%d OFFSET $%d`, len(args)-1, len(args))

	rows, err := r.replica.Query(ctx, query, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	items := make([]AlertHistoryEntry, 0, pageSize)
	total := 0
	for rows.Next() {
		var item AlertHistoryEntry
		if err := rows.Scan(
			&item.ID,
			&item.RuleID,
			&item.RuleName,
			&item.ListingID,
			&item.TriggeredAt,
			&item.Channel,
			&item.DeliveryStatus,
			&item.DeliveredAt,
			&item.ErrorDetail,
			&total,
		); err != nil {
			return nil, 0, err
		}
		items = append(items, item)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, err
	}

	return items, total, nil
}

func collectAlertRules(rows pgx.Rows) ([]AlertRule, int, error) {
	items := make([]AlertRule, 0)
	total := 0
	for rows.Next() {
		var (
			rule       AlertRule
			zoneIDsRaw []byte
			count      int
		)
		if err := rows.Scan(
			&rule.ID,
			&rule.UserID,
			&rule.Name,
			&zoneIDsRaw,
			&rule.Category,
			&rule.Filter,
			&rule.Channels,
			&rule.IsActive,
			&rule.CreatedAt,
			&rule.UpdatedAt,
			&count,
		); err != nil {
			return nil, 0, err
		}
		if err := json.Unmarshal(zoneIDsRaw, &rule.ZoneIDs); err != nil {
			return nil, 0, err
		}
		total = count
		items = append(items, rule)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, err
	}
	return items, total, nil
}

func scanAlertRule(row pgx.CollectableRow) (AlertRule, error) {
	var (
		rule       AlertRule
		zoneIDsRaw []byte
	)
	if err := row.Scan(
		&rule.ID,
		&rule.UserID,
		&rule.Name,
		&zoneIDsRaw,
		&rule.Category,
		&rule.Filter,
		&rule.Channels,
		&rule.IsActive,
		&rule.CreatedAt,
		&rule.UpdatedAt,
	); err != nil {
		return AlertRule{}, err
	}
	if err := json.Unmarshal(zoneIDsRaw, &rule.ZoneIDs); err != nil {
		return AlertRule{}, err
	}
	return rule, nil
}

func normalizePage(page, pageSize int) (int, int) {
	if page < 1 {
		page = 1
	}
	return page, clampLimit(pageSize, 20)
}

func jsonObjectOrDefault(raw json.RawMessage) string {
	trimmed := strings.TrimSpace(string(raw))
	if trimmed == "" || trimmed == "null" {
		return "{}"
	}
	return trimmed
}

func jsonArrayOrDefault(raw json.RawMessage) string {
	trimmed := strings.TrimSpace(string(raw))
	if trimmed == "" || trimmed == "null" {
		return "[]"
	}
	return trimmed
}
