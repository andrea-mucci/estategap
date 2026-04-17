package repository

import (
	"context"
	"errors"
	"fmt"

	"github.com/estategap/libs/models"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type ZoneAnalytics struct {
	ZoneID             uuid.UUID `json:"zone_id" db:"zone_id"`
	PeriodDays         int       `json:"period_days" db:"period_days"`
	AvgPricePerM2EUR   float64   `json:"avg_price_per_m2_eur" db:"avg_price_per_m2_eur"`
	MedianPriceEUR     float64   `json:"median_price_eur" db:"median_price_eur"`
	ListingCount       int64     `json:"listing_count" db:"listing_count"`
	PriceChangePercent float64   `json:"price_change_pct" db:"price_change_pct"`
}

type ZonesRepo struct {
	replica *pgxpool.Pool
}

func NewZonesRepo(replica *pgxpool.Pool) *ZonesRepo {
	return &ZonesRepo{replica: replica}
}

func (r *ZonesRepo) ListZones(ctx context.Context, country string, cursor string, limit int) ([]models.Zone, string, error) {
	limit = clampLimit(limit, 20)
	args := []any{country}
	query := `
		SELECT *
		FROM zones
		WHERE country_code = $1`
	if cursor != "" {
		cursorID, err := decodeIDCursor(cursor)
		if err != nil {
			return nil, "", err
		}
		args = append(args, pgUUID(cursorID))
		query += ` AND id > $2`
	}
	args = append(args, limit+1)
	query += fmt.Sprintf(" ORDER BY id ASC LIMIT $%d", len(args))

	rows, err := r.replica.Query(ctx, query, args...)
	if err != nil {
		return nil, "", err
	}
	items, err := pgx.CollectRows(rows, pgx.RowToStructByNameLax[models.Zone])
	if err != nil {
		return nil, "", err
	}

	var nextCursor string
	if len(items) > limit {
		last := items[limit-1]
		zoneID, err := uuidFromPG(last.ID)
		if err != nil {
			return nil, "", err
		}
		nextCursor = encodeIDCursor(zoneID)
		items = items[:limit]
	}

	return items, nextCursor, nil
}

func (r *ZonesRepo) GetZoneByID(ctx context.Context, id uuid.UUID) (*models.Zone, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT *
		FROM zones
		WHERE id = $1
		LIMIT 1`, pgUUID(id))
	if err != nil {
		return nil, err
	}
	item, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.Zone])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return item, err
}

func (r *ZonesRepo) GetZoneAnalytics(ctx context.Context, zoneID uuid.UUID, periodDays int) (*ZoneAnalytics, error) {
	query := `
		SELECT
			z.id AS zone_id,
			$2::int AS period_days,
			COALESCE(curr.avg_price_per_m2_eur, 0)::double precision AS avg_price_per_m2_eur,
			COALESCE(curr.median_price_eur, 0)::double precision AS median_price_eur,
			COALESCE(curr.listing_count, 0)::bigint AS listing_count,
			COALESCE(
				CASE
					WHEN prev.avg_price_per_m2_eur IS NULL OR prev.avg_price_per_m2_eur = 0 THEN 0
					ELSE ((curr.avg_price_per_m2_eur - prev.avg_price_per_m2_eur) / prev.avg_price_per_m2_eur) * 100
				END,
				0
			)::double precision AS price_change_pct
		FROM zones z
		LEFT JOIN LATERAL (
			SELECT
				AVG(l.price_per_m2_eur) AS avg_price_per_m2_eur,
				PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.asking_price_eur) AS median_price_eur,
				COUNT(*) AS listing_count
			FROM listings l
			WHERE l.zone_id = z.id
				AND l.status = 'active'
				AND l.first_seen_at >= NOW() - ($2 * INTERVAL '1 day')
		) curr ON TRUE
		LEFT JOIN LATERAL (
			SELECT AVG(l.price_per_m2_eur) AS avg_price_per_m2_eur
			FROM listings l
			WHERE l.zone_id = z.id
				AND l.status = 'active'
				AND l.first_seen_at >= NOW() - (($2 * 2) * INTERVAL '1 day')
				AND l.first_seen_at < NOW() - ($2 * INTERVAL '1 day')
		) prev ON TRUE
		WHERE z.id = $1
		LIMIT 1`

	rows, err := r.replica.Query(ctx, query, pgUUID(zoneID), periodDays)
	if err != nil {
		return nil, err
	}
	item, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[ZoneAnalytics])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return item, err
}
