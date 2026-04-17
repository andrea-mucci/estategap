package handler

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/estategap/services/scrape-orchestrator/internal/job"
	"github.com/estategap/services/scrape-orchestrator/internal/redisclient"
	"github.com/go-chi/chi/v5"
)

type StatusHandler struct {
	redis *redisclient.Client
}

func NewStatusHandler(redisClient *redisclient.Client) *StatusHandler {
	return &StatusHandler{redis: redisClient}
}

func (h *StatusHandler) Status(w http.ResponseWriter, r *http.Request) {
	jobID := strings.TrimSpace(chi.URLParam(r, "id"))
	if jobID == "" {
		http.Error(w, "missing job id", http.StatusBadRequest)
		return
	}

	fields, err := h.redis.HGetAll(r.Context(), job.Key(jobID)).Result()
	if err != nil {
		http.Error(w, "failed to load job status", http.StatusInternalServerError)
		return
	}
	if len(fields) == 0 {
		http.Error(w, "job not found", http.StatusNotFound)
		return
	}
	fields["job_id"] = jobID

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(fields)
}
