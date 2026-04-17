package repository

import (
	"context"
	"sync"
	"time"

	"github.com/estategap/services/api-gateway/internal/cache"
	"github.com/jackc/pgx/v5/pgxpool"
)

type DashboardSummary struct {
	Country         string    `json:"country"`
	TotalListings   int64     `json:"total_listings"`
	NewToday        int64     `json:"new_today"`
	Tier1DealsToday int64     `json:"tier1_deals_today"`
	PriceDrops7D    int64     `json:"price_drops_7d"`
	LastRefreshedAt time.Time `json:"last_refreshed_at"`
}

type DashboardRepo struct {
	replica *pgxpool.Pool
	cache   *cache.Client
}

func NewDashboardRepo(replica *pgxpool.Pool, cacheClient *cache.Client) *DashboardRepo {
	return &DashboardRepo{
		replica: replica,
		cache:   cacheClient,
	}
}

func (r *DashboardRepo) GetDashboardSummary(ctx context.Context, country string) (*DashboardSummary, error) {
	return cache.GetOrSet(ctx, r.cache, "dashboard:summary:"+country, time.Minute, func() (*DashboardSummary, error) {
		summary := &DashboardSummary{
			Country:         country,
			LastRefreshedAt: time.Now().UTC(),
		}

		type querySpec struct {
			query string
			set   func(int64)
		}

		specs := []querySpec{
			{
				query: `
					SELECT COUNT(*)
					FROM listings
					WHERE country = $1
						AND status = 'active'`,
				set: func(value int64) { summary.TotalListings = value },
			},
			{
				query: `
					SELECT COUNT(*)
					FROM listings
					WHERE country = $1
						AND status = 'active'
						AND first_seen_at >= NOW() - INTERVAL '1 day'`,
				set: func(value int64) { summary.NewToday = value },
			},
			{
				query: `
					SELECT COUNT(*)
					FROM listings
					WHERE country = $1
						AND status = 'active'
						AND deal_tier = 1
						AND first_seen_at >= NOW() - INTERVAL '1 day'`,
				set: func(value int64) { summary.Tier1DealsToday = value },
			},
			{
				query: `
					SELECT COUNT(DISTINCT listing_id)
					FROM price_history
					WHERE country = $1
						AND change_type = 'price_change'
						AND old_price_eur IS NOT NULL
						AND new_price_eur IS NOT NULL
						AND new_price_eur < old_price_eur
						AND recorded_at >= NOW() - INTERVAL '7 days'`,
				set: func(value int64) { summary.PriceDrops7D = value },
			},
		}

		ctx, cancel := context.WithCancel(ctx)
		defer cancel()

		var (
			wg    sync.WaitGroup
			errCh = make(chan error, len(specs))
			mu    sync.Mutex
		)

		for _, spec := range specs {
			spec := spec
			wg.Add(1)
			go func() {
				defer wg.Done()

				var value int64
				if err := r.replica.QueryRow(ctx, spec.query, country).Scan(&value); err != nil {
					errCh <- err
					cancel()
					return
				}

				mu.Lock()
				spec.set(value)
				mu.Unlock()
			}()
		}

		wg.Wait()
		select {
		case err := <-errCh:
			return nil, err
		default:
			return summary, nil
		}
	})
}
