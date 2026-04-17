package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"time"

	"github.com/estategap/services/ws-server/internal/config"
	"github.com/estategap/services/ws-server/internal/hub"
	"github.com/estategap/services/ws-server/internal/metrics"
	"github.com/estategap/services/ws-server/internal/middleware"
	"github.com/estategap/services/ws-server/internal/protocol"
	"github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
)

type WSHandler struct {
	hub        *hub.Hub
	chatClient protocol.ChatStreamer
	cfg        *config.Config
	redis      *redis.Client
	upgrader   websocket.Upgrader
}

func NewWSHandler(h *hub.Hub, chatClient protocol.ChatStreamer, cfg *config.Config, redisClient *redis.Client) *WSHandler {
	return &WSHandler{
		hub:        h,
		chatClient: chatClient,
		cfg:        cfg,
		redis:      redisClient,
		upgrader: websocket.Upgrader{
			CheckOrigin: func(*http.Request) bool { return true },
		},
	}
}

func (h *WSHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	token := middleware.ExtractToken(r)
	claims, err := middleware.ValidateToken(token, h.cfg.JWTSecret, h.redis)
	if err != nil {
		metrics.UpgradeRejectedTotal.WithLabelValues("auth").Inc()
		writeJSONError(w, http.StatusUnauthorized, "unauthorized", middleware.Reason(err))
		return
	}

	if h.hub.ConnectionCount() >= h.cfg.MaxConnections {
		metrics.UpgradeRejectedTotal.WithLabelValues("capacity").Inc()
		w.Header().Set("Retry-After", "5")
		writeJSONError(w, http.StatusServiceUnavailable, "capacity", "connection limit reached")
		return
	}

	wsConn, err := h.upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}

	conn := hub.NewConnection(claims.Subject, claims.Tier, wsConn, h.cfg)
	if err := h.hub.Register(conn); err != nil {
		_ = wsConn.WriteControl(
			websocket.CloseMessage,
			websocket.FormatCloseMessage(websocket.CloseTryAgainLater, err.Error()),
			time.Now().Add(h.cfg.PongTimeout),
		)
		_ = wsConn.Close()
		if errors.Is(err, hub.ErrAtCapacity) {
			metrics.UpgradeRejectedTotal.WithLabelValues("capacity").Inc()
		}
		return
	}

	dispatch := func(c *hub.Connection, env protocol.Envelope) {
		protocol.Dispatch(c, env, h.chatClient)
	}

	go conn.WritePump(h.hub)
	go conn.ReadPump(h.hub, dispatch)
}

func writeJSONError(w http.ResponseWriter, status int, errorType, reason string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{
		"error":  errorType,
		"reason": reason,
	})
}
