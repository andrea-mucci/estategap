package dedup

import (
	"context"
	"fmt"
	"time"

	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/redis/go-redis/v9"
)

const dedupTTL = 7 * 24 * time.Hour

type Dedup struct {
	client  *redis.Client
	metrics *metrics.Registry
}

func New(client *redis.Client, registry *metrics.Registry) *Dedup {
	return &Dedup{
		client:  client,
		metrics: registry,
	}
}

func (d *Dedup) IsSent(ctx context.Context, userID, listingID string) (bool, error) {
	sent, err := d.client.SIsMember(ctx, key(userID), listingID).Result()
	if err != nil {
		return false, err
	}
	if sent && d.metrics != nil {
		d.metrics.DedupHits.Inc()
	}
	return sent, nil
}

func (d *Dedup) MarkSent(ctx context.Context, userID, listingID string) error {
	pipe := d.client.TxPipeline()
	pipe.SAdd(ctx, key(userID), listingID)
	pipe.Expire(ctx, key(userID), dedupTTL)
	_, err := pipe.Exec(ctx)
	return err
}

func (d *Dedup) ClearSent(ctx context.Context, userID, listingID string) error {
	return d.client.SRem(ctx, key(userID), listingID).Err()
}

func key(userID string) string {
	return fmt.Sprintf("alerts:sent:%s", userID)
}
