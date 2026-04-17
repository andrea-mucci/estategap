package dispatcher

import (
	"context"
	"crypto/rand"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/metrics"
	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/estategap/services/alert-dispatcher/internal/repository"
	senderpkg "github.com/estategap/services/alert-dispatcher/internal/sender"
)

type Dispatcher struct {
	senders map[string]senderpkg.Sender
	history *repository.HistoryRepo
	users   *repository.UserRepo
	metrics *metrics.Registry
	now     func() time.Time
}

func New(
	senders map[string]senderpkg.Sender,
	historyRepo *repository.HistoryRepo,
	userRepo *repository.UserRepo,
	registry *metrics.Registry,
) *Dispatcher {
	return &Dispatcher{
		senders: senders,
		history: historyRepo,
		users:   userRepo,
		metrics: registry,
		now:     func() time.Time { return time.Now().UTC() },
	}
}

func (d *Dispatcher) Register(channel string, client senderpkg.Sender) {
	if d.senders == nil {
		d.senders = make(map[string]senderpkg.Sender)
	}
	d.senders[strings.ToLower(strings.TrimSpace(channel))] = client
}

func (d *Dispatcher) Dispatch(ctx context.Context, event model.NotificationEvent) (model.DeliveryResult, error) {
	channel := strings.ToLower(strings.TrimSpace(event.Channel))
	client, ok := d.senders[channel]
	if !ok || client == nil {
		result := model.DeliveryResult{
			Success:      false,
			AttemptCount: 1,
			ErrorDetail:  "unknown channel",
		}
		return result, fmt.Errorf("unknown channel: %s", channel)
	}

	user, err := d.users.GetChannelProfile(ctx, event.UserID)
	if err != nil {
		result := model.DeliveryResult{
			Success:      false,
			AttemptCount: 1,
			ErrorDetail:  err.Error(),
		}
		return result, fmt.Errorf("load user channel profile: %w", err)
	}

	historyID := newHistoryID()
	if err := d.history.Insert(ctx, historyID, event.EventID, event.RuleID, derefString(event.ListingID), channel); err != nil {
		if err == repository.ErrDuplicateEvent {
			slog.Info("notification already recorded", "event_id", event.EventID, "channel", channel)
			return model.DeliveryResult{Success: true, AttemptCount: 1}, nil
		}
		result := model.DeliveryResult{
			Success:      false,
			AttemptCount: 1,
			ErrorDetail:  err.Error(),
		}
		return result, fmt.Errorf("insert history: %w", err)
	}

	startedAt := d.now()
	sendCtx := senderpkg.WithHistoryID(ctx, historyID)
	result, sendErr := client.Send(sendCtx, event, user)
	if result.AttemptCount <= 0 {
		result.AttemptCount = 1
	}
	if result.ErrorDetail == "" && sendErr != nil {
		result.ErrorDetail = sendErr.Error()
	}

	status := "sent"
	if sendErr != nil || !result.Success {
		status = "failed"
	}
	if status == "sent" && result.DeliveredAt == nil {
		deliveredAt := d.now()
		result.DeliveredAt = &deliveredAt
	}

	if err := d.history.UpdateStatus(
		ctx,
		historyID,
		status,
		result.ErrorDetail,
		result.AttemptCount,
		result.DeliveredAt,
	); err != nil {
		return result, fmt.Errorf("update history: %w", err)
	}

	if d.metrics != nil {
		d.metrics.ObserveDelivery(channel, status, d.now().Sub(startedAt), result.AttemptCount)
	}

	attrs := []any{
		"event_id", event.EventID,
		"history_id", historyID,
		"channel", channel,
		"user_id", event.UserID,
		"status", status,
		"attempts", result.AttemptCount,
	}
	if result.ErrorDetail != "" {
		attrs = append(attrs, "error_detail", result.ErrorDetail)
	}
	slog.Info("notification dispatched", attrs...)

	if sendErr != nil {
		return result, sendErr
	}

	return result, nil
}

func derefString(value *string) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(*value)
}

func newHistoryID() string {
	var raw [16]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return fmt.Sprintf("fallback-%d", time.Now().UTC().UnixNano())
	}

	raw[6] = (raw[6] & 0x0f) | 0x40
	raw[8] = (raw[8] & 0x3f) | 0x80

	return fmt.Sprintf(
		"%x-%x-%x-%x-%x",
		raw[0:4],
		raw[4:6],
		raw[6:8],
		raw[8:10],
		raw[10:16],
	)
}
