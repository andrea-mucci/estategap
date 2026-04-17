package pool

import (
	"context"
	"testing"
	"time"

	"github.com/estategap/services/proxy-manager/internal/blacklist"
	"github.com/estategap/services/proxy-manager/internal/sticky"
)

func TestProxyPoolSelectHealthyProxy(t *testing.T) {
	t.Parallel()

	pool := New(0.5)
	first := newProxy("IT", "brightdata", "10.0.0.1:8000")
	second := newProxy("IT", "brightdata", "10.0.0.2:8000")
	for i := 0; i < 100; i++ {
		first.Health.Record(false)
		second.Health.Record(true)
	}
	pool.LoadForTest("IT", first, second)

	selected, err := pool.Select(context.Background(), "IT", nil, blacklist.New(nil), "", sticky.New(nil, time.Minute))
	if err != nil {
		t.Fatalf("Select() error = %v", err)
	}
	if selected.ID != second.ID {
		t.Fatalf("Select() returned proxy %q, want %q", selected.ID, second.ID)
	}
}

func TestProxyPoolAllBlacklisted(t *testing.T) {
	t.Parallel()

	pool := New(0.5)
	proxy := newProxy("IT", "brightdata", "10.0.0.1:8000")
	pool.LoadForTest("IT", proxy)

	bl := blacklist.New(nil)
	if err := bl.Blacklist(context.Background(), proxy.Host(), time.Minute); err != nil {
		t.Fatalf("Blacklist() error = %v", err)
	}

	if _, err := pool.Select(context.Background(), "IT", nil, bl, "", sticky.New(nil, time.Minute)); err == nil {
		t.Fatal("expected selection to fail when all proxies are blacklisted")
	}
}

func TestProxyPoolStickyReturnsSameProxy(t *testing.T) {
	t.Parallel()

	pool := New(0.5)
	first := newProxy("IT", "brightdata", "10.0.0.1:8000")
	second := newProxy("IT", "brightdata", "10.0.0.2:8000")
	pool.LoadForTest("IT", first, second)

	stickyStore := sticky.New(nil, time.Minute)
	firstPick, err := pool.Select(context.Background(), "IT", nil, blacklist.New(nil), "session-1", stickyStore)
	if err != nil {
		t.Fatalf("Select() error = %v", err)
	}
	secondPick, err := pool.Select(context.Background(), "IT", nil, blacklist.New(nil), "session-1", stickyStore)
	if err != nil {
		t.Fatalf("Select() error = %v", err)
	}

	if secondPick.ID != firstPick.ID {
		t.Fatalf("sticky Select() returned %q, want %q", secondPick.ID, firstPick.ID)
	}
}

func newProxy(country, providerName, endpoint string) *Proxy {
	return &Proxy{
		ID:       endpoint,
		Country:  country,
		Provider: providerName,
		Endpoint: endpoint,
		Health:   &HealthWindow{},
	}
}
