package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/estategap/libs/models"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type AlertInput struct {
	Name     string          `json:"name"`
	Filters  json.RawMessage `json:"filters"`
	Channels json.RawMessage `json:"channels"`
	Active   bool            `json:"active"`
}

type AlertEvent struct {
	ID           uuid.UUID `json:"id" db:"id"`
	TriggeredAt  string    `json:"triggered_at" db:"triggered_at"`
	ListingCount int64     `json:"listing_count" db:"listing_count"`
}

type AlertsRepo struct {
	primary *pgxpool.Pool
	replica *pgxpool.Pool
}

func NewAlertsRepo(primary, replica *pgxpool.Pool) *AlertsRepo {
	return &AlertsRepo{primary: primary, replica: replica}
}

func (r *AlertsRepo) ListAlerts(ctx context.Context, userID uuid.UUID, cursor string, limit int) ([]models.AlertRule, string, error) {
	limit = clampLimit(limit, 20)
	args := []any{pgUUID(userID)}
	query := `
		SELECT *
		FROM alert_rules
		WHERE user_id = $1`
	if cursor != "" {
		cursorTime, cursorID, err := decodeTimeCursor(cursor)
		if err != nil {
			return nil, "", err
		}
		args = append(args, cursorTime, pgUUID(cursorID))
		query += fmt.Sprintf(" AND (created_at, id) < ($%d, $%d)", len(args)-1, len(args))
	}
	args = append(args, limit+1)
	query += fmt.Sprintf(" ORDER BY created_at DESC, id DESC LIMIT $%d", len(args))

	rows, err := r.replica.Query(ctx, query, args...)
	if err != nil {
		return nil, "", err
	}
	items, err := pgx.CollectRows(rows, pgx.RowToStructByNameLax[models.AlertRule])
	if err != nil {
		return nil, "", err
	}

	var nextCursor string
	if len(items) > limit {
		last := items[limit-1]
		alertID, err := uuidFromPG(last.ID)
		if err != nil {
			return nil, "", err
		}
		nextCursor = encodeTimeCursor(last.CreatedAt.Time.UTC(), alertID)
		items = items[:limit]
	}

	return items, nextCursor, nil
}

func (r *AlertsRepo) CreateAlert(ctx context.Context, userID uuid.UUID, input AlertInput) (*models.AlertRule, error) {
	if err := r.ensureAlertCapacity(ctx, userID, uuid.Nil, input.Active); err != nil {
		return nil, err
	}

	rows, err := r.primary.Query(ctx, `
		INSERT INTO alert_rules (user_id, name, filters, channels, active)
		VALUES ($1, $2, $3::jsonb, $4::jsonb, $5)
		RETURNING *`,
		pgUUID(userID), input.Name, jsonOrEmpty(input.Filters), jsonOrEmpty(input.Channels), input.Active)
	if err != nil {
		return nil, err
	}
	item, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.AlertRule])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return item, err
}

func (r *AlertsRepo) GetAlertByID(ctx context.Context, id, userID uuid.UUID) (*models.AlertRule, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT *
		FROM alert_rules
		WHERE id = $1 AND user_id = $2
		LIMIT 1`, pgUUID(id), pgUUID(userID))
	if err != nil {
		return nil, err
	}
	item, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.AlertRule])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return item, err
}

func (r *AlertsRepo) UpdateAlert(ctx context.Context, id, userID uuid.UUID, input AlertInput) (*models.AlertRule, error) {
	if err := r.ensureAlertCapacity(ctx, userID, id, input.Active); err != nil {
		return nil, err
	}

	rows, err := r.primary.Query(ctx, `
		UPDATE alert_rules
		SET name = $3,
			filters = $4::jsonb,
			channels = $5::jsonb,
			active = $6,
			updated_at = NOW()
		WHERE id = $1 AND user_id = $2
		RETURNING *`,
		pgUUID(id), pgUUID(userID), input.Name, jsonOrEmpty(input.Filters), jsonOrEmpty(input.Channels), input.Active)
	if err != nil {
		return nil, err
	}
	item, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.AlertRule])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return item, err
}

func (r *AlertsRepo) DeleteAlert(ctx context.Context, id, userID uuid.UUID) error {
	tag, err := r.primary.Exec(ctx, `
		DELETE FROM alert_rules
		WHERE id = $1 AND user_id = $2`, pgUUID(id), pgUUID(userID))
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *AlertsRepo) ListAlertHistory(ctx context.Context, alertID, userID uuid.UUID, cursor string, limit int) ([]AlertEvent, string, error) {
	limit = clampLimit(limit, 20)
	args := []any{pgUUID(alertID), pgUUID(userID)}
	query := `
		SELECT
			l.id,
			TO_CHAR(COALESCE(l.sent_at, l.created_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS triggered_at,
			1::bigint AS listing_count
		FROM alert_log l
		JOIN alert_rules r ON r.id = l.rule_id
		WHERE l.rule_id = $1 AND r.user_id = $2`
	if cursor != "" {
		cursorTime, cursorID, err := decodeTimeCursor(cursor)
		if err != nil {
			return nil, "", err
		}
		args = append(args, cursorTime, pgUUID(cursorID))
		query += fmt.Sprintf(" AND (COALESCE(l.sent_at, l.created_at), l.id) < ($%d, $%d)", len(args)-1, len(args))
	}
	args = append(args, limit+1)
	query += fmt.Sprintf(" ORDER BY COALESCE(l.sent_at, l.created_at) DESC, l.id DESC LIMIT $%d", len(args))

	rows, err := r.replica.Query(ctx, query, args...)
	if err != nil {
		return nil, "", err
	}
	items, err := pgx.CollectRows(rows, pgx.RowToStructByNameLax[AlertEvent])
	if err != nil {
		return nil, "", err
	}

	var nextCursor string
	if len(items) > limit {
		last := items[limit-1]
		triggeredAt, err := parseRFC3339Millis(last.TriggeredAt)
		if err != nil {
			return nil, "", err
		}
		nextCursor = encodeTimeCursor(triggeredAt, last.ID)
		items = items[:limit]
	}

	return items, nextCursor, nil
}

func (r *AlertsRepo) ensureAlertCapacity(ctx context.Context, userID, excludeID uuid.UUID, desiredActive bool) error {
	if !desiredActive {
		return nil
	}

	var alertLimit int
	if err := r.replica.QueryRow(ctx, `
		SELECT alert_limit
		FROM users
		WHERE id = $1 AND deleted_at IS NULL`, pgUUID(userID)).Scan(&alertLimit); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return ErrNotFound
		}
		return err
	}

	var count int
	query := `SELECT COUNT(*) FROM alert_rules WHERE user_id = $1 AND active = TRUE`
	args := []any{pgUUID(userID)}
	if excludeID != uuid.Nil {
		args = append(args, pgUUID(excludeID))
		query += fmt.Sprintf(" AND id <> $%d", len(args))
	}
	if err := r.replica.QueryRow(ctx, query, args...).Scan(&count); err != nil {
		return err
	}
	if count >= alertLimit {
		return ErrAlertLimitReached
	}
	return nil
}

func jsonOrEmpty(raw json.RawMessage) string {
	trimmed := strings.TrimSpace(string(raw))
	if trimmed == "" {
		return "{}"
	}
	return trimmed
}
