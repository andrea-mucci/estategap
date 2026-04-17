package cache

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/redis/go-redis/v9"
)

type Client struct {
	rdb *redis.Client
}

func NewClient(rdb *redis.Client) *Client {
	return &Client{rdb: rdb}
}

func GetOrSet[T any](ctx context.Context, c *Client, key string, ttl time.Duration, fn func() (T, error)) (T, error) {
	var zero T

	if c == nil || c.rdb == nil {
		return fn()
	}

	payload, err := c.rdb.Get(ctx, key).Bytes()
	switch {
	case err == nil:
		var cached T
		if json.Unmarshal(payload, &cached) == nil {
			return cached, nil
		}
		_ = c.rdb.Del(ctx, key).Err()
	case !errors.Is(err, redis.Nil):
		// Degrade to the source of truth instead of failing the request on cache errors.
	}

	value, err := fn()
	if err != nil {
		return zero, err
	}

	encoded, err := json.Marshal(value)
	if err != nil {
		return zero, err
	}

	if err := c.rdb.Set(ctx, key, encoded, ttl).Err(); err != nil {
		return value, nil
	}

	return value, nil
}
