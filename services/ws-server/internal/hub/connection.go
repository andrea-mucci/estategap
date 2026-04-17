package hub

import (
	"context"
	"encoding/json"
	"sync"
	"time"

	"github.com/estategap/services/ws-server/internal/config"
	"github.com/estategap/services/ws-server/internal/protocol"
	"github.com/gorilla/websocket"
)

type Connection struct {
	userID       string
	tier         string
	conn         *websocket.Conn
	send         chan []byte
	done         chan struct{}
	connectedAt  time.Time
	lastActivity time.Time
	cfg          *config.Config

	ctx        context.Context
	cancel     context.CancelFunc
	signalOnce sync.Once
	doneOnce   sync.Once
	activityMu sync.RWMutex
}

func NewConnection(userID, tier string, conn *websocket.Conn, cfg *config.Config) *Connection {
	now := time.Now().UTC()
	ctx, cancel := context.WithCancel(context.Background())
	return &Connection{
		userID:       userID,
		tier:         tier,
		conn:         conn,
		send:         make(chan []byte, 256),
		done:         make(chan struct{}),
		connectedAt:  now,
		lastActivity: now,
		cfg:          cfg,
		ctx:          ctx,
		cancel:       cancel,
	}
}

func (c *Connection) UserID() string {
	return c.userID
}

func (c *Connection) Tier() string {
	return c.tier
}

func (c *Connection) Context() context.Context {
	return c.ctx
}

func (c *Connection) Done() <-chan struct{} {
	return c.done
}

func (c *Connection) SendQueue() <-chan []byte {
	return c.send
}

func (c *Connection) Enqueue(payload []byte) bool {
	select {
	case <-c.done:
		return false
	case c.send <- payload:
		return true
	default:
		return false
	}
}

func (c *Connection) Close() {
	c.signalOnce.Do(func() {
		c.cancel()
	})
}

func (c *Connection) ForceClose() {
	c.Close()
	if c.conn != nil {
		_ = c.conn.Close()
	}
}

func (c *Connection) LastActivity() time.Time {
	c.activityMu.RLock()
	defer c.activityMu.RUnlock()
	return c.lastActivity
}

func (c *Connection) MarkActivity() {
	c.activityMu.Lock()
	c.lastActivity = time.Now().UTC()
	c.activityMu.Unlock()
}

func (c *Connection) WritePump(hub *Hub) {
	ticker := time.NewTicker(c.cfg.PingInterval)
	defer ticker.Stop()
	defer func() {
		hub.Unregister(c)
		c.markDone()
		c.ForceClose()
	}()

	for {
		select {
		case <-c.ctx.Done():
			_ = c.conn.SetWriteDeadline(time.Now().Add(c.cfg.PongTimeout))
			_ = c.conn.WriteControl(
				websocket.CloseMessage,
				websocket.FormatCloseMessage(websocket.CloseGoingAway, "going away"),
				time.Now().Add(c.cfg.PongTimeout),
			)
			return
		case payload, ok := <-c.send:
			if !ok {
				return
			}
			if err := c.conn.SetWriteDeadline(time.Now().Add(c.cfg.PongTimeout)); err != nil {
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, payload); err != nil {
				return
			}
		case <-ticker.C:
			if c.cfg.IdleTimeout > 0 && time.Since(c.LastActivity()) >= c.cfg.IdleTimeout {
				return
			}
			if err := c.conn.SetWriteDeadline(time.Now().Add(c.cfg.PongTimeout)); err != nil {
				return
			}
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

func (c *Connection) ReadPump(hub *Hub, dispatch func(*Connection, protocol.Envelope)) {
	defer func() {
		hub.Unregister(c)
		c.markDone()
		c.ForceClose()
	}()

	_ = c.conn.SetReadDeadline(time.Now().Add(c.readDeadline()))
	c.conn.SetPongHandler(func(string) error {
		return c.conn.SetReadDeadline(time.Now().Add(c.readDeadline()))
	})

	for {
		_, payload, err := c.conn.ReadMessage()
		if err != nil {
			return
		}

		_ = c.conn.SetReadDeadline(time.Now().Add(c.readDeadline()))
		c.MarkActivity()

		var env protocol.Envelope
		if err := json.Unmarshal(payload, &env); err != nil {
			c.writeErrorEnvelope()
			continue
		}

		dispatch(c, env)
	}
}

func (c *Connection) readDeadline() time.Duration {
	return c.cfg.PingInterval + c.cfg.PongTimeout
}

func (c *Connection) writeErrorEnvelope() {
	payload, err := protocol.MarshalEnvelope("error", "", protocol.ErrorPayload{
		Code:    "invalid_message",
		Message: "invalid message envelope",
	})
	if err != nil {
		return
	}
	_ = c.Enqueue(payload)
}

func (c *Connection) markDone() {
	c.doneOnce.Do(func() {
		close(c.done)
	})
}
