package repository

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

type HistoryRepo struct {
	primary *pgxpool.Pool
	replica *pgxpool.Pool
}

func NewHistoryRepo(primary, replica *pgxpool.Pool) *HistoryRepo {
	return &HistoryRepo{
		primary: primary,
		replica: replica,
	}
}

func (r *HistoryRepo) InsertHistory(ctx context.Context, ruleID, listingID string, channel string) error {
	_, err := r.primary.Exec(ctx, `
		INSERT INTO alert_history (rule_id, listing_id, channel, delivery_status, triggered_at)
		VALUES ($1, $2, $3, 'pending', NOW())
	`, ruleID, listingID, channel)
	return err
}

func (r *HistoryRepo) ListUsersForListing(ctx context.Context, listingID string) ([]string, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT DISTINCT ar.user_id
		FROM alert_history ah
		JOIN alert_rules ar ON ar.id = ah.rule_id
		WHERE ah.listing_id = $1
	`, listingID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	userIDs := make([]string, 0)
	for rows.Next() {
		var userID string
		if err := rows.Scan(&userID); err != nil {
			return nil, err
		}
		userIDs = append(userIDs, userID)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	return userIDs, nil
}
