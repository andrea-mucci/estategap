package broker

import (
	"context"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/segmentio/kafka-go"
)

var kafkaConsumerLag = promauto.NewGaugeVec(prometheus.GaugeOpts{
	Name: "estategap_kafka_consumer_lag",
	Help: "Kafka consumer group lag per topic partition.",
}, []string{"group", "topic", "partition"})

// StartLagPoller periodically snapshots reader lag into Prometheus.
func StartLagPoller(ctx context.Context, reader *kafka.Reader, group string) {
	ticker := time.NewTicker(30 * time.Second)
	go func() {
		defer ticker.Stop()
		updateLagGauge(reader, group)
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				updateLagGauge(reader, group)
			}
		}
	}()
}

func updateLagGauge(reader *kafka.Reader, group string) {
	stats := reader.Stats()
	partition := "all"
	if stats.Partition >= 0 {
		partition = strconv.FormatInt(int64(stats.Partition), 10)
	}
	topic := stats.Topic
	if topic == "" {
		topic = "unknown"
	}
	kafkaConsumerLag.WithLabelValues(group, topic, partition).Set(float64(stats.Lag))
}
