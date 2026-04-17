package scheduler

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/estategap/services/scrape-orchestrator/internal/db"
	"github.com/estategap/services/scrape-orchestrator/internal/job"
	"github.com/estategap/services/scrape-orchestrator/internal/redisclient"
	"github.com/google/uuid"
)

type Publisher interface {
	Publish(subject string, payload []byte) error
}

type portalTicker struct {
	portal db.Portal
	ticker *time.Ticker
	cancel context.CancelFunc
}

type Scheduler struct {
	mu                sync.Mutex
	jobTTL            time.Duration
	tickers           map[string]*portalTicker
	frequencyOverride *time.Duration

	store      db.Querier
	publisher  Publisher
	redis      *redisclient.Client
	saveJobFn  func(context.Context, *job.ScrapeJob) error
	publishNow func(string, []byte) error
}

func New(jobTTL time.Duration) *Scheduler {
	return &Scheduler{
		jobTTL:  jobTTL,
		tickers: make(map[string]*portalTicker),
	}
}

func (s *Scheduler) SetFrequencyOverride(override time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.frequencyOverride = &override
}

func ParseScheduleOverride(raw string) (time.Duration, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return 0, fmt.Errorf("TEST_SCHEDULE_OVERRIDE is empty")
	}
	if duration, err := time.ParseDuration(raw); err == nil {
		if duration <= 0 {
			return 0, fmt.Errorf("TEST_SCHEDULE_OVERRIDE must be greater than zero")
		}
		return duration, nil
	}

	fields := strings.Fields(raw)
	switch len(fields) {
	case 6:
		if duration, ok := cronStepDuration(fields[0], time.Second); ok && fields[1] == "*" && fields[2] == "*" && fields[3] == "*" && fields[4] == "*" && fields[5] == "*" {
			return duration, nil
		}
	case 5:
		if duration, ok := cronStepDuration(fields[0], time.Minute); ok && fields[1] == "*" && fields[2] == "*" && fields[3] == "*" && fields[4] == "*" {
			return duration, nil
		}
	}

	return 0, fmt.Errorf("unsupported TEST_SCHEDULE_OVERRIDE format %q", raw)
}

func (s *Scheduler) Start(ctx context.Context, store db.Querier, publisher Publisher, redisClient *redisclient.Client) error {
	s.mu.Lock()
	s.store = store
	s.publisher = publisher
	s.redis = redisClient
	if publisher != nil {
		s.publishNow = publisher.Publish
	}
	if s.saveJobFn == nil {
		s.saveJobFn = func(ctx context.Context, scrapeJob *job.ScrapeJob) error {
			return scrapeJob.Save(ctx, s.redis, s.jobTTL)
		}
	}
	s.mu.Unlock()

	return s.Reload(ctx, store)
}

func (s *Scheduler) PublishNow(ctx context.Context, portal db.Portal, mode string, zoneFilter []string, searchURL string) (string, error) {
	return s.publishJob(ctx, portal, mode, zoneFilter, searchURL)
}

func (s *Scheduler) Reload(ctx context.Context, store db.Querier) error {
	portals, err := store.QueryPortals(ctx)
	if err != nil {
		return err
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	next := make(map[string]db.Portal, len(portals))
	for _, portal := range portals {
		portal = s.applyFrequencyOverride(portal)
		next[portal.Name] = portal
		existing, ok := s.tickers[portal.Name]
		if ok && existing.portal.ScrapeFrequency == portal.ScrapeFrequency {
			existing.portal = portal
			continue
		}
		if portal.ScrapeFrequency <= 0 {
			if ok {
				existing.cancel()
				existing.ticker.Stop()
				delete(s.tickers, portal.Name)
			}
			slog.Warn("skipping portal with non-positive frequency", "portal", portal.Name, "frequency", portal.ScrapeFrequency)
			continue
		}

		if ok {
			existing.cancel()
			existing.ticker.Stop()
		}

		tickerCtx, cancel := context.WithCancel(ctx)
		portalTicker := &portalTicker{
			portal: portal,
			ticker: time.NewTicker(portal.ScrapeFrequency),
			cancel: cancel,
		}
		s.tickers[portal.Name] = portalTicker
		go s.runPortalTicker(tickerCtx, portalTicker)
	}

	for name, existing := range s.tickers {
		if _, ok := next[name]; ok {
			continue
		}
		existing.cancel()
		existing.ticker.Stop()
		delete(s.tickers, name)
	}

	return nil
}

func (s *Scheduler) WatchReload(ctx context.Context, store db.Querier, interval time.Duration) {
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGHUP)
	defer signal.Stop(sigCh)

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-sigCh:
			if err := s.Reload(ctx, store); err != nil {
				slog.Error("scheduler reload failed", "error", err)
			}
		case <-ticker.C:
			if err := s.Reload(ctx, store); err != nil {
				slog.Error("scheduler reload failed", "error", err)
			}
		}
	}
}

