package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"hash/fnv"
	"sort"
	"strings"
	"time"

	"github.com/estategap/services/api-gateway/internal/cache"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

type ZoneWithStats struct {
	ID               uuid.UUID
	Name             string
	NameLocal        *string
	CountryCode      string
	Level            int16
	ParentID         *uuid.UUID
	AreaKm2          *float64
	Slug             *string
	ListingCount     int64
	MedianPriceM2EUR float64
	DealCount        int64
	PriceTrendPct    *float64
}

type ZoneMonthStat struct {
	Month            time.Time
	MedianPriceM2EUR float64
	ListingVolume    int64
	DealCount        int64
}

type ZoneCompareItem struct {
	ID                 uuid.UUID
	Name               string
	NameLocal          *string
	CountryCode        string
	Level              int16
	ParentID           *uuid.UUID
	AreaKm2            *float64
	Slug               *string
	ListingCount       int64
	MedianPriceM2EUR   float64
	DealCount          int64
	PriceTrendPct      *float64
	LocalCurrency      string
	MedianPriceM2Local *float64
}

type ZonesRepo struct {
	primary *pgxpool.Pool
	replica *pgxpool.Pool
	cache   *cache.Client
}

type ZoneGeometry struct {
	ZoneID   uuid.UUID       `json:"zone_id"`
	ZoneName string          `json:"zone_name"`
	Geometry json.RawMessage `json:"geometry"`
	BBox     [4]float64      `json:"bbox"`
}

type CreateCustomZoneRequest struct {
	Name     string
	Type     string
	Country  string
	Geometry json.RawMessage
}

func NewZonesRepo(primary, replica *pgxpool.Pool, cacheClient *cache.Client) *ZonesRepo {
	return &ZonesRepo{
		primary: primary,
		replica: replica,
		cache:   cacheClient,
	}
}

