package hub

import (
	"errors"
	"sync"
	"time"

	"github.com/estategap/services/ws-server/internal/metrics"
	"github.com/estategap/services/ws-server/internal/protocol"
)

var (
	ErrAtCapacity   = errors.New("hub at capacity")
	ErrShuttingDown = errors.New("hub shutting down")
)

type Hub struct {
	mu           sync.RWMutex
	conns        map[string][]*Connection
	maxConns     int
	shuttingDown bool
}

func New(maxConns int) *Hub {
	if maxConns <= 0 {
		maxConns = 10000
	}
	return &Hub{
		conns:    make(map[string][]*Connection),
		maxConns: maxConns,
	}
}

func (h *Hub) Register(c *Connection) error {
	h.mu.Lock()
	defer h.mu.Unlock()

	if h.shuttingDown {
		return ErrShuttingDown
	}
	if h.connectionCountLocked() >= h.maxConns {
		return ErrAtCapacity
	}

	h.conns[c.userID] = append(h.conns[c.userID], c)
	metrics.ConnectionsActive.Inc()
	return nil
}

func (h *Hub) Unregister(c *Connection) {
	h.mu.Lock()
	defer h.mu.Unlock()

	conns := h.conns[c.userID]
	if len(conns) == 0 {
		return
	}

	updated := conns[:0]
	removed := false
	for _, existing := range conns {
		if existing == c {
			removed = true
			continue
		}
		updated = append(updated, existing)
	}

	if !removed {
		return
	}
	if len(updated) == 0 {
		delete(h.conns, c.userID)
	} else {
		h.conns[c.userID] = updated
	}
	metrics.ConnectionsActive.Dec()
}

func (h *Hub) Send(userID string, payload []byte) bool {
	h.mu.RLock()
	targets := append([]*Connection(nil), h.conns[userID]...)
	h.mu.RUnlock()

	if len(targets) == 0 {
		return false
	}

	messageType := metrics.TypeFromPayload(payload)
	delivered := false
	for _, conn := range targets {
		if conn.Enqueue(payload) {
			metrics.MessagesSentTotal.WithLabelValues(messageType).Inc()
			delivered = true
			continue
		}
		metrics.SendDroppedTotal.Inc()
	}
	return delivered
}

func (h *Hub) ConnectionCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.connectionCountLocked()
}

func (h *Hub) Shutdown(timeout time.Duration) {
	h.mu.Lock()
	h.shuttingDown = true
	targets := make([]*Connection, 0, h.connectionCountLocked())
	for _, conns := range h.conns {
		targets = append(targets, conns...)
	}
	h.mu.Unlock()

	payload, _ := protocol.MarshalEnvelope("error", "", protocol.ErrorPayload{
		Code:    "server_shutting_down",
		Message: "server is shutting down",
	})

	var wg sync.WaitGroup
	for _, conn := range targets {
		if payload != nil {
			_ = conn.Enqueue(payload)
		}
		wg.Add(1)
		go func(c *Connection) {
			defer wg.Done()
			c.Close()
			select {
			case <-c.Done():
			case <-time.After(timeout):
				c.ForceClose()
			}
		}(conn)
	}

	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(timeout):
		for _, conn := range targets {
			conn.ForceClose()
		}
	}
}

func (h *Hub) connectionCountLocked() int {
	total := 0
	for _, conns := range h.conns {
		total += len(conns)
	}
	return total
}
