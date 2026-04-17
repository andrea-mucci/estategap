package blacklist

import (
	"context"
	"testing"
	"time"
)

func TestBlacklistLifecycle(t *testing.T) {
	t.Parallel()

	store := New(nil)
	ctx := context.Background()

	if store.IsBlacklisted(ctx, "10.0.0.1") {
		t.Fatal("unexpected blacklisted proxy")
	}
	if err := store.Blacklist(ctx, "10.0.0.1", 50*time.Millisecond); err != nil {
		t.Fatalf("Blacklist() error = %v", err)
	}
	if !store.IsBlacklisted(ctx, "10.0.0.1") {
		t.Fatal("expected proxy to be blacklisted")
	}

	time.Sleep(70 * time.Millisecond)
	if store.IsBlacklisted(ctx, "10.0.0.1") {
		t.Fatal("expected TTL expiry to clear blacklist entry")
	}
}
