package cache

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/redis/go-redis/v9"
)

type Client struct {
	rdb *redis.Client
}

type RequestCache struct {
	client *Client
	prefix string
	ttl    time.Duration
}

type ZoneStatsCache struct {
	RequestCache
}

type TopDealsCache struct {
	RequestCache
}

type AlertRulesCache struct {
	RequestCache
}

func NewClient(rdb *redis.Client) *Client {
	return &Client{rdb: rdb}
}

func NewZoneStatsCache(client *Client) ZoneStatsCache {
	return ZoneStatsCache{
		RequestCache: RequestCache{
			client: client,
			prefix: "cache:zone-stats",
			ttl:    5 * time.Minute,
		},
	}
}

func NewTopDealsCache(client *Client) TopDealsCache {
	return TopDealsCache{
		RequestCache: RequestCache{
			client: client,
			prefix: "cache:top-deals",
			ttl:    time.Minute,
		},
	}
}

func NewAlertRulesCache(client *Client) AlertRulesCache {
	return AlertRulesCache{
		RequestCache: RequestCache{
			client: client,
			prefix: "cache:alert-rules",
			ttl:    time.Minute,
		},
	}
}

func GetOrSet[T any](ctx context.Context, c *Client, key string, ttl time.Duration, fn func() (T, error)) (T, error) {
	value, _, err := getOrSetWithStatus(ctx, c, key, ttl, fn)
	return value, err
}

func GetOrSetRequest[T any](ctx context.Context, cache RequestCache, r *http.Request, fn func() (T, error)) (T, bool, error) {
	return getOrSetWithStatus(ctx, cache.client, cache.cacheKey(r), cache.ttl, fn)
}

func (c RequestCache) cacheKey(r *http.Request) string {
	if r == nil {
		return c.prefix
	}

	values := r.URL.Query()
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	var builder strings.Builder
	builder.WriteString(r.URL.Path)
	builder.WriteString("\n")

	if userID := ctxkey.String(r.Context(), ctxkey.UserID); userID != "" {
		builder.WriteString("user=")
		builder.WriteString(userID)
		builder.WriteString("\n")
	}

	for _, key := range keys {
		params := append([]string(nil), values[key]...)
		sort.Strings(params)
		if len(params) == 0 {
			builder.WriteString(key)
			builder.WriteString("=\n")
			continue
		}
		for _, value := range params {
			builder.WriteString(key)
			builder.WriteString("=")
			builder.WriteString(value)
			builder.WriteString("\n")
		}
	}

	sum := sha256.Sum256([]byte(builder.String()))
	return c.prefix + ":" + hex.EncodeToString(sum[:])
}

func getOrSetWithStatus[T any](ctx context.Context, c *Client, key string, ttl time.Duration, fn func() (T, error)) (T, bool, error) {
	var zero T

	if c == nil || c.rdb == nil {
		value, err := fn()
		return value, false, err
	}

	payload, err := c.rdb.Get(ctx, key).Bytes()
	switch {
	case err == nil:
		var cached T
		if json.Unmarshal(payload, &cached) == nil {
			return cached, true, nil
		}
		_ = c.rdb.Del(ctx, key).Err()
	case !errors.Is(err, redis.Nil):
		// Degrade to the source of truth instead of failing the request on cache errors.
	}

	value, err := fn()
	if err != nil {
		return zero, false, err
	}

	encoded, err := json.Marshal(value)
	if err != nil {
		return zero, false, err
	}

	if err := c.rdb.Set(ctx, key, encoded, ttl).Err(); err != nil {
		return value, false, nil
	}

	return value, false, nil
}
