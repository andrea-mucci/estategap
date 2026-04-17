package testhelpers

import (
	"testing"
	"time"
)

func WaitForCondition(t *testing.T, fn func() bool, timeout, interval time.Duration) {
	t.Helper()

	deadline := time.Now().Add(timeout)
	for {
		if fn() {
			return
		}

		if time.Now().After(deadline) {
			t.Fatalf("condition was not met within %s", timeout)
		}

		time.Sleep(interval)
	}
}
