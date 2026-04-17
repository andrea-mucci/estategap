package sender

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/redis/go-redis/v9"
)

type redisStub struct {
	counts map[string]int64
}

func (r *redisStub) Incr(_ context.Context, key string) *redis.IntCmd {
	if r.counts == nil {
		r.counts = make(map[string]int64)
	}
	r.counts[key]++
	cmd := redis.NewIntCmd(context.Background())
	cmd.SetVal(r.counts[key])
	return cmd
}

func (r *redisStub) Expire(_ context.Context, _ string, _ time.Duration) *redis.BoolCmd {
	cmd := redis.NewBoolCmd(context.Background())
	cmd.SetVal(true)
	return cmd
}

func TestComputeWebhookSignature(t *testing.T) {
	t.Parallel()

	got := computeWebhookSignature("secret", []byte("payload"))
	want := "sha256=b82fcb791acec57859b989b430a826488ce2e479fdf92326bd0a2e8375a42ba4"
	if got != want {
		t.Fatalf("signature = %q, want %q", got, want)
	}
}

func TestWebhookSenderRetriesAndTracksAttempts(t *testing.T) {
	t.Parallel()

	redisClient := &redisStub{}
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts < 3 {
			http.Error(w, "unavailable", http.StatusServiceUnavailable)
			return
		}
		if got := r.Header.Get("X-Webhook-Signature"); !strings.HasPrefix(got, "sha256=") {
			t.Fatalf("signature header = %q", got)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	url := server.URL
	sender := NewWebhookSender(server.Client(), redisClient)
	result, err := sender.Send(WithHistoryID(context.Background(), "history-1"), model.NotificationEvent{
		EventID:    "event-55",
		WebhookURL: &url,
	}, &model.UserChannelProfile{WebhookSecret: ptr("secret")})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if !result.Success {
		t.Fatalf("Send() success = false")
	}
	if attempts != 3 {
		t.Fatalf("attempts = %d, want 3", attempts)
	}
	if redisClient.counts["webhook:retry:event-55"] != 3 {
		t.Fatalf("redis attempts = %d", redisClient.counts["webhook:retry:event-55"])
	}
}

func TestWebhookSenderStopsOnClientError(t *testing.T) {
	t.Parallel()

	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		http.Error(w, "bad request", http.StatusBadRequest)
	}))
	defer server.Close()

	url := server.URL
	sender := NewWebhookSender(server.Client(), &redisStub{})
	result, err := sender.Send(context.Background(), model.NotificationEvent{WebhookURL: &url}, &model.UserChannelProfile{})
	if err == nil {
		t.Fatalf("expected permanent error")
	}
	if result.Success {
		t.Fatalf("Send() success = true")
	}
	if attempts != 1 {
		t.Fatalf("attempts = %d, want 1", attempts)
	}
}

func TestWebhookSenderRequiresURL(t *testing.T) {
	t.Parallel()

	sender := NewWebhookSender(nil, &redisStub{})
	result, err := sender.Send(context.Background(), model.NotificationEvent{}, &model.UserChannelProfile{})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if result.Success {
		t.Fatalf("Send() success = true")
	}
}

func TestWebhookSenderPreservesPayload(t *testing.T) {
	t.Parallel()

	var body map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		if err := json.Unmarshal(raw, &body); err != nil {
			t.Fatalf("payload json: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	url := server.URL
	sender := NewWebhookSender(server.Client(), &redisStub{})
	_, err := sender.Send(context.Background(), model.NotificationEvent{
		EventID:    "event-1",
		UserID:     "user-1",
		WebhookURL: &url,
	}, &model.UserChannelProfile{})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if body["event_id"] != "event-1" {
		t.Fatalf("payload event_id = %#v", body["event_id"])
	}
}

func ptr(value string) *string {
	return &value
}
