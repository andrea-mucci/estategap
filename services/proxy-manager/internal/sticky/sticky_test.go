package sticky

import (
	"context"
	"testing"
	"time"
)

func TestStickyGetRenewsTTL(t *testing.T) {
	t.Parallel()

	store := New(nil, 80*time.Millisecond)
	ctx := context.Background()

	if err := store.Set(ctx, "session-1", "proxy-1", 0); err != nil {
		t.Fatalf("Set() error = %v", err)
	}

	time.Sleep(50 * time.Millisecond)
	proxyID, found := store.Get(ctx, "session-1")
	if !found {
		t.Fatal("expected sticky session to exist")
	}
	if proxyID != "proxy-1" {
		t.Fatalf("Get() proxyID = %q, want %q", proxyID, "proxy-1")
	}

	time.Sleep(50 * time.Millisecond)
	if _, found := store.Get(ctx, "session-1"); !found {
		t.Fatal("expected TTL renewal to keep sticky session alive")
	}
}
