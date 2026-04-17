package repository

import (
	"context"
	"time"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/cache"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type CountrySummary struct {
	Code         string `db:"code"`
	Name         string `db:"name"`
	Currency     string `db:"currency"`
	ListingCount int64  `db:"listing_count"`
	DealCount    int64  `db:"deal_count"`
	PortalCount  int64  `db:"portal_count"`
}

type ReferenceRepo struct {
	replica *pgxpool.Pool
	cache   *cache.Client
}

func NewReferenceRepo(replica *pgxpool.Pool, cacheClient *cache.Client) *ReferenceRepo {
	return &ReferenceRepo{
		replica: replica,
		cache:   cacheClient,
	}
}

func (r *ReferenceRepo) ListCountries(ctx context.Context) ([]CountrySummary, error) {
	return cache.GetOrSet(ctx, r.cache, "cache:countries", 15*time.Minute, func() ([]CountrySummary, error) {
		rows, err := r.replica.Query(ctx, `
			SELECT
				c.code,
				c.name,
				c.currency,
				COALESCE(ls.listing_count, 0)::bigint AS listing_count,
				COALESCE(ls.deal_count, 0)::bigint AS deal_count,
				COALESCE(ps.portal_count, 0)::bigint AS portal_count
			FROM countries c
			LEFT JOIN LATERAL (
				SELECT
					COUNT(*) FILTER (WHERE l.status = 'active') AS listing_count,
					COUNT(*) FILTER (WHERE l.status = 'active' AND l.deal_tier IN (1, 2)) AS deal_count
				FROM listings l
				WHERE l.country = c.code
			) ls ON TRUE
			LEFT JOIN LATERAL (
				SELECT COUNT(*) AS portal_count
				FROM portals p
				WHERE p.country_code = c.code
					AND p.enabled = true
			) ps ON TRUE
			WHERE c.active = true
			ORDER BY c.name ASC`)
		if err != nil {
			return nil, err
		}

		return pgx.CollectRows(rows, pgx.RowToStructByNameLax[CountrySummary])
	})
}

func (r *ReferenceRepo) ListPortals(ctx context.Context) ([]models.Portal, error) {
	return cache.GetOrSet(ctx, r.cache, "cache:portals", 15*time.Minute, func() ([]models.Portal, error) {
		rows, err := r.replica.Query(ctx, `
			SELECT *
			FROM portals
			WHERE enabled = true
			ORDER BY name ASC`)
		if err != nil {
			return nil, err
		}

		return pgx.CollectRows(rows, pgx.RowToStructByNameLax[models.Portal])
	})
}
