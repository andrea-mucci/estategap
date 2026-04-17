package repository

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/estategap/libs/models"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/shopspring/decimal"
)

type ListingFilter struct {
	Country           string
	City              string
	Bounds            *[4]float64
	ZoneID            *uuid.UUID
	PropertyType      string
	MinPriceEUR       *float64
	MaxPriceEUR       *float64
	MinAreaM2         *float64
	MaxAreaM2         *float64
	PropertyCategory  *models.PropertyCategory
	MinBedrooms       *int
	MinBathrooms      *int
	DealTier          *models.DealTier
	Status            *models.ListingStatus
	PortalID          *uuid.UUID
	MinDaysOnMarket   *int
	MaxDaysOnMarket   *int
	SortBy            string
	SortDir           string
	Currency          string
	FreeTierGate      bool
	AllowedCountries  []string
	Format            string
	DisablePagination bool
	Cursor            string
	Limit             int
}

type ListingDetail struct {
	Listing      *models.Listing
	PriceHistory []models.PriceHistory
	Comparables  []uuid.UUID
	ZoneStats    *ZoneStats
}

type ZoneStats struct {
	ZoneID           uuid.UUID
	ZoneName         string
	ListingCount     int64
	MedianPriceM2EUR float64
	DealCount        int64
}

type ListingsRepo struct {
	replica *pgxpool.Pool
}

func NewListingsRepo(replica *pgxpool.Pool) *ListingsRepo {
	return &ListingsRepo{replica: replica}
}

