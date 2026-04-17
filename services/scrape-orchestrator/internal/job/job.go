package job

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/estategap/services/scrape-orchestrator/internal/redisclient"
)

type ScrapeJob struct {
	JobID      string    `json:"job_id"`
	Portal     string    `json:"portal"`
	Country    string    `json:"country"`
	Mode       string    `json:"mode"`
	ZoneFilter []string  `json:"zone_filter,omitempty"`
	SearchURL  string    `json:"search_url"`
	CreatedAt  time.Time `json:"created_at"`
}

func (j *ScrapeJob) Marshal() ([]byte, error) {
	return json.Marshal(j)
}

func (j *ScrapeJob) Save(ctx context.Context, rdb *redisclient.Client, ttl time.Duration) error {
	if rdb == nil {
		return errors.New("redis client is required")
	}

	fields, err := j.Fields()
	if err != nil {
		return err
	}
	if err := rdb.HSet(ctx, key(j.JobID), fields).Err(); err != nil {
		return err
	}
	return rdb.Expire(ctx, key(j.JobID), ttl).Err()
}

func (j *ScrapeJob) Fields() (map[string]any, error) {
	zoneFilter, err := json.Marshal(j.ZoneFilter)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"job_id":       j.JobID,
		"status":       "pending",
		"portal":       j.Portal,
		"country":      j.Country,
		"mode":         j.Mode,
		"zone_filter":  string(zoneFilter),
		"search_url":   j.SearchURL,
		"created_at":   j.CreatedAt.UTC().Format(time.RFC3339),
		"started_at":   "",
		"completed_at": "",
		"error":        "",
	}, nil
}

func Key(jobID string) string {
	return key(jobID)
}

func key(jobID string) string {
	return "jobs:" + jobID
}
