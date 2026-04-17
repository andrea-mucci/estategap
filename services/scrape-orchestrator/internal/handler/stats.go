package handler

import (
	"encoding/json"
	"net/http"

	"github.com/estategap/services/scrape-orchestrator/internal/redisclient"
	"github.com/redis/go-redis/v9"
)

type StatsHandler struct {
	redis *redisclient.Client
}

func NewStatsHandler(redisClient *redisclient.Client) *StatsHandler {
	return &StatsHandler{redis: redisClient}
}

func (h *StatsHandler) Stats(w http.ResponseWriter, r *http.Request) {
	stats := map[string]int{
		"pending":   0,
		"running":   0,
		"completed": 0,
		"failed":    0,
		"total":     0,
	}

	var cursor uint64
	for {
		keys, next, err := h.redis.Scan(r.Context(), cursor, "jobs:*", 100).Result()
		if err != nil {
			http.Error(w, "failed to scan jobs", http.StatusInternalServerError)
			return
		}

		if len(keys) > 0 {
			pipe := h.redis.Pipeline()
			cmds := make([]*redis.StringCmd, 0, len(keys))
			for _, key := range keys {
				cmds = append(cmds, pipe.HGet(r.Context(), key, "status"))
			}
			if _, err := pipe.Exec(r.Context()); err != nil && err != redis.Nil {
				http.Error(w, "failed to aggregate job stats", http.StatusInternalServerError)
				return
			}
			for _, cmd := range cmds {
				status, err := cmd.Result()
				if err != nil && err != redis.Nil {
					http.Error(w, "failed to aggregate job stats", http.StatusInternalServerError)
					return
				}
				if _, ok := stats[status]; ok {
					stats[status]++
				}
				stats["total"]++
			}
		}

		cursor = next
		if cursor == 0 {
			break
		}
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(stats)
}