func (s *Scheduler) Stop() {
	s.mu.Lock()
	defer s.mu.Unlock()

	for name, portalTicker := range s.tickers {
		portalTicker.cancel()
		portalTicker.ticker.Stop()
		delete(s.tickers, name)
	}
}

func (s *Scheduler) ActiveTickers() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.tickers)
}

func (s *Scheduler) runPortalTicker(ctx context.Context, ticker *portalTicker) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.ticker.C:
			if err := s.publishPortalJobs(ctx, ticker.portal); err != nil {
				slog.Error("scheduled publish failed", "portal", ticker.portal.Name, "error", err)
			}
		}
	}
}

func (s *Scheduler) publishPortalJobs(ctx context.Context, portal db.Portal) error {
	urls := make([]string, 0, len(portal.SearchURLs))
	for _, searchURL := range portal.SearchURLs {
		if trimmed := strings.TrimSpace(searchURL); trimmed != "" {
			urls = append(urls, trimmed)
		}
	}
	if len(urls) == 0 {
		return fmt.Errorf("portal %s has no search URLs", portal.Name)
	}

	for _, searchURL := range urls {
		if _, err := s.publishJob(ctx, portal, "full", nil, searchURL); err != nil {
			return err
		}
	}
	return nil
}

func (s *Scheduler) applyFrequencyOverride(portal db.Portal) db.Portal {
	if s.frequencyOverride == nil {
		return portal
	}
	portal.ScrapeFrequency = *s.frequencyOverride
	return portal
}

func cronStepDuration(field string, unit time.Duration) (time.Duration, bool) {
	if !strings.HasPrefix(field, "*/") {
		return 0, false
	}
	value, err := strconv.Atoi(strings.TrimPrefix(field, "*/"))
	if err != nil || value <= 0 {
		return 0, false
	}
	return time.Duration(value) * unit, true
}

func (s *Scheduler) publishJob(ctx context.Context, portal db.Portal, mode string, zoneFilter []string, searchURL string) (string, error) {
	s.mu.Lock()
	publish := s.publishNow
	saveJobFn := s.saveJobFn
	s.mu.Unlock()

	if publish == nil || saveJobFn == nil {
		return "", fmt.Errorf("scheduler is not initialized")
	}

	scrapeJob := &job.ScrapeJob{
		JobID:      uuid.NewString(),
		Portal:     portal.Name,
		Country:    strings.ToUpper(strings.TrimSpace(portal.Country)),
		Mode:       mode,
		ZoneFilter: zoneFilter,
		SearchURL:  searchURL,
		CreatedAt:  time.Now().UTC(),
	}

	payload, err := scrapeJob.Marshal()
	if err != nil {
		return "", err
	}

	subject := fmt.Sprintf("scraper.commands.%s.%s", scrapeJob.Country, scrapeJob.Portal)
	if err := publish(subject, payload); err != nil {
		return "", err
	}
	if err := saveJobFn(ctx, scrapeJob); err != nil {
		return "", err
	}

	return scrapeJob.JobID, nil
}
