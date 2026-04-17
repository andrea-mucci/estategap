package metrics

import (
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
)

type Registry struct {
	RulesCached            prometheus.Gauge
	EventsProcessed        *prometheus.CounterVec
	Matches                prometheus.Counter
	DedupHits              prometheus.Counter
	NotificationsPublished *prometheus.CounterVec
	DigestBufferDepth      *prometheus.GaugeVec
	RuleEvalDuration       prometheus.Histogram
}

var (
	once     sync.Once
	registry *Registry
)

func New() *Registry {
	once.Do(func() {
		registry = &Registry{
			RulesCached: prometheus.NewGauge(prometheus.GaugeOpts{
				Name: "alert_engine_rules_cached_total",
				Help: "Number of active rules currently loaded in memory.",
			}),
			EventsProcessed: prometheus.NewCounterVec(prometheus.CounterOpts{
				Name: "alert_engine_events_processed_total",
				Help: "Number of events processed by the alert engine.",
			}, []string{"event_type"}),
			Matches: prometheus.NewCounter(prometheus.CounterOpts{
				Name: "alert_engine_matches_total",
				Help: "Number of rule matches produced by the engine.",
			}),
			DedupHits: prometheus.NewCounter(prometheus.CounterOpts{
				Name: "alert_engine_dedup_hits_total",
				Help: "Number of notifications skipped because they were already sent.",
			}),
			NotificationsPublished: prometheus.NewCounterVec(prometheus.CounterOpts{
				Name: "alert_engine_notifications_published_total",
				Help: "Number of notification events published to NATS.",
			}, []string{"channel", "frequency"}),
			DigestBufferDepth: prometheus.NewGaugeVec(prometheus.GaugeOpts{
				Name: "alert_engine_digest_buffer_depth",
				Help: "Approximate number of buffered digest entries by frequency.",
			}, []string{"frequency"}),
			RuleEvalDuration: prometheus.NewHistogram(prometheus.HistogramOpts{
				Name:    "alert_engine_rule_eval_duration_seconds",
				Help:    "End-to-end time spent evaluating one listing against cached rules.",
				Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1},
			}),
		}
		prometheus.MustRegister(
			registry.RulesCached,
			registry.EventsProcessed,
			registry.Matches,
			registry.DedupHits,
			registry.NotificationsPublished,
			registry.DigestBufferDepth,
			registry.RuleEvalDuration,
		)
	})

	return registry
}

func (r *Registry) ObserveRuleEval(duration time.Duration) {
	if r == nil {
		return
	}
	r.RuleEvalDuration.Observe(duration.Seconds())
}
