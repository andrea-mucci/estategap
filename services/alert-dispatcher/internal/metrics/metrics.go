package metrics

import (
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
)

type Registry struct {
	NotificationsTotal *prometheus.CounterVec
	DeliveryLatency    *prometheus.HistogramVec
	RetryAttemptsTotal *prometheus.CounterVec
	ConsumerLag        prometheus.Gauge
}

var (
	once     sync.Once
	registry *Registry
)

func New() *Registry {
	once.Do(func() {
		registry = &Registry{
			NotificationsTotal: prometheus.NewCounterVec(prometheus.CounterOpts{
				Name: "dispatcher_notifications_total",
				Help: "Notifications processed by channel and terminal status.",
			}, []string{"channel", "status"}),
			DeliveryLatency: prometheus.NewHistogramVec(prometheus.HistogramOpts{
				Name:    "dispatcher_delivery_latency_seconds",
				Help:    "End-to-end notification delivery latency per channel.",
				Buckets: []float64{0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30},
			}, []string{"channel"}),
			RetryAttemptsTotal: prometheus.NewCounterVec(prometheus.CounterOpts{
				Name: "dispatcher_retry_attempts_total",
				Help: "Additional retry attempts performed per channel.",
			}, []string{"channel"}),
			ConsumerLag: prometheus.NewGauge(prometheus.GaugeOpts{
				Name: "dispatcher_consumer_lag",
				Help: "Approximate number of pending notifications in JetStream.",
			}),
		}
		prometheus.MustRegister(
			registry.NotificationsTotal,
			registry.DeliveryLatency,
			registry.RetryAttemptsTotal,
			registry.ConsumerLag,
		)
	})

	return registry
}

func (r *Registry) ObserveDelivery(channel, status string, duration time.Duration, attempts int) {
	if r == nil {
		return
	}
	r.NotificationsTotal.WithLabelValues(channel, status).Inc()
	r.DeliveryLatency.WithLabelValues(channel).Observe(duration.Seconds())
	if attempts > 1 {
		r.RetryAttemptsTotal.WithLabelValues(channel).Add(float64(attempts - 1))
	}
}
