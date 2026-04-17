package middleware

import (
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/prometheus/client_golang/prometheus"
)

var (
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests processed by the API gateway.",
		},
		[]string{"method", "path", "status"},
	)
	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request durations by method and path.",
			Buckets: []float64{0.005, 0.025, 0.1, 0.25, 0.5, 1, 2.5},
		},
		[]string{"method", "path"},
	)
	activeConnections = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "active_connections",
			Help: "Number of in-flight HTTP requests.",
		},
	)
	registerMetrics sync.Once
)

func MetricsMiddleware() func(http.Handler) http.Handler {
	registerMetrics.Do(func() {
		for _, collector := range []prometheus.Collector{httpRequestsTotal, httpRequestDuration, activeConnections} {
			if err := prometheus.Register(collector); err != nil {
				if _, ok := err.(prometheus.AlreadyRegisteredError); !ok {
					panic(err)
				}
			}
		}
	})

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			activeConnections.Inc()
			defer activeConnections.Dec()

			ww := &metricsResponseWriter{ResponseWriter: w, status: http.StatusOK}
			started := time.Now()
			next.ServeHTTP(ww, r)

			path := routePattern(r)
			status := strconv.Itoa(ww.status)
			httpRequestsTotal.WithLabelValues(r.Method, path, status).Inc()
			httpRequestDuration.WithLabelValues(r.Method, path).Observe(time.Since(started).Seconds())
		})
	}
}

func routePattern(r *http.Request) string {
	if routeCtx := chi.RouteContext(r.Context()); routeCtx != nil {
		if pattern := routeCtx.RoutePattern(); pattern != "" {
			return pattern
		}
	}
	return r.URL.Path
}

type metricsResponseWriter struct {
	http.ResponseWriter
	status int
}

func (w *metricsResponseWriter) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}
