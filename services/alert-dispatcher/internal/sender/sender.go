package sender

import (
	"context"
	"errors"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/model"
)

type Sender interface {
	Send(ctx context.Context, event model.NotificationEvent, user *model.UserChannelProfile) (model.DeliveryResult, error)
}

type SenderFault struct {
	Err error
}

func (e SenderFault) Error() string {
	if e.Err == nil {
		return "sender fault"
	}
	return e.Err.Error()
}

func (e SenderFault) Unwrap() error {
	return e.Err
}

var RetryDelays = []time.Duration{time.Second, 4 * time.Second, 16 * time.Second}

type historyIDKey struct{}

func WithHistoryID(ctx context.Context, historyID string) context.Context {
	return context.WithValue(ctx, historyIDKey{}, historyID)
}

func HistoryIDFromContext(ctx context.Context) string {
	value, _ := ctx.Value(historyIDKey{}).(string)
	return value
}

func Permanent(err error) error {
	if err == nil {
		return nil
	}
	return SenderFault{Err: err}
}

func IsPermanent(err error) bool {
	var fault SenderFault
	return errors.As(err, &fault)
}

func withRetry(
	ctx context.Context,
	maxAttempts int,
	delays []time.Duration,
	fn func() (model.DeliveryResult, error),
) (model.DeliveryResult, error) {
	if maxAttempts <= 0 {
		maxAttempts = 1
	}

	var (
		lastResult model.DeliveryResult
		lastErr    error
	)

	for attempt := 1; attempt <= maxAttempts; attempt++ {
		if ctx.Err() != nil {
			lastResult.AttemptCount = attempt
			return lastResult, ctx.Err()
		}

		result, err := fn()
		if result.AttemptCount <= 0 {
			result.AttemptCount = attempt
		}
		lastResult = result
		lastErr = err

		if err == nil || IsPermanent(err) || attempt == maxAttempts {
			if err != nil && lastResult.ErrorDetail == "" {
				lastResult.ErrorDetail = err.Error()
			}
			return lastResult, err
		}

		delayIdx := attempt - 1
		if delayIdx >= len(delays) {
			delayIdx = len(delays) - 1
		}
		if delayIdx < 0 {
			continue
		}

		timer := time.NewTimer(delays[delayIdx])
		select {
		case <-ctx.Done():
			timer.Stop()
			lastResult.AttemptCount = attempt
			return lastResult, ctx.Err()
		case <-timer.C:
		}
	}

	if lastErr != nil && lastResult.ErrorDetail == "" {
		lastResult.ErrorDetail = lastErr.Error()
	}
	return lastResult, lastErr
}
