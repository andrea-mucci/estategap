package sticky

import (
	"context"
	"strings"
	"sync"
	"time"

	"github.com/estategap/services/proxy-manager/internal/redisclient"
	"github.com/redis/go-redis/v9"
)

type Sticky struct {
	client *redisclient.Client
	ttl    time.Duration

	mu     sync.RWMutex
	memory map[string]memoryEntry
}

type memoryEntry struct {
	proxyID   string
	expiresAt time.Time
}

func New(client *redisclient.Client, ttl time.Duration) *Sticky {
	return &Sticky{
		client: client,
		ttl:    ttl,
		memory: make(map[string]memoryEntry),
	}
}

func (s *Sticky) Get(ctx context.Context, sessionID string) (string, bool) {
	sessionID = strings.TrimSpace(sessionID)
	if sessionID == "" {
		return "", false
	}

	if s.client == nil {
		s.mu.Lock()
		defer s.mu.Unlock()

		entry, ok := s.memory[sessionID]
		if !ok || time.Now().After(entry.expiresAt) {
			delete(s.memory, sessionID)
			return "", false
		}
		entry.expiresAt = time.Now().Add(s.ttl)
		s.memory[sessionID] = entry
		return entry.proxyID, true
	}

	result, err := s.client.GetEx(ctx, key(sessionID), s.ttl).Result()
	if err == redis.Nil {
		return "", false
	}
	if err != nil {
		return "", false
	}
	return result, true
}

func (s *Sticky) Set(ctx context.Context, sessionID, proxyID string, ttl time.Duration) error {
	sessionID = strings.TrimSpace(sessionID)
	if sessionID == "" {
		return nil
	}

	if ttl <= 0 {
		ttl = s.ttl
	}

	if s.client == nil {
		s.mu.Lock()
		defer s.mu.Unlock()
		s.memory[sessionID] = memoryEntry{
			proxyID:   proxyID,
			expiresAt: time.Now().Add(ttl),
		}
		return nil
	}

	return s.client.Set(ctx, key(sessionID), proxyID, ttl).Err()
}

func key(sessionID string) string {
	return "proxy:sticky:" + sessionID
}
