package sender

import (
	"context"
	"errors"
	"testing"

	"github.com/estategap/services/alert-dispatcher/internal/model"
)

type pushClientStub struct {
	calls int
	err   error
}

func (c *pushClientStub) Send(_ context.Context, _ PushMessage) error {
	c.calls++
	return c.err
}

type pushRepoStub struct {
	cleared int
	lastID  string
}

func (r *pushRepoStub) ClearPushToken(_ context.Context, userID string) error {
	r.cleared++
	r.lastID = userID
	return nil
}

func TestPushSenderRequiresToken(t *testing.T) {
	t.Parallel()

	sender := NewPushSender(&pushClientStub{}, &pushRepoStub{}, "https://app.estategap.test")
	result, err := sender.Send(context.Background(), model.NotificationEvent{}, &model.UserChannelProfile{})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if result.Success {
		t.Fatalf("Send() success = true, want false")
	}
}

func TestPushSenderClearsExpiredTokenWithoutRetry(t *testing.T) {
	t.Parallel()

	token := "token-1"
	client := &pushClientStub{err: ErrPushTokenNotRegistered}
	repo := &pushRepoStub{}
	sender := NewPushSender(client, repo, "https://app.estategap.test")
	result, err := sender.Send(context.Background(), model.NotificationEvent{}, &model.UserChannelProfile{
		UserID:    "user-7",
		PushToken: &token,
	})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if result.Success {
		t.Fatalf("Send() success = true, want false")
	}
	if client.calls != 1 {
		t.Fatalf("calls = %d, want 1", client.calls)
	}
	if repo.cleared != 1 || repo.lastID != "user-7" {
		t.Fatalf("clear token calls = %d user = %q", repo.cleared, repo.lastID)
	}
}

func TestPushSenderReturnsSuccess(t *testing.T) {
	t.Parallel()

	token := "token-1"
	client := &pushClientStub{}
	sender := NewPushSender(client, &pushRepoStub{}, "https://app.estategap.test")
	result, err := sender.Send(context.Background(), model.NotificationEvent{}, &model.UserChannelProfile{
		PushToken: &token,
	})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if !result.Success {
		t.Fatalf("Send() success = false")
	}
}

func TestPushSenderRetriesTransientError(t *testing.T) {
	t.Parallel()

	token := "token-1"
	client := &pushClientStub{err: errors.New("temporary")}
	sender := NewPushSender(client, &pushRepoStub{}, "https://app.estategap.test")
	_, err := sender.Send(context.Background(), model.NotificationEvent{}, &model.UserChannelProfile{
		PushToken: &token,
	})
	if err == nil {
		t.Fatalf("expected retryable error")
	}
	if client.calls != 4 {
		t.Fatalf("calls = %d, want 4", client.calls)
	}
}
