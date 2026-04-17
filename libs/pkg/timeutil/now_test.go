package timeutil

import (
	"testing"
	"time"
)

func TestNowUsesOverrideWhenPresent(t *testing.T) {
	t.Setenv("NOW_OVERRIDE", "1745000000")

	got := Now()
	want := time.Unix(1745000000, 0).UTC()
	if !got.Equal(want) {
		t.Fatalf("Now() = %v, want %v", got, want)
	}
}

func TestNowFallsBackWhenOverrideInvalid(t *testing.T) {
	t.Setenv("NOW_OVERRIDE", "invalid")

	before := time.Now().UTC().Add(-time.Second)
	got := Now()
	after := time.Now().UTC().Add(time.Second)
	if got.Before(before) || got.After(after) {
		t.Fatalf("Now() = %v, want current time window", got)
	}
}
