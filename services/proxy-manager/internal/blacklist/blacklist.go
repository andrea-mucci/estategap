package blacklist

import (
	"context"
	"strings"
	"sync"
	"time"

	"github.com/estategap/services/proxy-manager/internal/redisclient"
	"github.com/redis/go-redis/v9"
)

type Blacklist struct {
	client *redisclient.Client

	mu     sync.RWMutex
	memory map[string]time.Time
}

func New(client *redisclient.Client) *Blacklist {
	return &Blacklist{
		client: client,
		memory: make(map[string]time.Time),
	}
}

func (b *Blacklist) IsBlacklisted(ctx context.Context, ip string) bool {
	ip = strings.TrimSpace(ip)
	if ip == "" {
		return false
	}

	if b.client == nil {
		return b.memoryContains(ip)
	}

	_, err := b.client.Get(ctx, key(ip)).Result()
	return err == nil
}

func (b *Blacklist) Blacklist(ctx context.Context, ip string, ttl time.Duration) error {
	ip = strings.TrimSpace(ip)
	if ip == "" {
		return nil
	}

	if b.client == nil {
		b.mu.Lock()
		defer b.mu.Unlock()
		b.memory[ip] = time.Now().Add(ttl)
		return nil
	}

	return b.client.Set(ctx, key(ip), "1", ttl).Err()
}

func (b *Blacklist) BatchIsBlacklisted(ctx context.Context, ips []string) (map[string]bool, error) {
	if b.client == nil {
		out := make(map[string]bool, len(ips))
		for _, ip := range ips {
			out[ip] = b.memoryContains(ip)
		}
		return out, nil
	}

	pipe := b.client.Pipeline()
	cmds := make(map[string]*redis.IntCmd, len(ips))
	for _, ip := range ips {
		trimmed := strings.TrimSpace(ip)
		if trimmed == "" {
			continue
		}
		cmds[trimmed] = pipe.Exists(ctx, key(trimmed))
	}
	if _, err := pipe.Exec(ctx); err != nil && err != redis.Nil {
		return nil, err
	}

	out := make(map[string]bool, len(cmds))
	for ip, cmd := range cmds {
		count, err := cmd.Result()
		if err != nil && err != redis.Nil {
			return nil, err
		}
		out[ip] = count > 0
	}
	return out, nil
}

func key(ip string) string {
	return "proxy:blacklist:" + ip
}

func (b *Blacklist) memoryContains(ip string) bool {
	b.mu.Lock()
	defer b.mu.Unlock()

	expiresAt, ok := b.memory[ip]
	if !ok {
		return false
	}
	if time.Now().After(expiresAt) {
		delete(b.memory, ip)
		return false
	}
	return true
}