func (r *ZonesRepo) ListZones(ctx context.Context, country string, level *int, parentID *uuid.UUID, cursor string, limit int) ([]ZoneWithStats, string, int64, error) {
	limit = clampLimit(limit, 20)

	baseArgs := make([]any, 0, 3)
	baseConditions := make([]string, 0, 3)
	if country != "" {
		baseArgs = append(baseArgs, country)
		baseConditions = append(baseConditions, fmt.Sprintf("z.country_code = $%d", len(baseArgs)))
	}
	if level != nil {
		baseArgs = append(baseArgs, *level)
		baseConditions = append(baseConditions, fmt.Sprintf("z.level = $%d", len(baseArgs)))
	}
	if parentID != nil {
		baseArgs = append(baseArgs, pgUUID(*parentID))
		baseConditions = append(baseConditions, fmt.Sprintf("z.parent_id = $%d", len(baseArgs)))
	}

	args := append([]any(nil), baseArgs...)
	conditions := append([]string(nil), baseConditions...)
	if cursor != "" {
		cursorID, err := decodeIDCursor(cursor)
		if err != nil {
			return nil, "", 0, fmt.Errorf("%w: invalid cursor", ErrInvalidInput)
		}
		args = append(args, pgUUID(cursorID))
		conditions = append(conditions, fmt.Sprintf("z.id > $%d", len(args)))
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	args = append(args, limit+1)
	query := `
		SELECT
			z.id,
			z.name,
			z.name_local,
			z.country_code,
			z.level,
			z.parent_id,
			z.area_km2::double precision AS area_km2,
			z.slug,
			COALESCE(zs.listing_count, 0)::bigint AS listing_count,
			COALESCE(zs.median_price_m2_eur, 0)::double precision AS median_price_m2_eur,
			COALESCE(zs.deal_count, 0)::bigint AS deal_count,
			zs.price_trend_pct::double precision AS price_trend_pct
		FROM zones z
		LEFT JOIN zone_statistics zs ON zs.zone_id = z.id
	` + whereClause + `
		ORDER BY z.id ASC
		LIMIT $` + fmt.Sprintf("%d", len(args))

	rows, err := r.replica.Query(ctx, query, args...)
	if err != nil {
		return nil, "", 0, err
	}
	items, err := pgx.CollectRows(rows, scanZoneWithStats)
	if err != nil {
		return nil, "", 0, err
	}

	countQuery := `SELECT COUNT(*) FROM zones z`
	if len(baseConditions) > 0 {
		countQuery += ` WHERE ` + strings.Join(baseConditions, " AND ")
	}

	var totalCount int64
	if err := r.replica.QueryRow(ctx, countQuery, baseArgs...).Scan(&totalCount); err != nil {
		return nil, "", 0, err
	}

	var nextCursor string
	if len(items) > limit {
		nextCursor = encodeIDCursor(items[limit-1].ID)
		items = items[:limit]
	}

	return items, nextCursor, totalCount, nil
}

func (r *ZonesRepo) GetZoneByID(ctx context.Context, id uuid.UUID) (*ZoneWithStats, error) {
	return cache.GetOrSet(ctx, r.cache, "cache:zone:"+id.String(), 5*time.Minute, func() (*ZoneWithStats, error) {
		rows, err := r.replica.Query(ctx, `
			SELECT
				z.id,
				z.name,
				z.name_local,
				z.country_code,
				z.level,
				z.parent_id,
				z.area_km2::double precision AS area_km2,
				z.slug,
				COALESCE(zs.listing_count, 0)::bigint AS listing_count,
				COALESCE(zs.median_price_m2_eur, 0)::double precision AS median_price_m2_eur,
				COALESCE(zs.deal_count, 0)::bigint AS deal_count,
				zs.price_trend_pct::double precision AS price_trend_pct
			FROM zones z
			LEFT JOIN zone_statistics zs ON zs.zone_id = z.id
			WHERE z.id = $1
			LIMIT 1`, pgUUID(id))
		if err != nil {
			return nil, err
		}

		item, err := pgx.CollectOneRow(rows, scanZoneWithStats)
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return &item, err
	})
}

func (r *ZonesRepo) GetZoneAnalytics(ctx context.Context, zoneID uuid.UUID) ([]ZoneMonthStat, error) {
	return cache.GetOrSet(ctx, r.cache, "cache:zone_analytics:"+zoneID.String(), 5*time.Minute, func() ([]ZoneMonthStat, error) {
		var exists bool
		if err := r.replica.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM zones WHERE id = $1)`, pgUUID(zoneID)).Scan(&exists); err != nil {
			return nil, err
		}
		if !exists {
			return nil, ErrNotFound
		}

		rows, err := r.replica.Query(ctx, `
			WITH months AS (
				SELECT generate_series(
					date_trunc('month', NOW()) - INTERVAL '11 months',
					date_trunc('month', NOW()),
					INTERVAL '1 month'
				) AS month
			),
			stats AS (
				SELECT
					date_trunc('month', ph.recorded_at) AS month,
					COALESCE(
						PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.price_per_m2_eur),
						0
					)::double precision AS median_price_m2_eur,
					COUNT(DISTINCT ph.listing_id)::bigint AS listing_volume,
					COUNT(DISTINCT ph.listing_id) FILTER (WHERE l.deal_tier IN (1, 2))::bigint AS deal_count
				FROM price_history ph
				JOIN listings l ON l.id = ph.listing_id AND l.country = ph.country
				WHERE l.zone_id = $1
					AND ph.recorded_at >= date_trunc('month', NOW()) - INTERVAL '11 months'
				GROUP BY 1
			)
			SELECT
				m.month,
				COALESCE(s.median_price_m2_eur, 0)::double precision AS median_price_m2_eur,
				COALESCE(s.listing_volume, 0)::bigint AS listing_volume,
				COALESCE(s.deal_count, 0)::bigint AS deal_count
			FROM months m
			LEFT JOIN stats s ON s.month = m.month
			ORDER BY m.month ASC`, pgUUID(zoneID))
		if err != nil {
			return nil, err
		}

		return pgx.CollectRows(rows, func(row pgx.CollectableRow) (ZoneMonthStat, error) {
			var item ZoneMonthStat
			err := row.Scan(&item.Month, &item.MedianPriceM2EUR, &item.ListingVolume, &item.DealCount)
			return item, err
		})
	})
}

func (r *ZonesRepo) GetZoneGeometry(ctx context.Context, zoneID uuid.UUID) (*ZoneGeometry, error) {
	return cache.GetOrSet(ctx, r.cache, "zone:geometry:"+zoneID.String(), 5*time.Minute, func() (*ZoneGeometry, error) {
		row := r.replica.QueryRow(ctx, `
			SELECT
				z.id,
				z.name,
				ST_AsGeoJSON(z.geometry)::json AS geometry,
				ARRAY[
					ST_XMin(z.bbox),
					ST_YMin(z.bbox),
					ST_XMax(z.bbox),
					ST_YMax(z.bbox)
				]::double precision[] AS bbox
			FROM zones z
			WHERE z.id = $1
			LIMIT 1`, pgUUID(zoneID))

		var (
			rawID    pgtype.UUID
			geometry json.RawMessage
			bbox     []float64
			item     ZoneGeometry
		)
		if err := row.Scan(&rawID, &item.ZoneName, &geometry, &bbox); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return nil, ErrNotFound
			}
			return nil, err
		}

		parsedID, err := uuidFromPG(rawID)
		if err != nil {
			return nil, err
		}
		item.ZoneID = parsedID
		item.Geometry = geometry
		if len(bbox) == 4 {
			copy(item.BBox[:], bbox)
		}

		return &item, nil
	})
}

func (r *ZonesRepo) CreateCustomZone(ctx context.Context, req CreateCustomZoneRequest, userID uuid.UUID) (*ZoneWithStats, error) {
	if r.primary == nil {
		return nil, ErrInvalidInput
	}

	var isValid bool
	if err := r.primary.QueryRow(ctx, `
		SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON($1), 4326))`,
		string(req.Geometry),
	).Scan(&isValid); err != nil {
		return nil, err
	}
	if !isValid {
		return nil, ErrValidation
	}

	var count int64
	if err := r.primary.QueryRow(ctx, `
		SELECT COUNT(*)
		FROM zones
		WHERE user_id = $1
			AND level = 5`,
		pgUUID(userID),
	).Scan(&count); err != nil {
		return nil, err
	}
	if count >= 20 {
		return nil, ErrLimitReached
	}

	rows, err := r.primary.Query(ctx, `
		INSERT INTO zones (
			name,
			country_code,
			level,
			parent_id,
			geometry,
			bbox,
			user_id,
			created_at,
			updated_at
		)
		VALUES (
			$1,
			$2,
			5,
			NULL,
			ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON($3), 4326)),
			ST_Envelope(ST_SetSRID(ST_GeomFromGeoJSON($3), 4326)),
			$4,
			NOW(),
			NOW()
		)
		RETURNING
			id,
			name,
			name_local,
			country_code,
			level,
			parent_id,
			NULL::double precision AS area_km2,
			slug,
			0::bigint AS listing_count,
			0::double precision AS median_price_m2_eur,
			0::bigint AS deal_count,
			NULL::double precision AS price_trend_pct`,
		req.Name,
		req.Country,
		string(req.Geometry),
		pgUUID(userID),
	)
	if err != nil {
		return nil, err
	}

	item, err := pgx.CollectOneRow(rows, scanZoneWithStats)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &item, err
}

func (r *ZonesRepo) CompareZones(ctx context.Context, ids []uuid.UUID) ([]ZoneCompareItem, error) {
	uniqueIDs := dedupeZoneIDs(ids)
	if len(uniqueIDs) < 2 || len(uniqueIDs) > 5 {
		return nil, fmt.Errorf("%w: ids must contain between 2 and 5 zone ids", ErrInvalidInput)
	}

	cacheKey := "cache:zone_compare:" + hashZoneIDs(uniqueIDs)
	return cache.GetOrSet(ctx, r.cache, cacheKey, 2*time.Minute, func() ([]ZoneCompareItem, error) {
		idTexts := make([]string, 0, len(uniqueIDs))
		for _, id := range uniqueIDs {
			idTexts = append(idTexts, id.String())
		}

		rows, err := r.replica.Query(ctx, `
			SELECT
				z.id,
				z.name,
				z.name_local,
				z.country_code,
				z.level,
				z.parent_id,
				z.area_km2::double precision AS area_km2,
				z.slug,
				COALESCE(zs.listing_count, 0)::bigint AS listing_count,
				COALESCE(zs.median_price_m2_eur, 0)::double precision AS median_price_m2_eur,
				COALESCE(zs.deal_count, 0)::bigint AS deal_count,
				zs.price_trend_pct::double precision AS price_trend_pct,
				COALESCE(c.currency, 'EUR') AS local_currency,
				CASE
					WHEN COALESCE(c.currency, 'EUR') = 'EUR' THEN COALESCE(zs.median_price_m2_eur, 0)::double precision
					WHEN er.rate_to_eur IS NULL OR er.rate_to_eur = 0 OR zs.median_price_m2_eur IS NULL THEN NULL
					ELSE (zs.median_price_m2_eur / er.rate_to_eur)::double precision
				END AS median_price_m2_local
			FROM zones z
			LEFT JOIN zone_statistics zs ON zs.zone_id = z.id
			LEFT JOIN countries c ON c.code = z.country_code
			LEFT JOIN LATERAL (
				SELECT rate_to_eur
				FROM exchange_rates
				WHERE currency = c.currency
				ORDER BY date DESC
				LIMIT 1
			) er ON TRUE
			WHERE z.id::text = ANY($1)`, idTexts)
		if err != nil {
			return nil, err
		}

		items, err := pgx.CollectRows(rows, scanZoneCompareItem)
		if err != nil {
			return nil, err
		}
		if len(items) != len(uniqueIDs) {
			return nil, ErrNotFound
		}

		byID := make(map[uuid.UUID]ZoneCompareItem, len(items))
		for _, item := range items {
			byID[item.ID] = item
		}

		ordered := make([]ZoneCompareItem, 0, len(uniqueIDs))
		for _, id := range uniqueIDs {
			item, ok := byID[id]
			if !ok {
				return nil, ErrNotFound
			}
			ordered = append(ordered, item)
		}

		return ordered, nil
	})
}

func scanZoneWithStats(row pgx.CollectableRow) (ZoneWithStats, error) {
	var (
		item          ZoneWithStats
		rawID         pgtype.UUID
		rawParent     pgtype.UUID
		nameLocal     sql.NullString
		areaKm2       sql.NullFloat64
		slug          sql.NullString
		priceTrendPct sql.NullFloat64
	)

	err := row.Scan(
		&rawID,
		&item.Name,
		&nameLocal,
		&item.CountryCode,
		&item.Level,
		&rawParent,
		&areaKm2,
		&slug,
		&item.ListingCount,
		&item.MedianPriceM2EUR,
		&item.DealCount,
		&priceTrendPct,
	)
	if err != nil {
		return ZoneWithStats{}, err
	}

	parsedID, err := uuidFromPG(rawID)
	if err != nil {
		return ZoneWithStats{}, err
	}
	item.ID = parsedID
	item.ParentID = uuidPtrFromPG(rawParent)
	if nameLocal.Valid {
		item.NameLocal = &nameLocal.String
	}
	if areaKm2.Valid {
		item.AreaKm2 = &areaKm2.Float64
	}
	if slug.Valid {
		item.Slug = &slug.String
	}
	if priceTrendPct.Valid {
		item.PriceTrendPct = &priceTrendPct.Float64
	}

	return item, nil
}

func scanZoneCompareItem(row pgx.CollectableRow) (ZoneCompareItem, error) {
	var (
		item               ZoneCompareItem
		rawID              pgtype.UUID
		rawParent          pgtype.UUID
		nameLocal          sql.NullString
		areaKm2            sql.NullFloat64
		slug               sql.NullString
		priceTrendPct      sql.NullFloat64
		medianPriceM2Local sql.NullFloat64
	)

	err := row.Scan(
		&rawID,
		&item.Name,
		&nameLocal,
		&item.CountryCode,
		&item.Level,
		&rawParent,
		&areaKm2,
		&slug,
		&item.ListingCount,
		&item.MedianPriceM2EUR,
		&item.DealCount,
		&priceTrendPct,
		&item.LocalCurrency,
		&medianPriceM2Local,
	)
	if err != nil {
		return ZoneCompareItem{}, err
	}

	parsedID, err := uuidFromPG(rawID)
	if err != nil {
		return ZoneCompareItem{}, err
	}
	item.ID = parsedID
	item.ParentID = uuidPtrFromPG(rawParent)
	if nameLocal.Valid {
		item.NameLocal = &nameLocal.String
	}
	if areaKm2.Valid {
		item.AreaKm2 = &areaKm2.Float64
	}
	if slug.Valid {
		item.Slug = &slug.String
	}
	if priceTrendPct.Valid {
		item.PriceTrendPct = &priceTrendPct.Float64
	}
	if medianPriceM2Local.Valid {
		item.MedianPriceM2Local = &medianPriceM2Local.Float64
	}

	return item, nil
}

func uuidPtrFromPG(value pgtype.UUID) *uuid.UUID {
	if !value.Valid {
		return nil
	}

	parsed := uuid.UUID(value.Bytes)
	return &parsed
}

func dedupeZoneIDs(ids []uuid.UUID) []uuid.UUID {
	seen := make(map[uuid.UUID]struct{}, len(ids))
	unique := make([]uuid.UUID, 0, len(ids))
	for _, id := range ids {
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		unique = append(unique, id)
	}
	return unique
}

func hashZoneIDs(ids []uuid.UUID) string {
	idTexts := make([]string, 0, len(ids))
	for _, id := range ids {
		idTexts = append(idTexts, id.String())
	}
	sort.Strings(idTexts)

	hash := fnv.New32a()
	_, _ = hash.Write([]byte(strings.Join(idTexts, ",")))
	return fmt.Sprintf("%x", hash.Sum32())
}
