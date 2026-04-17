package metrics

import (
	"sync"

	"github.com/prometheus/client_golang/prometheus"
)

var (
	registerOnce sync.Once

	poolSize = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "proxy_pool_size",
			Help: "Configured proxies per country and provider.",
		},
		[]string{"country", "provider"},
	)
	healthyCount = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "proxy_healthy_count",
			Help: "Healthy proxies per country and provider.",
		},
		[]string{"country", "provider"},
	)
	blockRate = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "proxy_block_rate",
			Help: "Blacklisted proxy ratio per country and provider.",
		},
		[]string{"country", "provider"},
	)
)

func Update(country, provider string, total, healthy int, blockedRatio float64) {
	registerOnce.Do(func() {
		prometheus.MustRegister(poolSize, healthyCount, blockRate)
	})

	poolSize.WithLabelValues(country, provider).Set(float64(total))
	healthyCount.WithLabelValues(country, provider).Set(float64(healthy))
	blockRate.WithLabelValues(country, provider).Set(blockedRatio)
}
