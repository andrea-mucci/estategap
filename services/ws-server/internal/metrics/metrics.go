package metrics

import (
	"encoding/json"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	ConnectionsActive = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "ws_connections_active",
		Help: "Current number of active websocket connections.",
	})
	MessagesSentTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "ws_messages_sent_total",
		Help: "Total websocket messages sent to clients.",
	}, []string{"type"})
	MessagesReceivedTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "ws_messages_received_total",
		Help: "Total websocket messages received from clients.",
	}, []string{"type"})
	SendDroppedTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "ws_send_dropped_total",
		Help: "Total websocket messages dropped because the send buffer was full.",
	})
	UpgradeRejectedTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "ws_upgrade_rejected_total",
		Help: "Total websocket upgrade requests rejected before connection establishment.",
	}, []string{"reason"})
	GRPCStreamDurationSeconds = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "ws_grpc_stream_duration_seconds",
		Help:    "Duration of chat gRPC streams opened by ws-server.",
		Buckets: prometheus.DefBuckets,
	}, []string{"status"})
	NATSNotificationsDeliveredTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "ws_nats_notifications_delivered_total",
		Help: "Total deal alert notifications delivered to connected users.",
	})
	NATSNotificationsSkippedTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "ws_nats_notifications_skipped_total",
		Help: "Total deal alert notifications skipped because no active connection received them.",
	})
)

func TypeFromPayload(payload []byte) string {
	var env struct {
		Type string `json:"type"`
	}
	if err := json.Unmarshal(payload, &env); err != nil {
		return "unknown"
	}
	if env.Type == "" {
		return "unknown"
	}
	return env.Type
}
