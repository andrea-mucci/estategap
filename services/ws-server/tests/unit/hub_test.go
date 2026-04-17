package unit

import (
	"testing"
	"time"

	"github.com/estategap/services/ws-server/internal/config"
	"github.com/estategap/services/ws-server/internal/hub"
)

func TestHubOperations(t *testing.T) {
	t.Run("register and count connections", func(t *testing.T) {
		h := hub.New(2)
		conn := testConnection("user-1")

		if err := h.Register(conn); err != nil {
			t.Fatalf("register connection: %v", err)
		}
		if got := h.ConnectionCount(); got != 1 {
			t.Fatalf("connection count = %d, want 1", got)
		}

		h.Unregister(conn)
		if got := h.ConnectionCount(); got != 0 {
			t.Fatalf("connection count after unregister = %d, want 0", got)
		}
	})

	t.Run("send delivers to connected user", func(t *testing.T) {
		h := hub.New(2)
		conn := testConnection("user-1")
		if err := h.Register(conn); err != nil {
			t.Fatalf("register connection: %v", err)
		}

		if ok := h.Send("user-1", []byte(`{"type":"text_chunk","payload":{}}`)); !ok {
			t.Fatalf("send returned false, want true")
		}

		select {
		case got := <-conn.SendQueue():
			if string(got) != `{"type":"text_chunk","payload":{}}` {
				t.Fatalf("unexpected payload: %s", got)
			}
		default:
			t.Fatal("expected message in send queue")
		}
	})

	t.Run("send to disconnected user is no-op", func(t *testing.T) {
		h := hub.New(1)
		if ok := h.Send("missing-user", []byte(`{"type":"text_chunk","payload":{}}`)); ok {
			t.Fatalf("send returned true for missing user")
		}
	})

	t.Run("capacity rejection returns error", func(t *testing.T) {
		h := hub.New(1)
		if err := h.Register(testConnection("user-1")); err != nil {
			t.Fatalf("register first connection: %v", err)
		}
		if err := h.Register(testConnection("user-2")); err != hub.ErrAtCapacity {
			t.Fatalf("register second connection error = %v, want %v", err, hub.ErrAtCapacity)
		}
	})
}

func testConnection(userID string) *hub.Connection {
	return hub.NewConnection(userID, "basic", nil, &config.Config{
		PingInterval: time.Second,
		PongTimeout:  time.Second,
		IdleTimeout:  time.Minute,
	})
}
