package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

type CreatePortfolioPropertyRequest struct {
	Address             string
	Country             string
	PurchasePrice       float64
	PurchaseCurrency    string
	PurchaseDate        time.Time
	MonthlyRentalIncome float64
	AreaM2              *float64
	PropertyType        string
	Notes               *string
}

type UpdatePortfolioPropertyRequest = CreatePortfolioPropertyRequest

type PortfolioProperty struct {
	ID                     string   `json:"id"`
	UserID                 string   `json:"user_id"`
	Address                string   `json:"address"`
	Lat                    *float64 `json:"lat,omitempty"`
	Lng                    *float64 `json:"lng,omitempty"`
	ZoneID                 *string  `json:"zone_id,omitempty"`
	Country                string   `json:"country"`
	PurchasePrice          float64  `json:"purchase_price"`
	PurchaseCurrency       string   `json:"purchase_currency"`
	PurchasePriceEUR       float64  `json:"purchase_price_eur"`
	PurchaseDate           string   `json:"purchase_date"`
	MonthlyRentalIncome    float64  `json:"monthly_rental_income"`
	MonthlyRentalIncomeEUR float64  `json:"monthly_rental_income_eur"`
	AreaM2                 *float64 `json:"area_m2,omitempty"`
	PropertyType           string   `json:"property_type"`
	Notes                  *string  `json:"notes,omitempty"`
	EstimatedValueEUR      *float64 `json:"estimated_value_eur,omitempty"`
	EstimatedAt            *string  `json:"estimated_at,omitempty"`
	CreatedAt              string   `json:"created_at"`
	UpdatedAt              string   `json:"updated_at"`
}

type PortfolioSummary struct {
	TotalProperties        int     `json:"total_properties"`
	TotalInvestedEUR       float64 `json:"total_invested_eur"`
	TotalCurrentValueEUR   float64 `json:"total_current_value_eur"`
	UnrealizedGainLossEUR  float64 `json:"unrealized_gain_loss_eur"`
	UnrealizedGainLossPct  float64 `json:"unrealized_gain_loss_pct"`
	AverageRentalYieldPct  float64 `json:"average_rental_yield_pct"`
	PropertiesWithEstimate int     `json:"properties_with_estimate"`
}

type PortfolioRepo struct {
	primary    *pgxpool.Pool
	replica    *pgxpool.Pool
	httpClient *http.Client
}

