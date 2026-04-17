package digest

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/redis/go-redis/v9"
)

type Buffer struct {
	client  *redis.Client
	metrics *metrics.Registry
}

func NewBuffer(client *redis.Client, registry *metrics.Registry) *Buffer {
	return &Buffer{
		client:  client,
		metrics: registry,
	}
}

func (b *Buffer) Add(ctx context.Context, userID, ruleID string, frequency string, listingID string, dealScore float64) error {
	frequency = model.NormalizeFrequency(frequency)
	key := Key(userID, ruleID, frequency)

	added, err := b.client.ZAdd(ctx, key, redis.Z{Score: dealScore, Member: listingID}).Result()
	if err != nil {
		return err
	}
	if err := b.client.Expire(ctx, key, ttlForFrequency(frequency)).Err(); err != nil {
		return err
	}

	if added > 0 && b.metrics != nil {
		b.metrics.DigestBufferDepth.WithLabelValues(frequency).Add(float64(added))
	}

	return nil
}

func (b *Buffer) Flush(ctx context.Context, key string, limit int) ([]string, int, error) {
	if limit <= 0 {
		limit = 20
	}

	pipe := b.client.TxPipeline()
	totalCmd := pipe.ZCard(ctx, key)
	itemsCmd := pipe.ZRevRange(ctx, key, 0, int64(limit-1))
	pipe.Del(ctx, key)
	if _, err := pipe.Exec(ctx); err != nil {
		return nil, 0, err
	}

	items := itemsCmd.Val()
	total := int(totalCmd.Val())
	if total > 0 && b.metrics != nil {
		frequency := frequencyFromKey(key)
		b.metrics.DigestBufferDepth.WithLabelValues(frequency).Add(-float64(total))
	}

	return items, total, nil
}

func Key(userID, ruleID string, frequency string) string {
	return fmt.Sprintf("alerts:digest:%s:%s:%s", userID, ruleID, model.NormalizeFrequency(frequency))
}

func ParseKey(key string) (string, string, string, error) {
	parts := strings.Split(key, ":")
	if len(parts) != 5 {
		return "", "", "", fmt.Errorf("invalid digest key: %s", key)
	}
	return parts[2], parts[3], model.NormalizeFrequency(parts[4]), nil
}

func frequencyFromKey(key string) string {
	_, _, frequency, err := ParseKey(key)
	if err != nil {
		return model.FrequencyInstant
	}
	return frequency
}

func ttlForFrequency(frequency string) time.Duration {
	switch model.NormalizeFrequency(frequency) {
	case model.FrequencyHourly:
		return time.Hour
	case model.FrequencyDaily:
		return 24 * time.Hour
	default:
		return time.Hour
	}
}