func (r *ListingsRepo) SearchListings(ctx context.Context, filter ListingFilter) ([]models.Listing, string, int64, string, error) {
	limit := clampLimit(filter.Limit, 20)
	sortBy := filter.SortBy
	if sortBy == "" {
		sortBy = "recency"
	}
	sortDir := strings.ToLower(filter.SortDir)
	if sortDir != "asc" {
		sortDir = "desc"
	}
	targetCurrency := strings.ToUpper(filter.Currency)
	if targetCurrency == "" {
		targetCurrency = "EUR"
	}

	baseArgs := []any{filter.Country}
	baseConditions := []string{"l.country = $1"}

	if filter.City != "" {
		baseArgs = append(baseArgs, filter.City)
		baseConditions = append(baseConditions, fmt.Sprintf("l.city = $%d", len(baseArgs)))
	}
	if filter.Bounds != nil {
		baseArgs = append(baseArgs, filter.Bounds[0], filter.Bounds[1], filter.Bounds[2], filter.Bounds[3])
		baseConditions = append(baseConditions,
			"l.location IS NOT NULL",
			fmt.Sprintf(
				"ST_Intersects(l.location, ST_MakeEnvelope($%d, $%d, $%d, $%d, 4326))",
				len(baseArgs)-3,
				len(baseArgs)-2,
				len(baseArgs)-1,
				len(baseArgs),
			),
		)
	}
	if filter.ZoneID != nil {
		baseArgs = append(baseArgs, pgUUID(*filter.ZoneID))
		baseConditions = append(baseConditions, fmt.Sprintf("l.zone_id = $%d", len(baseArgs)))
	}
	if filter.PropertyType != "" {
		baseArgs = append(baseArgs, filter.PropertyType)
		baseConditions = append(baseConditions, fmt.Sprintf("l.property_type ILIKE $%d", len(baseArgs)))
	}
	if filter.MinPriceEUR != nil {
		baseArgs = append(baseArgs, *filter.MinPriceEUR)
		baseConditions = append(baseConditions, fmt.Sprintf("l.asking_price_eur >= $%d", len(baseArgs)))
	}
	if filter.MaxPriceEUR != nil {
		baseArgs = append(baseArgs, *filter.MaxPriceEUR)
		baseConditions = append(baseConditions, fmt.Sprintf("l.asking_price_eur <= $%d", len(baseArgs)))
	}
	if filter.MinAreaM2 != nil {
		baseArgs = append(baseArgs, *filter.MinAreaM2)
		baseConditions = append(baseConditions, fmt.Sprintf("l.built_area_m2 >= $%d", len(baseArgs)))
	}
	if filter.MaxAreaM2 != nil {
		baseArgs = append(baseArgs, *filter.MaxAreaM2)
		baseConditions = append(baseConditions, fmt.Sprintf("l.built_area_m2 <= $%d", len(baseArgs)))
	}
	if filter.PropertyCategory != nil {
		baseArgs = append(baseArgs, string(*filter.PropertyCategory))
		baseConditions = append(baseConditions, fmt.Sprintf("l.property_category = $%d", len(baseArgs)))
	}
	if filter.MinBedrooms != nil {
		baseArgs = append(baseArgs, *filter.MinBedrooms)
		baseConditions = append(baseConditions, fmt.Sprintf("l.bedrooms >= $%d", len(baseArgs)))
	}
	if filter.MinBathrooms != nil {
		baseArgs = append(baseArgs, *filter.MinBathrooms)
		baseConditions = append(baseConditions, fmt.Sprintf("l.bathrooms >= $%d", len(baseArgs)))
	}
	if filter.DealTier != nil {
		baseArgs = append(baseArgs, int16(*filter.DealTier))
		baseConditions = append(baseConditions, fmt.Sprintf("l.deal_tier = $%d", len(baseArgs)))
	}
	if filter.Status != nil {
		baseArgs = append(baseArgs, string(*filter.Status))
		baseConditions = append(baseConditions, fmt.Sprintf("l.status = $%d", len(baseArgs)))
	}
	if filter.PortalID != nil {
		baseArgs = append(baseArgs, pgUUID(*filter.PortalID))
		baseConditions = append(baseConditions, fmt.Sprintf("l.portal_id = $%d", len(baseArgs)))
	}
	if filter.MinDaysOnMarket != nil {
		baseArgs = append(baseArgs, *filter.MinDaysOnMarket)
		baseConditions = append(baseConditions, fmt.Sprintf("l.days_on_market >= $%d", len(baseArgs)))
	}
	if filter.MaxDaysOnMarket != nil {
		baseArgs = append(baseArgs, *filter.MaxDaysOnMarket)
		baseConditions = append(baseConditions, fmt.Sprintf("l.days_on_market <= $%d", len(baseArgs)))
	}
	if filter.FreeTierGate {
		baseConditions = append(baseConditions, "l.first_seen_at < NOW() - INTERVAL '48 hours'")
	}
	if len(filter.AllowedCountries) > 0 {
		baseArgs = append(baseArgs, filter.AllowedCountries)
		baseConditions = append(baseConditions, fmt.Sprintf("l.country = ANY($%d)", len(baseArgs)))
	}
	if sortBy == "deal_score" {
		baseConditions = append(baseConditions, "l.deal_score IS NOT NULL")
	}
	if sortBy == "days_on_market" {
		baseConditions = append(baseConditions, "l.days_on_market IS NOT NULL")
	}

	args := append([]any(nil), baseArgs...)
	conditions := append([]string(nil), baseConditions...)
	if filter.Cursor != "" {
		switch sortBy {
		case "recency":
			cursorTime, cursorID, err := decodeTimeCursor(filter.Cursor)
			if err != nil {
				return nil, "", 0, "", fmt.Errorf("%w: invalid cursor", ErrInvalidInput)
			}
			args = append(args, cursorTime, pgUUID(cursorID))
			conditions = append(conditions, fmt.Sprintf("(l.first_seen_at, l.id) %s ($%d, $%d)", listingCursorOperator(sortDir), len(args)-1, len(args)))
		default:
			cursorValue, cursorID, err := decodeFloatCursor(filter.Cursor)
			if err != nil {
				return nil, "", 0, "", fmt.Errorf("%w: invalid cursor", ErrInvalidInput)
			}
			args = append(args, cursorValue, pgUUID(cursorID))
			conditions = append(conditions, fmt.Sprintf("((%s), l.id) %s ($%d, $%d)", listingCursorExpression(sortBy), listingCursorOperator(sortDir), len(args)-1, len(args)))
		}
	}

	selectColumns := `
		l.*,
		ST_Y(l.location)::double precision AS latitude,
		ST_X(l.location)::double precision AS longitude`
	joins := ""
	if targetCurrency != "EUR" {
		args = append(args, targetCurrency)
		joins = fmt.Sprintf(`
			LEFT JOIN LATERAL (
				SELECT rate_to_eur, date
				FROM exchange_rates
				WHERE currency = $%d
				ORDER BY date DESC
				LIMIT 1
			) er ON TRUE`, len(args))
		selectColumns += `,
			CASE
				WHEN er.rate_to_eur IS NULL OR er.rate_to_eur = 0 OR l.asking_price_eur IS NULL THEN NULL
				ELSE l.asking_price_eur / er.rate_to_eur
			END AS price_converted,
			er.date AS exchange_rate_date`
	}

	query := `
		SELECT ` + selectColumns + `
		FROM listings l
	` + joins + `
		WHERE ` + strings.Join(conditions, " AND ") + `
		ORDER BY ` + listingSortColumn(sortBy) + ` ` + sortDir + `, l.id ` + sortDir

	if !filter.DisablePagination {
		args = append(args, limit+1)
		query += `
		LIMIT $` + fmt.Sprintf("%d", len(args))
	}

	rows, err := r.replica.Query(ctx, query, args...)
	if err != nil {
		return nil, "", 0, "", err
	}
	items, err := pgx.CollectRows(rows, pgx.RowToStructByNameLax[models.Listing])
	if err != nil {
		return nil, "", 0, "", err
	}

	var totalCount int64
	if filter.DisablePagination {
		totalCount = int64(len(items))
	} else {
		countCtx, cancel := context.WithTimeout(ctx, 200*time.Millisecond)
		defer cancel()

		countQuery := `
			SELECT COUNT(*)
			FROM listings l
			WHERE ` + strings.Join(baseConditions, " AND ")
		if err := r.replica.QueryRow(countCtx, countQuery, baseArgs...).Scan(&totalCount); err != nil {
			return nil, "", 0, "", err
		}
	}

	var rateDate string
	if len(items) > 0 && items[0].ExchangeRateDate.Valid {
		rateDate = items[0].ExchangeRateDate.Time.Format("2006-01-02")
	}

	var nextCursor string
	if !filter.DisablePagination && len(items) > limit {
		last := items[limit-1]
		listingID, err := uuidFromPG(last.ID)
		if err != nil {
			return nil, "", 0, "", err
		}

		switch sortBy {
		case "recency":
			nextCursor = encodeTimeCursor(last.FirstSeenAt.Time.UTC(), listingID)
		default:
			cursorValue, err := listingCursorValue(&last, sortBy)
			if err != nil {
				return nil, "", 0, "", err
			}
			nextCursor = encodeFloatCursor(cursorValue, listingID)
		}
		items = items[:limit]
	}

	return items, nextCursor, totalCount, rateDate, nil
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

func (r *ListingsRepo) GetListingDetail(ctx context.Context, id uuid.UUID) (*ListingDetail, error) {
	listing, err := r.GetListingByID(ctx, id)
	if err != nil {
		return nil, err
	}

	detail := &ListingDetail{
		Listing:      listing,
		PriceHistory: []models.PriceHistory{},
		Comparables:  []uuid.UUID{},
	}

	zoneID, hasZone := listingZoneID(listing)
	runComparables := hasZone && listing.PropertyCategory != nil && listing.AskingPriceEUR != nil

	var (
		priceHistory []models.PriceHistory
		comparables  []uuid.UUID
		zoneStats    *ZoneStats
		wg           sync.WaitGroup
		errCh        = make(chan error, 3)
	)

	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	wg.Add(1)
	go func() {
		defer wg.Done()

		rows, err := r.replica.Query(ctx, `
			SELECT old_price_eur, new_price_eur, change_type, recorded_at
			FROM price_history
			WHERE listing_id = $1
			ORDER BY recorded_at ASC`, pgUUID(id))
		if err != nil {
			errCh <- err
			cancel()
			return
		}

		items, err := pgx.CollectRows(rows, pgx.RowToStructByNameLax[models.PriceHistory])
		if err != nil {
			errCh <- err
			cancel()
			return
		}
		priceHistory = items
	}()

	if runComparables {
		wg.Add(1)
		go func() {
			defer wg.Done()

			priceLow := listing.AskingPriceEUR.Mul(decimal.NewFromFloat(0.8))
			priceHigh := listing.AskingPriceEUR.Mul(decimal.NewFromFloat(1.2))

			rows, err := r.replica.Query(ctx, `
				SELECT id
				FROM listings
				WHERE zone_id = $1
					AND property_category = $2
					AND asking_price_eur BETWEEN $3 AND $4
					AND id != $5
					AND status = 'active'
				LIMIT 5`,
				pgUUID(zoneID),
				string(*listing.PropertyCategory),
				priceLow,
				priceHigh,
				pgUUID(id),
			)
			if err != nil {
				errCh <- err
				cancel()
				return
			}

			items, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (uuid.UUID, error) {
				var rawID pgtype.UUID
				if err := row.Scan(&rawID); err != nil {
					return uuid.Nil, err
				}
				return uuidFromPG(rawID)
			})
			if err != nil {
				errCh <- err
				cancel()
				return
			}
			comparables = items
		}()
	}

	if hasZone {
		wg.Add(1)
		go func() {
			defer wg.Done()

			rows, err := r.replica.Query(ctx, `
				SELECT
					zs.zone_id,
					z.name AS zone_name,
					COALESCE(zs.listing_count, 0)::bigint AS listing_count,
					COALESCE(zs.median_price_m2_eur, 0)::double precision AS median_price_m2_eur,
					COALESCE(zs.deal_count, 0)::bigint AS deal_count
				FROM zone_statistics zs
				JOIN zones z ON z.id = zs.zone_id
				WHERE zs.zone_id = $1
				LIMIT 1`,
				pgUUID(zoneID),
			)
			if err != nil {
				errCh <- err
				cancel()
				return
			}

			type zoneStatsRow struct {
				ZoneID           pgtype.UUID `db:"zone_id"`
				ZoneName         string      `db:"zone_name"`
				ListingCount     int64       `db:"listing_count"`
				MedianPriceM2EUR float64     `db:"median_price_m2_eur"`
				DealCount        int64       `db:"deal_count"`
			}

			item, err := pgx.CollectOneRow(rows, pgx.RowToStructByNameLax[zoneStatsRow])
			if err != nil {
				if errors.Is(err, pgx.ErrNoRows) {
					return
				}
				errCh <- err
				cancel()
				return
			}

			parsedZoneID, err := uuidFromPG(item.ZoneID)
			if err != nil {
				errCh <- err
				cancel()
				return
			}
			zoneStats = &ZoneStats{
				ZoneID:           parsedZoneID,
				ZoneName:         item.ZoneName,
				ListingCount:     item.ListingCount,
				MedianPriceM2EUR: item.MedianPriceM2EUR,
				DealCount:        item.DealCount,
			}
		}()
	}

	wg.Wait()
	close(errCh)

	for err := range errCh {
		if err != nil {
			return nil, err
		}
	}

	detail.PriceHistory = priceHistory
	detail.Comparables = comparables
	detail.ZoneStats = zoneStats

	return detail, nil
}

