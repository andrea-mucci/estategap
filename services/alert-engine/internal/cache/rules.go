package cache

import (
	"context"
	"log/slog"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/model"
)

type RuleRepository interface {
	LoadActiveRules(ctx context.Context) ([]model.CachedRule, error)
	LoadZoneGeometries(ctx context.Context, zoneIDs []string) (map[string]model.ZoneGeometry, error)
}

type RuleCache struct {
	mu        sync.RWMutex
	byCountry map[string][]*model.CachedRule
	byID      map[string]*model.CachedRule
	zones     map[string]model.ZoneGeometry
	metrics   *metrics.Registry
}

func New(registry *metrics.Registry) *RuleCache {
	return &RuleCache{
		byCountry: make(map[string][]*model.CachedRule),
		byID:      make(map[string]*model.CachedRule),
		zones:     make(map[string]model.ZoneGeometry),
		metrics:   registry,
	}
}

func (c *RuleCache) Load(ctx context.Context, repo RuleRepository) error {
	rules, err := repo.LoadActiveRules(ctx)
	if err != nil {
		return err
	}

	zoneSet := make(map[string]struct{})
	for _, rule := range rules {
		for _, zoneID := range rule.ZoneIDs {
			zoneSet[zoneID] = struct{}{}
		}
	}

	zoneIDs := make([]string, 0, len(zoneSet))
	for zoneID := range zoneSet {
		zoneIDs = append(zoneIDs, zoneID)
	}
	sort.Slice(zoneIDs, func(i, j int) bool {
		return zoneIDs[i] < zoneIDs[j]
	})

	zones, err := repo.LoadZoneGeometries(ctx, zoneIDs)
	if err != nil {
		return err
	}

	byCountry := make(map[string][]*model.CachedRule)
	byID := make(map[string]*model.CachedRule, len(rules))
	for i := range rules {
		rule := rules[i]
		countryCode := strings.ToUpper(strings.TrimSpace(rule.CountryCode))
		ptr := &rule
		byCountry[countryCode] = append(byCountry[countryCode], ptr)
		byID[rule.ID] = ptr
	}

	c.mu.Lock()
	c.byCountry = byCountry
	c.byID = byID
	c.zones = zones
	c.mu.Unlock()

	if c.metrics != nil {
		c.metrics.RulesCached.Set(float64(len(rules)))
	}

	return nil
}

func (c *RuleCache) StartRefresh(ctx context.Context, repo RuleRepository, interval time.Duration) {
	if interval <= 0 {
		interval = time.Minute
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := c.Load(ctx, repo); err != nil {
				slog.Warn("rule cache refresh failed", "error", err)
			}
		}
	}
}

func (c *RuleCache) Get(countryCode string) []*model.CachedRule {
	c.mu.RLock()
	defer c.mu.RUnlock()

	rules := c.byCountry[strings.ToUpper(strings.TrimSpace(countryCode))]
	out := make([]*model.CachedRule, len(rules))
	copy(out, rules)
	return out
}

func (c *RuleCache) FindRule(ruleID string) (*model.CachedRule, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	rule, ok := c.byID[ruleID]
	return rule, ok
}

func (c *RuleCache) GetZone(zoneID string) (model.ZoneGeometry, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	zone, ok := c.zones[zoneID]
	return zone, ok
}
