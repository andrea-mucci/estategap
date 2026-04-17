package pool

import (
	"context"
	"errors"
	"fmt"
	"net"
	"strings"
	"sync"

	"github.com/estategap/services/proxy-manager/internal/blacklist"
	"github.com/estategap/services/proxy-manager/internal/config"
	"github.com/estategap/services/proxy-manager/internal/provider"
	"github.com/estategap/services/proxy-manager/internal/redisclient"
	"github.com/estategap/services/proxy-manager/internal/sticky"
	"github.com/google/uuid"
)

type Proxy struct {
	ID       string
	Country  string
	Provider string
	Endpoint string
	Username string
	Password string
	Adapter  provider.ProxyProvider
	Health   *HealthWindow
}

func (p *Proxy) Host() string {
	host, _, err := net.SplitHostPort(p.Endpoint)
	if err != nil {
		return p.Endpoint
	}
	return host
}

type ProxyPool struct {
	mu            sync.RWMutex
	proxies       map[string][]*Proxy
	byID          map[string]*Proxy
	roundRobin    map[string]int
	healthMinimum float64
}

func New(healthMinimum float64) *ProxyPool {
	if healthMinimum <= 0 || healthMinimum > 1 {
		healthMinimum = 0.5
	}

	return &ProxyPool{
		proxies:       make(map[string][]*Proxy),
		byID:          make(map[string]*Proxy),
		roundRobin:    make(map[string]int),
		healthMinimum: healthMinimum,
	}
}

func (p *ProxyPool) LoadFromConfig(cfg *config.Config, registry provider.ProviderRegistry) error {
	proxies := make(map[string][]*Proxy)
	byID := make(map[string]*Proxy)

	for _, country := range cfg.Countries {
		countryCfg, ok := cfg.CountryConfigs[country]
		if !ok {
			return fmt.Errorf("missing proxy config for country %s", country)
		}

		adapter, err := registry.New(countryCfg.Provider)
		if err != nil {
			return err
		}

		for _, endpoint := range countryCfg.Endpoints {
			proxy := &Proxy{
				ID:       uuid.NewString(),
				Country:  country,
				Provider: adapter.Name(),
				Endpoint: strings.TrimSpace(endpoint),
				Username: countryCfg.Username,
				Password: countryCfg.Password,
				Adapter:  adapter,
				Health:   &HealthWindow{},
			}

			proxies[country] = append(proxies[country], proxy)
			byID[proxy.ID] = proxy
		}
	}

	p.mu.Lock()
	defer p.mu.Unlock()
	p.proxies = proxies
	p.byID = byID
	p.roundRobin = make(map[string]int)
	p.healthMinimum = cfg.HealthThreshold

	return nil
}

func (p *ProxyPool) LoadForTest(country string, proxies ...*Proxy) {
	p.mu.Lock()
	defer p.mu.Unlock()

	country = strings.ToUpper(strings.TrimSpace(country))
	p.proxies[country] = append([]*Proxy(nil), proxies...)
	for _, proxy := range proxies {
		p.byID[proxy.ID] = proxy
	}
}

func (p *ProxyPool) Select(ctx context.Context, country string, redisClient *redisclient.Client, bl *blacklist.Blacklist, sessionID string, stickyStore *sticky.Sticky) (*Proxy, error) {
	country = strings.ToUpper(strings.TrimSpace(country))
	if country == "" {
		return nil, errors.New("country is required")
	}

	if sessionID != "" && stickyStore != nil {
		if proxyID, found := stickyStore.Get(ctx, sessionID); found {
			if proxy, ok := p.GetByID(proxyID); ok {
				if bl == nil || !bl.IsBlacklisted(ctx, proxy.Host()) {
					return proxy, nil
				}
			}
		}
	}

	p.mu.RLock()
	candidates := append([]*Proxy(nil), p.proxies[country]...)
	p.mu.RUnlock()
	if len(candidates) == 0 {
		return nil, fmt.Errorf("no proxies configured for country %s", country)
	}

	healthy := make([]*Proxy, 0, len(candidates))
	for _, candidate := range candidates {
		if candidate.Health.Score() >= p.healthMinimum {
			healthy = append(healthy, candidate)
		}
	}
	if len(healthy) == 0 {
		return nil, fmt.Errorf("no healthy proxies available for country %s", country)
	}

	available, err := p.filterBlacklisted(ctx, healthy, redisClient, bl)
	if err != nil {
		return nil, err
	}
	if len(available) == 0 {
		return nil, fmt.Errorf("all healthy proxies are blacklisted for country %s", country)
	}

	p.mu.Lock()
	index := p.roundRobin[country] % len(available)
	selected := available[index]
	p.roundRobin[country] = (p.roundRobin[country] + 1) % len(available)
	p.mu.Unlock()

	if sessionID != "" && stickyStore != nil {
		if err := stickyStore.Set(ctx, sessionID, selected.ID, 0); err != nil {
			return nil, err
		}
	}

	return selected, nil
}

func (p *ProxyPool) GetByID(id string) (*Proxy, bool) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	proxy, ok := p.byID[id]
	return proxy, ok
}

func (p *ProxyPool) Stats(ctx context.Context, bl *blacklist.Blacklist, country, providerName string) (poolSize, healthyCount, blacklistedCount int, err error) {
	p.mu.RLock()
	candidates := append([]*Proxy(nil), p.proxies[strings.ToUpper(strings.TrimSpace(country))]...)
	p.mu.RUnlock()

	var ips []string
	for _, candidate := range candidates {
		if providerName != "" && candidate.Provider != providerName {
			continue
		}
		poolSize++
		if candidate.Health.Score() >= p.healthMinimum {
			healthyCount++
		}
		ips = append(ips, candidate.Host())
	}

	if bl == nil || len(ips) == 0 {
		return poolSize, healthyCount, 0, nil
	}

	blacklisted, err := bl.BatchIsBlacklisted(ctx, ips)
	if err != nil {
		return 0, 0, 0, err
	}
	for _, blocked := range blacklisted {
		if blocked {
			blacklistedCount++
		}
	}

	return poolSize, healthyCount, blacklistedCount, nil
}

func (p *ProxyPool) filterBlacklisted(ctx context.Context, candidates []*Proxy, _ *redisclient.Client, bl *blacklist.Blacklist) ([]*Proxy, error) {
	if bl == nil {
		return candidates, nil
	}

	ips := make([]string, 0, len(candidates))
	for _, candidate := range candidates {
		ip := candidate.Host()
		ips = append(ips, ip)
	}

	blacklisted, err := bl.BatchIsBlacklisted(ctx, ips)
	if err != nil {
		return nil, err
	}

	available := make([]*Proxy, 0, len(candidates))
	for _, candidate := range candidates {
		if blacklisted[candidate.Host()] {
			continue
		}
		available = append(available, candidate)
	}

	return available, nil
}
