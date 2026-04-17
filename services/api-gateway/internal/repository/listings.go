package repository

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/estategap/libs/models"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type ListingFilter struct {
	Country          string
	City             string
	MinPriceEUR      *float64
	MaxPriceEUR      *float64
	MinAreaM2        *float64
	MaxAreaM2        *float64
	PropertyCategory *models.PropertyCategory
	DealTier         *models.DealTier
	Status           *models.ListingStatus
	Cursor           string
	Limit            int
}

type ListingsRepo struct {
	replica *pgxpool.Pool
}

func NewListingsRepo(replica *pgxpool.Pool) *ListingsRepo {
	return &ListingsRepo{replica: replica}
}

func (r *ListingsRepo) SearchListings(ctx context.Context, filter ListingFilter) ([]models.Listing, string, error) {
	limit := clampLimit(filter.Limit, 20)
	args := []any{filter.Country}
	conditions := []string{"country = $1"}

	if filter.City != "" {
		args = append(args, filter.City)
		conditions = append(conditions, fmt.Sprintf("city = $%d", len(args)))
	}
	if filter.MinPriceEUR != nil {
		args = append(args, *filter.MinPriceEUR)
		conditions = append(conditions, fmt.Sprintf("asking_price_eur >= $%d", len(args)))
	}
	if filter.MaxPriceEUR != nil {
		args = append(args, *filter.MaxPriceEUR)
		conditions = append(conditions, fmt.Sprintf("asking_price_eur <= $%d", len(args)))
	}
	if filter.MinAreaM2 != nil {
		args = append(args, *filter.MinAreaM2)
		conditions = append(conditions, fmt.Sprintf("built_area_m2 >= $%d", len(args)))
	}
	if filter.MaxAreaM2 != nil {
		args = append(args, *filter.MaxAreaM2)
		conditions = append(conditions, fmt.Sprintf("built_area_m2 <= $%d", len(args)))
	}
	if filter.PropertyCategory != nil {
		args = append(args, string(*filter.PropertyCategory))
		conditions = append(conditions, fmt.Sprintf("property_category = $%d", len(args)))
	}
	if filter.DealTier != nil {
		args = append(args, int16(*filter.DealTier))
		conditions = append(conditions, fmt.Sprintf("deal_tier = $%d", len(args)))
	}
	if filter.Status != nil {
		args = append(args, string(*filter.Status))
		conditions = append(conditions, fmt.Sprintf("status = $%d", len(args)))
	}
	if filter.Cursor != "" {
		cursorTime, cursorID, err := decodeTimeCursor(filter.Cursor)
		if err != nil {
			return nil, "", err
		}
		args = append(args, cursorTime, pgUUID(cursorID))
		conditions = append(conditions, fmt.Sprintf("(first_seen_at, id) < ($%d, $%d)", len(args)-1, len(args)))
	}

	args = append(args, limit+1)

	query := `
		SELECT *
		FROM listings
		WHERE ` + strings.Join(conditions, " AND ") + `
		ORDER BY first_seen_at DESC, id DESC
		LIMIT $` + fmt.Sprintf("%d", len(args))

	rows, err := r.replica.Query(ctx, query, args...)
	if err != nil {
		return nil, "", err
	}
	items, err := pgx.CollectRows(rows, pgx.RowToStructByNameLax[models.Listing])
	if err != nil {
		return nil, "", err
	}

	var nextCursor string
	if len(items) > limit {
		last := items[limit-1]
		listingID, err := uuidFromPG(last.ID)
		if err != nil {
			return nil, "", err
		}
		nextCursor = encodeTimeCursor(last.FirstSeenAt.Time.UTC(), listingID)
		items = items[:limit]
	}

	return items, nextCursor, nil
}

func (r *ListingsRepo) GetListingByID(ctx context.Context, id uuid.UUID) (*models.Listing, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT *
		FROM listings
		WHERE id = $1
		LIMIT 1`, pgUUID(id))
	if err != nil {
		return nil, err
	}
	item, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.Listing])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return item, err
}
