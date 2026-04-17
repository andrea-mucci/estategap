package scheduler

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/estategap/services/scrape-orchestrator/internal/db"
	"github.com/estategap/services/scrape-orchestrator/internal/job"
)

func TestSchedulerTickPublishesJobs(t *testing.T) {
	t.Parallel()

	store := &stubStore{
		portals: []db.Portal{
			{
				Name:            "immobiliare",
				Country:         "IT",
				ScrapeFrequency: 20 * time.Millisecond,
				SearchURLs:      []string{"https://example.com/search"},
			},
		},
	}
	publisher := &stubPublisher{}
	scheduler := New(time.Hour)
	scheduler.publishNow = publisher.Publish
	scheduler.saveJobFn = func(context.Context, *job.ScrapeJob) error { return nil }

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	if err := scheduler.Start(ctx, store, nil, nil); err != nil {
		t.Fatalf("Start() error = %v", err)
	}
	defer scheduler.Stop()

	deadline := time.After(200 * time.Millisecond)
	for {
		if publisher.Count() > 0 {
			return
		}
		select {
		case <-deadline:
			t.Fatal("expected scheduled publish to occur")
		default:
			time.Sleep(10 * time.Millisecond)
		}
	}
}

func TestSchedulerReloadAddsAndRemovesTickers(t *testing.T) {
	t.Parallel()

	store := &stubStore{
		portals: []db.Portal{
			{
				Name:            "immobiliare",
				Country:         "IT",
				ScrapeFrequency: time.Second,
				SearchURLs:      []string{"https://example.com/a"},
			},
		},
	}
	scheduler := New(time.Hour)
	scheduler.publishNow = func(context.Context, string, string, []byte) error { return nil }
	scheduler.saveJobFn = func(context.Context, *job.ScrapeJob) error { return nil }

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	if err := scheduler.Start(ctx, store, nil, nil); err != nil {
		t.Fatalf("Start() error = %v", err)
	}
	defer scheduler.Stop()

	if got := scheduler.ActiveTickers(); got != 1 {
		t.Fatalf("ActiveTickers() = %d, want 1", got)
	}

	store.SetPortals([]db.Portal{
		{
			Name:            "idealista",
			Country:         "ES",
			ScrapeFrequency: time.Second,
			SearchURLs:      []string{"https://example.com/b"},
		},
	})
	if err := scheduler.Reload(ctx, store); err != nil {
		t.Fatalf("Reload() error = %v", err)
	}
	if got := scheduler.ActiveTickers(); got != 1 {
		t.Fatalf("ActiveTickers() after reload = %d, want 1", got)
	}
}

func TestParseScheduleOverrideSupportsCronStep(t *testing.T) {
	t.Parallel()

	override, err := ParseScheduleOverride("*/30 * * * * *")
	if err != nil {
		t.Fatalf("ParseScheduleOverride() error = %v", err)
	}
	if override != 30*time.Second {
		t.Fatalf("ParseScheduleOverride() = %s, want 30s", override)
	}
}

func TestSchedulerAppliesFrequencyOverride(t *testing.T) {
	t.Parallel()

	store := &stubStore{
		portals: []db.Portal{
			{
				Name:            "idealista",
				Country:         "ES",
				ScrapeFrequency: 5 * time.Minute,
				SearchURLs:      []string{"https://example.com/search"},
			},
		},
	}
	scheduler := New(time.Hour)
	scheduler.publishNow = func(context.Context, string, string, []byte) error { return nil }
	scheduler.saveJobFn = func(context.Context, *job.ScrapeJob) error { return nil }
	scheduler.SetFrequencyOverride(30 * time.Second)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	if err := scheduler.Start(ctx, store, nil, nil); err != nil {
		t.Fatalf("Start() error = %v", err)
	}
	defer scheduler.Stop()

	ticker := scheduler.tickers["idealista"]
	if ticker == nil {
		t.Fatal("expected ticker for idealista")
	}
	if ticker.portal.ScrapeFrequency != 30*time.Second {
		t.Fatalf("ticker frequency = %s, want 30s", ticker.portal.ScrapeFrequency)
	}
}

type stubStore struct {
	mu      sync.Mutex
	portals []db.Portal
}

func (s *stubStore) QueryPortals(context.Context) ([]db.Portal, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]db.Portal(nil), s.portals...), nil
}

func (s *stubStore) Ping(context.Context) error { return nil }

func (s *stubStore) SetPortals(portals []db.Portal) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.portals = append([]db.Portal(nil), portals...)
}

type stubPublisher struct {
	mu       sync.Mutex
	keys     []string
}

func (s *stubPublisher) Publish(_ context.Context, _ string, key string, _ []byte) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.keys = append(s.keys, key)
	return nil
}

func (s *stubPublisher) Count() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.keys)
}
