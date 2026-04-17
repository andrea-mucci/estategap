package grpc

import (
	"sync/atomic"
	"time"
)

const (
	circuitStateClosed int32 = iota
	circuitStateOpen
	circuitStateHalfOpen
)

type CircuitBreaker struct {
	state           int32
	failures        int32
	lastFailureUnix int64

	Threshold    int
	WindowSecs   int64
	CooldownSecs int64

	nowFunc func() int64
}

func NewCircuitBreaker(threshold int, windowSecs, cooldownSecs int64) *CircuitBreaker {
	return &CircuitBreaker{
		Threshold:    threshold,
		WindowSecs:   windowSecs,
		CooldownSecs: cooldownSecs,
		nowFunc: func() int64 {
			return time.Now().Unix()
		},
	}
}

func (cb *CircuitBreaker) Allow() bool {
	now := cb.nowUnix()

	switch atomic.LoadInt32(&cb.state) {
	case circuitStateClosed:
		return true
	case circuitStateOpen:
		lastFailure := atomic.LoadInt64(&cb.lastFailureUnix)
		if now-lastFailure < cb.CooldownSecs {
			return false
		}
		return atomic.CompareAndSwapInt32(&cb.state, circuitStateOpen, circuitStateHalfOpen)
	case circuitStateHalfOpen:
		return false
	default:
		return true
	}
}

func (cb *CircuitBreaker) RecordSuccess() {
	atomic.StoreInt32(&cb.failures, 0)
	atomic.StoreInt32(&cb.state, circuitStateClosed)
}

func (cb *CircuitBreaker) RecordFailure() {
	now := cb.nowUnix()
	lastFailure := atomic.LoadInt64(&cb.lastFailureUnix)
	atomic.StoreInt64(&cb.lastFailureUnix, now)

	switch atomic.LoadInt32(&cb.state) {
	case circuitStateHalfOpen:
		atomic.StoreInt32(&cb.failures, int32(cb.Threshold))
		atomic.StoreInt32(&cb.state, circuitStateOpen)
		return
	case circuitStateOpen:
		return
	}

	if lastFailure == 0 || now-lastFailure > cb.WindowSecs {
		atomic.StoreInt32(&cb.failures, 1)
	} else {
		atomic.AddInt32(&cb.failures, 1)
	}

	if int(atomic.LoadInt32(&cb.failures)) >= cb.Threshold {
		atomic.StoreInt32(&cb.state, circuitStateOpen)
	}
}

func (cb *CircuitBreaker) nowUnix() int64 {
	if cb != nil && cb.nowFunc != nil {
		return cb.nowFunc()
	}
	return time.Now().Unix()
}