func listingSortColumn(sortBy string) string {
	switch sortBy {
	case "deal_score":
		return "l.deal_score"
	case "price":
		return "l.asking_price_eur"
	case "price_m2":
		return "l.price_per_m2_eur"
	case "days_on_market":
		return "l.days_on_market"
	default:
		return "l.first_seen_at"
	}
}

func listingCursorExpression(sortBy string) string {
	switch sortBy {
	case "deal_score":
		return "l.deal_score::double precision"
	case "price":
		return "l.asking_price_eur::double precision"
	case "price_m2":
		return "l.price_per_m2_eur::double precision"
	case "days_on_market":
		return "l.days_on_market::double precision"
	default:
		return "EXTRACT(EPOCH FROM l.first_seen_at)"
	}
}

func listingCursorOperator(sortDir string) string {
	if sortDir == "asc" {
		return ">"
	}
	return "<"
}

func listingCursorValue(item *models.Listing, sortBy string) (float64, error) {
	switch sortBy {
	case "deal_score":
		if item.DealScore == nil {
			return 0, fmt.Errorf("%w: missing deal_score cursor value", ErrInvalidInput)
		}
		return item.DealScore.InexactFloat64(), nil
	case "price":
		if item.AskingPriceEUR == nil {
			return 0, fmt.Errorf("%w: missing asking_price_eur cursor value", ErrInvalidInput)
		}
		return item.AskingPriceEUR.InexactFloat64(), nil
	case "price_m2":
		if item.PricePerM2EUR == nil {
			return 0, fmt.Errorf("%w: missing price_per_m2_eur cursor value", ErrInvalidInput)
		}
		return item.PricePerM2EUR.InexactFloat64(), nil
	case "days_on_market":
		if item.DaysOnMarket == nil {
			return 0, fmt.Errorf("%w: missing days_on_market cursor value", ErrInvalidInput)
		}
		return float64(*item.DaysOnMarket), nil
	default:
		return 0, fmt.Errorf("%w: unsupported sort", ErrInvalidInput)
	}
}

func listingZoneID(listing *models.Listing) (uuid.UUID, bool) {
	if listing.ZoneID == nil || !listing.ZoneID.Valid {
		return uuid.Nil, false
	}

	zoneID, err := uuidFromPG(*listing.ZoneID)
	if err != nil {
		return uuid.Nil, false
	}

	return zoneID, true
}
