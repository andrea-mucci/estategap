package matcher

import (
	"context"
	"log/slog"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/estategap/services/alert-engine/internal/cache"
	"github.com/estategap/services/alert-engine/internal/dedup"
	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Engine struct {
	cache    *cache.RuleCache
	db       *pgxpool.Pool
	dedup    *dedup.Dedup
	poolSize int
	metrics  *metrics.Registry
}

func New(rules *cache.RuleCache, db *pgxpool.Pool, dedupStore *dedup.Dedup, poolSize int, registry *metrics.Registry) *Engine {
	return &Engine{
		cache:    rules,
		db:       db,
		dedup:    dedupStore,
		poolSize: poolSize,
		metrics:  registry,
	}
}

func (e *Engine) Match(ctx context.Context, listing model.ScoredListingEvent) ([]*model.CachedRule, error) {
	start := time.Now()
	defer func() {
		if e.metrics != nil {
			e.metrics.ObserveRuleEval(time.Since(start))
		}
	}()

	rules := e.cache.Get(listing.CountryCode)
	if len(rules) == 0 {
		return nil, nil
	}

	limit := e.poolSize
	if limit <= 0 {
		limit = runtime.GOMAXPROCS(0)
	}

	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	var (
		wg      sync.WaitGroup
		mu      sync.Mutex
		matches []*model.CachedRule
	)

	sem := make(chan struct{}, limit)
	errCh := make(chan error, 1)

	for _, rule := range rules {
		if ctx.Err() != nil {
			break
		}

		rule := rule
		wg.Add(1)
		sem <- struct{}{}
		go func() {
			defer wg.Done()
			defer func() { <-sem }()

			matched, err := e.evaluateRule(ctx, rule, listing)
			if err != nil {
				select {
				case errCh <- err:
					cancel()
				default:
				}
				return
			}
			if !matched {
				return
			}

			mu.Lock()
			matches = append(matches, rule)
			mu.Unlock()
		}()
	}

	wg.Wait()

	select {
	case err := <-errCh:
		return nil, err
	default:
	}

	if e.metrics != nil {
		e.metrics.Matches.Add(float64(len(matches)))
	}

	return matches, nil
}

func (e *Engine) evaluateRule(ctx context.Context, rule *model.CachedRule, listing model.ScoredListingEvent) (bool, error) {
	if rule == nil {
		return false, nil
	}
	if rule.Category != "" && !strings.EqualFold(rule.Category, listing.PropertyType) {
		return false, nil
	}
	if len(rule.ZoneIDs) > 0 {
		inZone, err := InAnyZone(ctx, listing, rule.ZoneIDs, e.cache, e.db)
		if err != nil {
			return false, err
		}
		if !inZone {
			return false, nil
		}
	}
	if !Evaluate(rule.Filter, listing) {
		return false, nil
	}
	if e.dedup == nil {
		return true, nil
	}

	sent, err := e.dedup.IsSent(ctx, rule.UserID, listing.ListingID)
	if err != nil {
		slog.Warn("dedup lookup failed; allowing notification", "rule_id", rule.ID, "listing_id", listing.ListingID, "error", err)
		return true, nil
	}

	return !sent, nil
}
