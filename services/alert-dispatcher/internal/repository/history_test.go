package repository

import (
	"context"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgconn"
)

type historyExecStub struct {
	tag      pgconn.CommandTag
	err      error
	calls    int
	lastSQL  string
	lastArgs []any
}

func (s *historyExecStub) Exec(_ context.Context, sql string, arguments ...any) (pgconn.CommandTag, error) {
	s.calls++
	s.lastSQL = sql
	s.lastArgs = arguments
	return s.tag, s.err
}

func TestHistoryInsertDuplicateEventIsNoOp(t *testing.T) {
	t.Parallel()

	exec := &historyExecStub{tag: pgconn.NewCommandTag("INSERT 0 0")}
	repo := NewHistoryRepoWithClients(exec, exec)

	err := repo.Insert(context.Background(), "history-1", "event-1", "rule-1", "listing-1", "email")
	if err != ErrDuplicateEvent {
		t.Fatalf("Insert() error = %v, want %v", err, ErrDuplicateEvent)
	}
	if exec.calls != 1 {
		t.Fatalf("calls = %d, want 1", exec.calls)
	}
}

func TestHistoryUpdateStatusWritesDeliveredFields(t *testing.T) {
	t.Parallel()

	exec := &historyExecStub{tag: pgconn.NewCommandTag("UPDATE 1")}
	repo := NewHistoryRepoWithClients(exec, exec)
	deliveredAt := time.Now().UTC().Truncate(time.Second)

	if err := repo.UpdateStatus(context.Background(), "history-1", "sent", "", 2, &deliveredAt); err != nil {
		t.Fatalf("UpdateStatus() error = %v", err)
	}
	if exec.calls != 1 {
		t.Fatalf("calls = %d, want 1", exec.calls)
	}
	if len(exec.lastArgs) != 5 {
		t.Fatalf("args length = %d, want 5", len(exec.lastArgs))
	}
	if got := exec.lastArgs[1]; got != "sent" {
		t.Fatalf("status arg = %#v, want sent", got)
	}
	if got := exec.lastArgs[3]; got != 2 {
		t.Fatalf("attempt arg = %#v, want 2", got)
	}
}