func NewPortfolioRepo(primary, replica *pgxpool.Pool) *PortfolioRepo {
	return &PortfolioRepo{
		primary: primary,
		replica: replica,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (r *PortfolioRepo) CreatePortfolioProperty(ctx context.Context, userID uuid.UUID, req CreatePortfolioPropertyRequest) (*PortfolioProperty, error) {
	purchaseRate, err := r.latestRateToEUR(ctx, req.PurchaseCurrency)
	if err != nil {
		return nil, err
	}

	rows, err := r.primary.Query(ctx, `
		INSERT INTO portfolio_properties (
			user_id,
			address,
			country,
			purchase_price,
			purchase_currency,
			purchase_price_eur,
			purchase_date,
			monthly_rental_income,
			monthly_rental_income_eur,
			area_m2,
			property_type,
			notes
		)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NULLIF($12, ''))
		RETURNING
			id,
			user_id,
			address,
			lat,
			lng,
			zone_id,
			country,
			purchase_price::double precision,
			purchase_currency,
			purchase_price_eur::double precision,
			purchase_date,
			monthly_rental_income::double precision,
			monthly_rental_income_eur::double precision,
			area_m2::double precision,
			property_type,
			notes,
			NULL::double precision AS estimated_value_eur,
			NULL::timestamptz AS estimated_at,
			created_at,
			updated_at`,
		pgUUID(userID),
		req.Address,
		strings.ToUpper(req.Country),
		req.PurchasePrice,
		strings.ToUpper(req.PurchaseCurrency),
		req.PurchasePrice*purchaseRate,
		req.PurchaseDate,
		req.MonthlyRentalIncome,
		req.MonthlyRentalIncome*purchaseRate,
		req.AreaM2,
		req.PropertyType,
		stringPtrValue(req.Notes),
	)
	if err != nil {
		return nil, err
	}

	property, err := pgx.CollectOneRow(rows, scanPortfolioProperty)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}

	if propertyID, err := uuid.Parse(property.ID); err == nil {
		go r.enrichPortfolioProperty(propertyID, req.Address, req.Country)
	}

	return &property, nil
}

func (r *PortfolioRepo) ListPortfolioProperties(ctx context.Context, userID uuid.UUID) ([]PortfolioProperty, PortfolioSummary, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT
			p.id,
			p.user_id,
			p.address,
			p.lat,
			p.lng,
			p.zone_id,
			p.country,
			p.purchase_price::double precision,
			p.purchase_currency,
			p.purchase_price_eur::double precision,
			p.purchase_date,
			p.monthly_rental_income::double precision,
			p.monthly_rental_income_eur::double precision,
			p.area_m2::double precision,
			p.property_type,
			p.notes,
			CASE
				WHEN p.area_m2 IS NOT NULL AND zs.median_price_m2_eur IS NOT NULL
					THEN (p.area_m2 * zs.median_price_m2_eur)::double precision
				ELSE NULL
			END AS estimated_value_eur,
			zs.refreshed_at,
			p.created_at,
			p.updated_at
		FROM portfolio_properties p
		LEFT JOIN zone_statistics zs ON zs.zone_id = p.zone_id
		WHERE p.user_id = $1
		ORDER BY p.created_at DESC`,
		pgUUID(userID),
	)
	if err != nil {
		return nil, PortfolioSummary{}, err
	}

	properties, err := pgx.CollectRows(rows, scanPortfolioProperty)
	if err != nil {
		return nil, PortfolioSummary{}, err
	}

	var summary PortfolioSummary
	if err := r.replica.QueryRow(ctx, `
		WITH property_stats AS (
			SELECT
				p.purchase_price_eur::double precision AS purchase_price_eur,
				p.monthly_rental_income_eur::double precision AS monthly_rental_income_eur,
				CASE
					WHEN p.area_m2 IS NOT NULL AND zs.median_price_m2_eur IS NOT NULL
						THEN (p.area_m2 * zs.median_price_m2_eur)::double precision
					ELSE NULL
				END AS estimated_value_eur
			FROM portfolio_properties p
			LEFT JOIN zone_statistics zs ON zs.zone_id = p.zone_id
			WHERE p.user_id = $1
		)
		SELECT
			COUNT(*)::int AS total_properties,
			COALESCE(SUM(purchase_price_eur), 0)::double precision AS total_invested_eur,
			COALESCE(SUM(estimated_value_eur), 0)::double precision AS total_current_value_eur,
			COALESCE(
				AVG(
					CASE
						WHEN purchase_price_eur > 0
							THEN ((monthly_rental_income_eur * 12) / purchase_price_eur) * 100
						ELSE NULL
					END
				),
				0
			)::double precision AS average_rental_yield_pct,
			COUNT(*) FILTER (WHERE estimated_value_eur IS NOT NULL)::int AS properties_with_estimate
		FROM property_stats`,
		pgUUID(userID),
	).Scan(
		&summary.TotalProperties,
		&summary.TotalInvestedEUR,
		&summary.TotalCurrentValueEUR,
		&summary.AverageRentalYieldPct,
		&summary.PropertiesWithEstimate,
	); err != nil {
		return nil, PortfolioSummary{}, err
	}

	summary.UnrealizedGainLossEUR = summary.TotalCurrentValueEUR - summary.TotalInvestedEUR
	if summary.TotalInvestedEUR > 0 {
		summary.UnrealizedGainLossPct = (summary.UnrealizedGainLossEUR / summary.TotalInvestedEUR) * 100
	}

	return properties, summary, nil
}

func (r *PortfolioRepo) UpdatePortfolioProperty(ctx context.Context, userID, propertyID uuid.UUID, req UpdatePortfolioPropertyRequest) (*PortfolioProperty, error) {
	purchaseRate, err := r.latestRateToEUR(ctx, req.PurchaseCurrency)
	if err != nil {
		return nil, err
	}

	rows, err := r.primary.Query(ctx, `
		UPDATE portfolio_properties
		SET
			address = $3,
			country = $4,
			purchase_price = $5,
			purchase_currency = $6,
			purchase_price_eur = $7,
			purchase_date = $8,
			monthly_rental_income = $9,
			monthly_rental_income_eur = $10,
			area_m2 = $11,
			property_type = $12,
			notes = NULLIF($13, '')
		WHERE id = $1
			AND user_id = $2
		RETURNING
			id,
			user_id,
			address,
			lat,
			lng,
			zone_id,
			country,
			purchase_price::double precision,
			purchase_currency,
			purchase_price_eur::double precision,
			purchase_date,
			monthly_rental_income::double precision,
			monthly_rental_income_eur::double precision,
			area_m2::double precision,
			property_type,
			notes,
			NULL::double precision AS estimated_value_eur,
			NULL::timestamptz AS estimated_at,
			created_at,
			updated_at`,
		pgUUID(propertyID),
		pgUUID(userID),
		req.Address,
		strings.ToUpper(req.Country),
		req.PurchasePrice,
		strings.ToUpper(req.PurchaseCurrency),
		req.PurchasePrice*purchaseRate,
		req.PurchaseDate,
		req.MonthlyRentalIncome,
		req.MonthlyRentalIncome*purchaseRate,
		req.AreaM2,
		req.PropertyType,
		stringPtrValue(req.Notes),
	)
	if err != nil {
		return nil, err
	}

	property, err := pgx.CollectOneRow(rows, scanPortfolioProperty)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, r.portfolioMutationError(ctx, propertyID, userID)
		}
		return nil, err
	}

	if parsedID, err := uuid.Parse(property.ID); err == nil {
		go r.enrichPortfolioProperty(parsedID, req.Address, req.Country)
	}

	return &property, nil
}

func (r *PortfolioRepo) DeletePortfolioProperty(ctx context.Context, userID, propertyID uuid.UUID) error {
	tag, err := r.primary.Exec(ctx, `
		DELETE FROM portfolio_properties
		WHERE id = $1
			AND user_id = $2`,
		pgUUID(propertyID),
		pgUUID(userID),
	)
	if err != nil {
		return err
	}
	if tag.RowsAffected() > 0 {
		return nil
	}

	return r.portfolioMutationError(ctx, propertyID, userID)
}

func (r *PortfolioRepo) latestRateToEUR(ctx context.Context, currency string) (float64, error) {
	normalized := strings.ToUpper(strings.TrimSpace(currency))
	if normalized == "" {
		return 0, fmt.Errorf("%w: purchase currency is required", ErrInvalidInput)
	}
	if normalized == "EUR" {
		return 1, nil
	}

	var rate float64
	err := r.replica.QueryRow(ctx, `
		SELECT rate_to_eur::double precision
		FROM exchange_rates
		WHERE currency = $1
		ORDER BY date DESC
		LIMIT 1`,
		normalized,
	).Scan(&rate)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return 0, fmt.Errorf("%w: unsupported currency", ErrInvalidInput)
		}
		return 0, err
	}
	if rate <= 0 {
		return 0, fmt.Errorf("%w: invalid exchange rate", ErrInvalidInput)
	}

	return rate, nil
}

func (r *PortfolioRepo) portfolioMutationError(ctx context.Context, propertyID, userID uuid.UUID) error {
	var ownerID pgtype.UUID
	err := r.replica.QueryRow(ctx, `
		SELECT user_id
		FROM portfolio_properties
		WHERE id = $1`,
		pgUUID(propertyID),
	).Scan(&ownerID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return ErrNotFound
		}
		return err
	}

	if ownerID.Valid && uuid.UUID(ownerID.Bytes) != userID {
		return ErrForbidden
	}

	return ErrNotFound
}

func (r *PortfolioRepo) enrichPortfolioProperty(propertyID uuid.UUID, address, country string) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	lat, lng, err := r.geocodeAddress(ctx, address, country)
	if err != nil {
		return
	}

	var zoneID *uuid.UUID
	row := r.primary.QueryRow(ctx, `
		SELECT id
		FROM zones
		WHERE country_code = $1
			AND ST_Contains(geometry, ST_SetSRID(ST_Point($2, $3), 4326))
		ORDER BY level DESC
		LIMIT 1`,
		strings.ToUpper(strings.TrimSpace(country)),
		lng,
		lat,
	)
	var rawZoneID pgtype.UUID
	if err := row.Scan(&rawZoneID); err == nil && rawZoneID.Valid {
		value := uuid.UUID(rawZoneID.Bytes)
		zoneID = &value
	}

	_, _ = r.primary.Exec(ctx, `
		UPDATE portfolio_properties
		SET lat = $2,
			lng = $3,
			zone_id = $4
		WHERE id = $1`,
		pgUUID(propertyID),
		lat,
		lng,
		uuidToAny(zoneID),
	)
}

func (r *PortfolioRepo) geocodeAddress(ctx context.Context, address, country string) (float64, float64, error) {
	query := url.Values{}
	query.Set("q", strings.TrimSpace(address))
	query.Set("countrycodes", strings.ToLower(strings.TrimSpace(country)))
	query.Set("format", "jsonv2")
	query.Set("limit", "1")

	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodGet,
		"https://nominatim.openstreetmap.org/search?"+query.Encode(),
		nil,
	)
	if err != nil {
		return 0, 0, err
	}
	req.Header.Set("User-Agent", "EstateGap API Gateway/1.0")

	resp, err := r.httpClient.Do(req)
	if err != nil {
		return 0, 0, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return 0, 0, fmt.Errorf("geocoder returned status %d", resp.StatusCode)
	}

	var payload []struct {
		Lat string `json:"lat"`
		Lon string `json:"lon"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return 0, 0, err
	}
	if len(payload) == 0 {
		return 0, 0, ErrNotFound
	}

	lat, err := strconv.ParseFloat(strings.TrimSpace(payload[0].Lat), 64)
	if err != nil {
		return 0, 0, err
	}
	lng, err := strconv.ParseFloat(strings.TrimSpace(payload[0].Lon), 64)
	if err != nil {
		return 0, 0, err
	}

	return lat, lng, nil
}

