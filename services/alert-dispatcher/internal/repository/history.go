package repository

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

var (
	ErrDuplicateEvent = errors.New("duplicate event")
	ErrNotFound       = errors.New("not found")
)

type historyExec interface {
	Exec(ctx context.Context, sql string, arguments ...any) (pgconn.CommandTag, error)
}

type HistoryRepo struct {
	primary historyExec
	replica historyExec
}

func NewHistoryRepo(primary, replica *pgxpool.Pool) *HistoryRepo {
	return &HistoryRepo{
		primary: primary,
		replica: replica,
	}
}

func NewHistoryRepoWithClients(primary, replica historyExec) *HistoryRepo {
	return &HistoryRepo{
		primary: primary,
		replica: replica,
	}
}

func (r *HistoryRepo) Insert(ctx context.Context, historyID, eventID, ruleID, listingID, channel string) error {
	var nullableListing any
	if trimmed := strings.TrimSpace(listingID); trimmed != "" {
		nullableListing = trimmed
	}

	tag, err := r.primary.Exec(ctx, `
		INSERT INTO alert_history (
			id,
			event_id,
			rule_id,
			listing_id,
			channel,
			delivery_status,
			attempt_count,
			triggered_at
		)
		VALUES (
			$1::uuid,
			NULLIF($2, '')::uuid,
			$3::uuid,
			$4::uuid,
			$5,
			'pending',
			1,
			NOW()
		)
		ON CONFLICT (event_id, channel)
		WHERE event_id IS NOT NULL DO NOTHING
	`, historyID, strings.TrimSpace(eventID), ruleID, nullableListing, channel)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrDuplicateEvent
	}
	return nil
}

func (r *HistoryRepo) UpdateStatus(
	ctx context.Context,
	historyID,
	status,
	errorDetail string,
	attempts int,
	deliveredAt *time.Time,
) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE alert_history
		SET delivery_status = $2,
			error_detail = NULLIF($3, ''),
			attempt_count = $4,
			delivered_at = $5
		WHERE id = $1::uuid
	`, historyID, status, strings.TrimSpace(errorDetail), attempts, deliveredAt)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}
