package job

import (
	"encoding/json"
	"testing"
	"time"
)

func TestScrapeJobMarshal(t *testing.T) {
	t.Parallel()

	createdAt := time.Date(2026, 4, 17, 10, 30, 0, 0, time.UTC)
	item := &ScrapeJob{
		JobID:      "job-1",
		Portal:     "immobiliare",
		Country:    "IT",
		Mode:       "full",
		ZoneFilter: []string{"zone-1"},
		SearchURL:  "https://example.com/search",
		CreatedAt:  createdAt,
	}

	payload, err := item.Marshal()
	if err != nil {
		t.Fatalf("Marshal() error = %v", err)
	}

	var decoded map[string]any
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("json.Unmarshal() error = %v", err)
	}

	if decoded["job_id"] != item.JobID {
		t.Fatalf("job_id = %v, want %q", decoded["job_id"], item.JobID)
	}
	if decoded["search_url"] != item.SearchURL {
		t.Fatalf("search_url = %v, want %q", decoded["search_url"], item.SearchURL)
	}
}

func TestScrapeJobFields(t *testing.T) {
	t.Parallel()

	createdAt := time.Date(2026, 4, 17, 10, 30, 0, 0, time.UTC)
	item := &ScrapeJob{
		JobID:      "job-1",
		Portal:     "immobiliare",
		Country:    "IT",
		Mode:       "full",
		ZoneFilter: []string{"zone-1"},
		SearchURL:  "https://example.com/search",
		CreatedAt:  createdAt,
	}

	fields, err := item.Fields()
	if err != nil {
		t.Fatalf("Fields() error = %v", err)
	}
	if fields["status"] != "pending" {
		t.Fatalf("status = %v, want pending", fields["status"])
	}
	if fields["created_at"] != createdAt.Format(time.RFC3339) {
		t.Fatalf("created_at = %v, want %q", fields["created_at"], createdAt.Format(time.RFC3339))
	}
}
