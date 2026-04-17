package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Repo struct {
	primary *pgxpool.Pool
	replica *pgxpool.Pool
}

func New(primary, replica *pgxpool.Pool) *Repo {
	return &Repo{
		primary: primary,
		replica: replica,
	}
}

func (r *Repo) LoadActiveRules(ctx context.Context) ([]model.CachedRule, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT
			ar.id,
			ar.user_id,
			ar.name,
			COALESCE(MIN(z.country_code), '') AS country_code,
			to_json(ar.zone_ids),
			ar.category,
			ar.filter,
			ar.channels,
			COALESCE(ar.frequency, 'instant') AS frequency
		FROM alert_rules ar
		LEFT JOIN LATERAL unnest(ar.zone_ids) AS zone_ref(zone_id) ON TRUE
		LEFT JOIN zones z ON z.id = zone_ref.zone_id
		WHERE ar.is_active = TRUE
		GROUP BY ar.id, ar.user_id, ar.name, ar.zone_ids, ar.category, ar.filter, ar.channels, ar.frequency
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	rules := make([]model.CachedRule, 0)
	for rows.Next() {
		var (
			rule        model.CachedRule
			filterRaw   []byte
			channelsRaw []byte
			zoneIDsRaw  []byte
		)

		if err := rows.Scan(
			&rule.ID,
			&rule.UserID,
			&rule.Name,
			&rule.CountryCode,
			&zoneIDsRaw,
			&rule.Category,
			&filterRaw,
			&channelsRaw,
			&rule.Frequency,
		); err != nil {
			return nil, err
		}

		rule.CountryCode = strings.ToUpper(strings.TrimSpace(rule.CountryCode))
		rule.Category = strings.ToLower(strings.TrimSpace(rule.Category))
		rule.Frequency = model.NormalizeFrequency(rule.Frequency)

		if len(filterRaw) != 0 {
			if err := json.Unmarshal(filterRaw, &rule.Filter); err != nil {
				return nil, fmt.Errorf("unmarshal filter for rule %s: %w", rule.ID, err)
			}
		}
		if len(zoneIDsRaw) != 0 {
			if err := json.Unmarshal(zoneIDsRaw, &rule.ZoneIDs); err != nil {
				return nil, fmt.Errorf("unmarshal zone IDs for rule %s: %w", rule.ID, err)
			}
		}
		if len(channelsRaw) != 0 {
			if err := json.Unmarshal(channelsRaw, &rule.Channels); err != nil {
				return nil, fmt.Errorf("unmarshal channels for rule %s: %w", rule.ID, err)
			}
			for idx := range rule.Channels {
				rule.Channels[idx].Type = strings.ToLower(strings.TrimSpace(rule.Channels[idx].Type))
			}
		}

		rules = append(rules, rule)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	return rules, nil
}

func (r *Repo) LoadZoneGeometries(ctx context.Context, zoneIDs []string) (map[string]model.ZoneGeometry, error) {
	if len(zoneIDs) == 0 {
		return map[string]model.ZoneGeometry{}, nil
	}

	rows, err := r.replica.Query(ctx, `
		SELECT
			id,
			country_code,
			COALESCE(ST_YMin(bbox), ST_YMin(ST_Envelope(geometry)))::double precision AS bbox_min_lat,
			COALESCE(ST_YMax(bbox), ST_YMax(ST_Envelope(geometry)))::double precision AS bbox_max_lat,
			COALESCE(ST_XMin(bbox), ST_XMin(ST_Envelope(geometry)))::double precision AS bbox_min_lon,
			COALESCE(ST_XMax(bbox), ST_XMax(ST_Envelope(geometry)))::double precision AS bbox_max_lon
		FROM zones
		WHERE id = ANY($1::uuid[])
		  AND (bbox IS NOT NULL OR geometry IS NOT NULL)
	`, zoneIDs)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	zones := make(map[string]model.ZoneGeometry, len(zoneIDs))
	for rows.Next() {
		var zone model.ZoneGeometry
		if err := rows.Scan(
			&zone.ID,
			&zone.CountryCode,
			&zone.BBoxMinLat,
			&zone.BBoxMaxLat,
			&zone.BBoxMinLon,
			&zone.BBoxMaxLon,
		); err != nil {
			return nil, err
		}
		zone.CountryCode = strings.ToUpper(strings.TrimSpace(zone.CountryCode))
		zones[zone.ID] = zone
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	return zones, nil
}

func (r *Repo) FetchListingSummaries(ctx context.Context, listingIDs []string) (map[string]model.ListingSummary, error) {
	if len(listingIDs) == 0 {
		return map[string]model.ListingSummary{}, nil
	}

	rows, err := r.replica.Query(ctx, `
		SELECT
			id,
			COALESCE(address, neighborhood, district, city, source || ' ' || source_id) AS title,
			COALESCE(asking_price_eur, 0)::double precision AS price_eur,
			COALESCE(built_area_m2, usable_area_m2, plot_area_m2, 0)::double precision AS area_m2,
			bedrooms::integer,
			COALESCE(city, district, region, country) AS city,
			country,
			COALESCE(deal_score, 0)::double precision AS deal_score,
			COALESCE(deal_tier, 0)::integer AS deal_tier
		FROM listings
		WHERE id = ANY($1::uuid[])
		  AND status = 'active'
	`, listingIDs)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	summaries := make(map[string]model.ListingSummary, len(listingIDs))
	for rows.Next() {
		var (
			listingID string
			summary   model.ListingSummary
		)
		if err := rows.Scan(
			&listingID,
			&summary.Title,
			&summary.PriceEUR,
			&summary.AreaM2,
			&summary.Bedrooms,
			&summary.City,
			&summary.CountryCode,
			&summary.DealScore,
			&summary.DealTier,
		); err != nil {
			return nil, err
		}
		summaries[listingID] = summary
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	return summaries, nil
}
