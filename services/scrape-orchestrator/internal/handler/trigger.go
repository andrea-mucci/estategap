package handler

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/estategap/services/scrape-orchestrator/internal/db"
)

type triggerScheduler interface {
	PublishNow(ctx context.Context, portal db.Portal, mode string, zoneFilter []string, searchURL string) (string, error)
}

type TriggerHandler struct {
	scheduler triggerScheduler
}

type TriggerRequest struct {
	Portal     string   `json:"portal"`
	Country    string   `json:"country"`
	Mode       string   `json:"mode"`
	ZoneFilter []string `json:"zone_filter"`
	SearchURL  string   `json:"search_url"`
}

func NewTriggerHandler(scheduler triggerScheduler) *TriggerHandler {
	return &TriggerHandler{scheduler: scheduler}
}

func (h *TriggerHandler) Trigger(w http.ResponseWriter, r *http.Request) {
	var req TriggerRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}

	req.Portal = strings.TrimSpace(req.Portal)
	req.Country = strings.ToUpper(strings.TrimSpace(req.Country))
	req.Mode = strings.TrimSpace(req.Mode)
	req.SearchURL = strings.TrimSpace(req.SearchURL)
	if req.Portal == "" || req.Country == "" || req.Mode == "" || req.SearchURL == "" {
		http.Error(w, "portal, country, mode, and search_url are required", http.StatusBadRequest)
		return
	}

	jobID, err := h.scheduler.PublishNow(r.Context(), db.Portal{
		Name:       req.Portal,
		Country:    req.Country,
		SearchURLs: []string{req.SearchURL},
	}, req.Mode, req.ZoneFilter, req.SearchURL)
	if err != nil {
		http.Error(w, "failed to publish job", http.StatusServiceUnavailable)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"job_id": jobID,
		"status": "pending",
	})
}