func scanPortfolioProperty(row pgx.CollectableRow) (PortfolioProperty, error) {
	var (
		item              PortfolioProperty
		rawID             pgtype.UUID
		rawUserID         pgtype.UUID
		rawZoneID         pgtype.UUID
		lat               sql.NullFloat64
		lng               sql.NullFloat64
		areaM2            sql.NullFloat64
		notes             sql.NullString
		estimatedValueEUR sql.NullFloat64
		estimatedAt       sql.NullTime
		purchaseDate      time.Time
		createdAt         time.Time
		updatedAt         time.Time
	)

	err := row.Scan(
		&rawID,
		&rawUserID,
		&item.Address,
		&lat,
		&lng,
		&rawZoneID,
		&item.Country,
		&item.PurchasePrice,
		&item.PurchaseCurrency,
		&item.PurchasePriceEUR,
		&purchaseDate,
		&item.MonthlyRentalIncome,
		&item.MonthlyRentalIncomeEUR,
		&areaM2,
		&item.PropertyType,
		&notes,
		&estimatedValueEUR,
		&estimatedAt,
		&createdAt,
		&updatedAt,
	)
	if err != nil {
		return PortfolioProperty{}, err
	}

	item.ID = uuid.UUID(rawID.Bytes).String()
	item.UserID = uuid.UUID(rawUserID.Bytes).String()
	item.Country = strings.ToUpper(item.Country)
	item.PurchaseCurrency = strings.ToUpper(item.PurchaseCurrency)
	item.PurchaseDate = purchaseDate.Format("2006-01-02")
	item.CreatedAt = createdAt.UTC().Format(time.RFC3339)
	item.UpdatedAt = updatedAt.UTC().Format(time.RFC3339)
	if lat.Valid {
		item.Lat = &lat.Float64
	}
	if lng.Valid {
		item.Lng = &lng.Float64
	}
	if rawZoneID.Valid {
		value := uuid.UUID(rawZoneID.Bytes).String()
		item.ZoneID = &value
	}
	if areaM2.Valid {
		item.AreaM2 = &areaM2.Float64
	}
	if notes.Valid {
		item.Notes = &notes.String
	}
	if estimatedValueEUR.Valid {
		item.EstimatedValueEUR = &estimatedValueEUR.Float64
	}
	if estimatedAt.Valid {
		value := estimatedAt.Time.UTC().Format(time.RFC3339)
		item.EstimatedAt = &value
	}

	return item, nil
}

func stringPtrValue(value *string) string {
	if value == nil {
		return ""
	}

	return strings.TrimSpace(*value)
}

func uuidToAny(value *uuid.UUID) any {
	if value == nil {
		return nil
	}

	return pgUUID(*value)
}
