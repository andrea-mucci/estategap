package dispatcher

import (
	"context"
	"errors"
	"testing"

	"github.com/estategap/services/alert-dispatcher/internal/metrics"
	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/estategap/services/alert-dispatcher/internal/repository"
	senderpkg "github.com/estategap/services/alert-dispatcher/internal/sender"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgtype"
)

type queryRowStub struct {
	scan func(dest ...any) error
}

func (r queryRowStub) Scan(dest ...any) error {
	return r.scan(dest...)
}

type userReaderStub struct {
	row pgx.Row
}

func (r *userReaderStub) QueryRow(_ context.Context, _ string, _ ...any) pgx.Row {
	return r.row
}

type execRecorder struct {
	tags     []pgconn.CommandTag
	errs     []error
	lastArgs []any
	calls    int
}

func (e *execRecorder) Exec(_ context.Context, _ string, arguments ...any) (pgconn.CommandTag, error) {
	e.calls++
	e.lastArgs = arguments
	idx := e.calls - 1
	var tag pgconn.CommandTag
	if idx < len(e.tags) {
		tag = e.tags[idx]
	}
	var err error
	if idx < len(e.errs) {
		err = e.errs[idx]
	}
	return tag, err
}

type senderStub struct {
	result model.DeliveryResult
	err    error
}

func (s *senderStub) Send(_ context.Context, _ model.NotificationEvent, _ *model.UserChannelProfile) (model.DeliveryResult, error) {
	return s.result, s.err
}

func TestDispatcherUnknownChannel(t *testing.T) {
	t.Parallel()

	dispatcher := New(map[string]senderpkg.Sender{}, nil, nil, nil)
	result, err := dispatcher.Dispatch(context.Background(), model.NotificationEvent{Channel: "unknown"})
	if err == nil {
		t.Fatalf("Dispatch() error = nil, want error")
	}
	if result.ErrorDetail != "unknown channel" {
		t.Fatalf("result.ErrorDetail = %q", result.ErrorDetail)
	}
}

func TestDispatcherHandlesProfileLookupError(t *testing.T) {
	t.Parallel()

	reader := &userReaderStub{
		row: queryRowStub{scan: func(_ ...any) error { return errors.New("db down") }},
	}
	writer := &execRecorder{}
	userRepo := repository.NewUserRepoWithClients(writer, reader)
	historyRepo := repository.NewHistoryRepoWithClients(writer, writer)
	dispatcher := New(map[string]senderpkg.Sender{
		model.ChannelEmail: &senderStub{},
	}, historyRepo, userRepo, metrics.New())

	result, err := dispatcher.Dispatch(context.Background(), model.NotificationEvent{
		Channel: model.ChannelEmail,
		UserID:  "user-1",
	})
	if err == nil {
		t.Fatalf("Dispatch() error = nil, want error")
	}
	if result.Success {
		t.Fatalf("Dispatch() success = true, want false")
	}
}

func TestDispatcherUpdatesHistoryOnSuccess(t *testing.T) {
	t.Parallel()

	reader := &userReaderStub{
		row: queryRowStub{scan: func(dest ...any) error {
			*(dest[0].(*string)) = "user-1"
			*(dest[1].(*string)) = "user@example.com"
			*(dest[2].(*string)) = "en"
			*(dest[3].(*pgtype.Int8)) = pgtype.Int8{}
			*(dest[4].(*pgtype.Text)) = pgtype.Text{}
			*(dest[5].(*pgtype.Text)) = pgtype.Text{}
			*(dest[6].(*pgtype.Text)) = pgtype.Text{}
			return nil
		}},
	}
	writer := &execRecorder{
		tags: []pgconn.CommandTag{
			pgconn.NewCommandTag("INSERT 0 1"),
			pgconn.NewCommandTag("UPDATE 1"),
		},
	}
	userRepo := repository.NewUserRepoWithClients(writer, reader)
	historyRepo := repository.NewHistoryRepoWithClients(writer, writer)
	dispatcher := New(map[string]senderpkg.Sender{
		model.ChannelEmail: &senderStub{result: model.DeliveryResult{Success: true}},
	}, historyRepo, userRepo, metrics.New())

	result, err := dispatcher.Dispatch(context.Background(), model.NotificationEvent{
		EventID: "event-1",
		RuleID:  "rule-1",
		UserID:  "user-1",
		Channel: model.ChannelEmail,
	})
	if err != nil {
		t.Fatalf("Dispatch() error = %v", err)
	}
	if !result.Success {
		t.Fatalf("Dispatch() success = false")
	}
	if writer.calls != 2 {
		t.Fatalf("writer calls = %d, want 2", writer.calls)
	}
	if got := writer.lastArgs[1]; got != "sent" {
		t.Fatalf("final status arg = %#v, want sent", got)
	}
}
