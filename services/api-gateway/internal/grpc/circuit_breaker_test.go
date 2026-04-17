package grpc

import (
	"sync/atomic"
	"testing"
)

func TestCircuitBreakerStateMachine(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		run  func(t *testing.T, cb *CircuitBreaker, now *int64)
	}{
		{
			name: "opens after threshold within window and blocks calls",
			run: func(t *testing.T, cb *CircuitBreaker, now *int64) {
				for range 4 {
					cb.RecordFailure()
				}

				if state := atomic.LoadInt32(&cb.state); state != circuitStateClosed {
					t.Fatalf("state after 4 failures = %d, want %d", state, circuitStateClosed)
				}
				cb.RecordFailure()

				if state := atomic.LoadInt32(&cb.state); state != circuitStateOpen {
					t.Fatalf("state after threshold = %d, want %d", state, circuitStateOpen)
				}
				if cb.Allow() {
					t.Fatal("Allow() = true, want false while open")
				}
			},
		},
		{
			name: "half-open probe success closes the breaker",
			run: func(t *testing.T, cb *CircuitBreaker, now *int64) {
				for range 5 {
					cb.RecordFailure()
				}

				*now += cb.CooldownSecs
				if !cb.Allow() {
					t.Fatal("Allow() = false, want true after cooldown")
				}
				if state := atomic.LoadInt32(&cb.state); state != circuitStateHalfOpen {
					t.Fatalf("state after cooldown = %d, want %d", state, circuitStateHalfOpen)
				}

				cb.RecordSuccess()

				if state := atomic.LoadInt32(&cb.state); state != circuitStateClosed {
					t.Fatalf("state after probe success = %d, want %d", state, circuitStateClosed)
				}
				if failures := atomic.LoadInt32(&cb.failures); failures != 0 {
					t.Fatalf("failures after probe success = %d, want 0", failures)
				}
			},
		},
		{
			name: "half-open probe failure reopens the breaker",
			run: func(t *testing.T, cb *CircuitBreaker, now *int64) {
				for range 5 {
					cb.RecordFailure()
				}

				*now += cb.CooldownSecs
				if !cb.Allow() {
					t.Fatal("Allow() = false, want true after cooldown")
				}

				cb.RecordFailure()

				if state := atomic.LoadInt32(&cb.state); state != circuitStateOpen {
					t.Fatalf("state after probe failure = %d, want %d", state, circuitStateOpen)
				}
				if cb.Allow() {
					t.Fatal("Allow() = true, want false after half-open failure")
				}
			},
		},
		{
			name: "failures outside the window do not accumulate",
			run: func(t *testing.T, cb *CircuitBreaker, now *int64) {
				for range 3 {
					cb.RecordFailure()
				}
				*now += cb.WindowSecs + 1
				cb.RecordFailure()

				if failures := atomic.LoadInt32(&cb.failures); failures != 1 {
					t.Fatalf("failures after window reset = %d, want 1", failures)
				}
				if state := atomic.LoadInt32(&cb.state); state != circuitStateClosed {
					t.Fatalf("state after window reset = %d, want %d", state, circuitStateClosed)
				}
			},
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			now := int64(1_000)
			cb := NewCircuitBreaker(5, 30, 30)
			cb.nowFunc = func() int64 { return now }
			tc.run(t, cb, &now)
		})
	}
}
