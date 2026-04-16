package grpcutil

import (
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/backoff"
)

// CircuitBreaker tracks consecutive failures and opens after a threshold.
type CircuitBreaker struct {
	mu               sync.Mutex
	consecutiveFails int
	threshold        int
}

// NewCircuitBreaker returns a breaker that opens after threshold consecutive failures.
func NewCircuitBreaker(threshold int) *CircuitBreaker {
	return &CircuitBreaker{threshold: threshold}
}

// RecordSuccess resets the failure counter.
func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	cb.consecutiveFails = 0
	cb.mu.Unlock()
}

// RecordFailure increments the failure counter and returns true if the breaker is open.
func (cb *CircuitBreaker) RecordFailure() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.consecutiveFails++
	return cb.consecutiveFails >= cb.threshold
}

// IsOpen returns whether the circuit breaker is open.
func (cb *CircuitBreaker) IsOpen() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	return cb.consecutiveFails >= cb.threshold
}

// Dial creates a gRPC client connection with exponential backoff retry.
func Dial(target string, opts ...grpc.DialOption) (*grpc.ClientConn, error) {
	bc := backoff.DefaultConfig
	bc.MaxDelay = 30 * time.Second

	defaultOpts := []grpc.DialOption{
		grpc.WithConnectParams(grpc.ConnectParams{
			Backoff: bc,
		}),
	}

	allOpts := append(defaultOpts, opts...)
	return grpc.NewClient(target, allOpts...)
}
