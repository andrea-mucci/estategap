package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"
	"time"

	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/google/uuid"
)

type stubAlertRulesRepo struct {
	countActiveRulesFn func(ctx context.Context, userID uuid.UUID) (int, error)
	createRuleFn       func(ctx context.Context, input repository.AlertRuleInput) (*repository.AlertRule, error)
	listHistoryFn      func(ctx context.Context, userID uuid.UUID, filter repository.HistoryFilter, page, pageSize int) ([]repository.AlertHistoryEntry, int, error)
	validateZoneIDsFn  func(ctx context.Context, zoneIDs []uuid.UUID) ([]uuid.UUID, error)
}

func (s *stubAlertRulesRepo) CountActiveRules(ctx context.Context, userID uuid.UUID) (int, error) {
	if s.countActiveRulesFn != nil {
		return s.countActiveRulesFn(ctx, userID)
	}
	return 0, nil
}

func (s *stubAlertRulesRepo) CreateRule(ctx context.Context, input repository.AlertRuleInput) (*repository.AlertRule, error) {
	if s.createRuleFn != nil {
		return s.createRuleFn(ctx, input)
	}
	return &repository.AlertRule{
		ID:        uuid.New(),
		UserID:    input.UserID,
		Name:      input.Name,
		ZoneIDs:   input.ZoneIDs,
		Category:  input.Category,
		Filter:    input.Filter,
		Channels:  input.Channels,
		IsActive:  true,
		CreatedAt: time.Now().UTC(),
		UpdatedAt: time.Now().UTC(),
	}, nil
}

func (s *stubAlertRulesRepo) ListRules(context.Context, uuid.UUID, int, int, *bool) ([]repository.AlertRule, int, error) {
	return nil, 0, nil
}

func (s *stubAlertRulesRepo) GetRule(context.Context, uuid.UUID, uuid.UUID) (*repository.AlertRule, error) {
	return nil, repository.ErrNotFound
}

func (s *stubAlertRulesRepo) UpdateRule(context.Context, uuid.UUID, uuid.UUID, repository.UpdateRuleInput) (*repository.AlertRule, error) {
	return nil, repository.ErrNotFound
}

func (s *stubAlertRulesRepo) DeleteRule(context.Context, uuid.UUID, uuid.UUID) error {
	return nil
}

func (s *stubAlertRulesRepo) ValidateZoneIDs(ctx context.Context, zoneIDs []uuid.UUID) ([]uuid.UUID, error) {
	if s.validateZoneIDsFn != nil {
		return s.validateZoneIDsFn(ctx, zoneIDs)
	}
	return nil, nil
}

func (s *stubAlertRulesRepo) ListHistory(ctx context.Context, userID uuid.UUID, filter repository.HistoryFilter, page, pageSize int) ([]repository.AlertHistoryEntry, int, error) {
	if s.listHistoryFn != nil {
		return s.listHistoryFn(ctx, userID, filter, page, pageSize)
	}
	return nil, 0, nil
}

func TestValidateAlertFilter(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		category string
		filter   map[string]map[string]any
		want     []string
	}{
		{
			name:     "residential allows known field",
			category: "residential",
			filter:   map[string]map[string]any{"bedrooms": {"gte": 3}},
			want:     nil,
		},
		{
			name:     "residential rejects disallowed field",
			category: "residential",
			filter:   map[string]map[string]any{"loading_docks": {"gte": 1}},
			want:     []string{"loading_docks"},
		},
		{
			name:     "residential empty filter passes",
			category: "residential",
			filter:   map[string]map[string]any{},
			want:     nil,
		},
		{
			name:     "commercial allows known field",
			category: "commercial",
			filter:   map[string]map[string]any{"has_parking": {"eq": true}},
			want:     nil,
		},
		{
			name:     "commercial rejects disallowed field",
			category: "commercial",
			filter:   map[string]map[string]any{"bedrooms": {"gte": 3}},
			want:     []string{"bedrooms"},
		},
		{
			name:     "commercial empty filter passes",
			category: "commercial",
			filter:   map[string]map[string]any{},
			want:     nil,
		},
		{
			name:     "industrial allows known field",
			category: "industrial",
			filter:   map[string]map[string]any{"property_type": {"in": []string{"warehouse"}}},
			want:     nil,
		},
		{
			name:     "industrial rejects disallowed field",
			category: "industrial",
			filter:   map[string]map[string]any{"bedrooms": {"gte": 3}},
			want:     []string{"bedrooms"},
		},
		{
			name:     "industrial empty filter passes",
			category: "industrial",
			filter:   map[string]map[string]any{},
			want:     nil,
		},
		{
			name:     "land allows known field",
			category: "land",
			filter:   map[string]map[string]any{"area_m2": {"gte": 500}},
			want:     nil,
		},
		{
			name:     "land rejects disallowed field",
			category: "land",
			filter:   map[string]map[string]any{"has_parking": {"eq": true}},
			want:     []string{"has_parking"},
		},
		{
			name:     "land empty filter passes",
			category: "land",
			filter:   map[string]map[string]any{},
			want:     nil,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := validateAlertFilter(tc.category, tc.filter)
			if !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("validateAlertFilter() = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestCreateAlertRuleTierEnforcement(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name         string
		tier         string
		currentCount int
		wantStatus   int
	}{
		{name: "free tier blocked", tier: "free", currentCount: 0, wantStatus: http.StatusForbidden},
		{name: "basic below limit proceeds", tier: "basic", currentCount: 2, wantStatus: http.StatusCreated},
		{name: "basic at limit blocked", tier: "basic", currentCount: 3, wantStatus: http.StatusUnprocessableEntity},
		{name: "pro tier unlimited", tier: "pro", currentCount: 999, wantStatus: http.StatusCreated},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			repo := &stubAlertRulesRepo{
				countActiveRulesFn: func(context.Context, uuid.UUID) (int, error) {
					return tc.currentCount, nil
				},
			}
			handler := NewAlertRulesHandler(repo)

			reqBody := `{"name":"Berlin Apartments","zone_ids":["550e8400-e29b-41d4-a716-446655440000"],"category":"residential","filter":{"price_eur":{"lte":500000}},"channels":[{"type":"email"}]}`
			req := withAlertAuthContext(
				httptest.NewRequest(http.MethodPost, "/api/v1/alerts/rules", bytes.NewBufferString(reqBody)),
				uuid.MustParse("11111111-1111-1111-1111-111111111111"),
				tc.tier,
			)
			rec := httptest.NewRecorder()

			handler.CreateAlertRule(rec, req)

			if rec.Code != tc.wantStatus {
				t.Fatalf("status = %d, want %d", rec.Code, tc.wantStatus)
			}
		})
	}
}

func TestListAlertHistoryParsesFiltersAndPagination(t *testing.T) {
	t.Parallel()

	since := time.Date(2026, 4, 17, 12, 0, 0, 0, time.UTC)
	ruleID := uuid.MustParse("22222222-2222-2222-2222-222222222222")
	userID := uuid.MustParse("11111111-1111-1111-1111-111111111111")

	tests := []struct {
		name              string
		target            string
		wantPage          int
		wantPageSize      int
		wantRuleID        *uuid.UUID
		wantDeliveryState *string
		wantSince         *time.Time
	}{
		{
			name:         "defaults pagination",
			target:       "/api/v1/alerts/history",
			wantPage:     1,
			wantPageSize: 20,
		},
		{
			name:         "rule id filter",
			target:       "/api/v1/alerts/history?rule_id=" + ruleID.String(),
			wantPage:     1,
			wantPageSize: 20,
			wantRuleID:   &ruleID,
		},
		{
			name:              "delivery status filter",
			target:            "/api/v1/alerts/history?delivery_status=failed&page=2&page_size=5",
			wantPage:          2,
			wantPageSize:      5,
			wantDeliveryState: stringPtr("failed"),
		},
		{
			name:         "since filter",
			target:       "/api/v1/alerts/history?since=" + since.Format(time.RFC3339),
			wantPage:     1,
			wantPageSize: 20,
			wantSince:    &since,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			repo := &stubAlertRulesRepo{
				listHistoryFn: func(_ context.Context, gotUserID uuid.UUID, filter repository.HistoryFilter, page, pageSize int) ([]repository.AlertHistoryEntry, int, error) {
					if gotUserID != userID {
						t.Fatalf("userID = %s, want %s", gotUserID, userID)
					}
					if page != tc.wantPage {
						t.Fatalf("page = %d, want %d", page, tc.wantPage)
					}
					if pageSize != tc.wantPageSize {
						t.Fatalf("pageSize = %d, want %d", pageSize, tc.wantPageSize)
					}
					if !reflect.DeepEqual(filter.RuleID, tc.wantRuleID) {
						t.Fatalf("filter.RuleID = %v, want %v", filter.RuleID, tc.wantRuleID)
					}
					if !reflect.DeepEqual(filter.DeliveryStatus, tc.wantDeliveryState) {
						t.Fatalf("filter.DeliveryStatus = %v, want %v", filter.DeliveryStatus, tc.wantDeliveryState)
					}
					if !timesEqual(filter.Since, tc.wantSince) {
						t.Fatalf("filter.Since = %v, want %v", filter.Since, tc.wantSince)
					}

					return []repository.AlertHistoryEntry{
						{
							ID:             uuid.New(),
							RuleID:         ruleID,
							RuleName:       "Berlin Apartments",
							ListingID:      uuid.New(),
							TriggeredAt:    since,
							Channel:        "email",
							DeliveryStatus: "delivered",
						},
					}, 1, nil
				},
			}
			handler := NewAlertRulesHandler(repo)
			req := withAlertAuthContext(httptest.NewRequest(http.MethodGet, tc.target, nil), userID, "pro")
			rec := httptest.NewRecorder()

			handler.ListAlertHistory(rec, req)

			if rec.Code != http.StatusOK {
				t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
			}

			var payload map[string]any
			if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
				t.Fatalf("Unmarshal() error = %v", err)
			}
			data, ok := payload["data"].([]any)
			if !ok || len(data) != 1 {
				t.Fatalf("data = %v, want one history entry", payload["data"])
			}
		})
	}
}

func TestListAlertHistoryUsesAuthenticatedUserScope(t *testing.T) {
	t.Parallel()

	userA := uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	userB := uuid.MustParse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
	repo := &stubAlertRulesRepo{
		listHistoryFn: func(_ context.Context, userID uuid.UUID, _ repository.HistoryFilter, _ int, _ int) ([]repository.AlertHistoryEntry, int, error) {
			return []repository.AlertHistoryEntry{
				{
					ID:             uuid.New(),
					RuleID:         uuid.New(),
					RuleName:       userID.String(),
					ListingID:      uuid.New(),
					TriggeredAt:    time.Now().UTC(),
					Channel:        "email",
					DeliveryStatus: "delivered",
				},
			}, 1, nil
		},
	}
	handler := NewAlertRulesHandler(repo)

	reqA := withAlertAuthContext(httptest.NewRequest(http.MethodGet, "/api/v1/alerts/history", nil), userA, "pro")
	recA := httptest.NewRecorder()
	handler.ListAlertHistory(recA, reqA)

	reqB := withAlertAuthContext(httptest.NewRequest(http.MethodGet, "/api/v1/alerts/history", nil), userB, "pro")
	recB := httptest.NewRecorder()
	handler.ListAlertHistory(recB, reqB)

	var payloadA map[string]any
	if err := json.Unmarshal(recA.Body.Bytes(), &payloadA); err != nil {
		t.Fatalf("Unmarshal(recA) error = %v", err)
	}
	var payloadB map[string]any
	if err := json.Unmarshal(recB.Body.Bytes(), &payloadB); err != nil {
		t.Fatalf("Unmarshal(recB) error = %v", err)
	}

	nameA := payloadA["data"].([]any)[0].(map[string]any)["rule_name"]
	nameB := payloadB["data"].([]any)[0].(map[string]any)["rule_name"]
	if nameA == nameB {
		t.Fatalf("rule_name for user A and user B matched (%v), want user-scoped results", nameA)
	}
}

func withAlertAuthContext(req *http.Request, userID uuid.UUID, tier string) *http.Request {
	ctx := context.WithValue(req.Context(), ctxkey.UserID, userID.String())
	ctx = context.WithValue(ctx, ctxkey.UserTier, tier)
	return req.WithContext(ctx)
}

func stringPtr(value string) *string {
	return &value
}

func timesEqual(a, b *time.Time) bool {
	switch {
	case a == nil && b == nil:
		return true
	case a == nil || b == nil:
		return false
	default:
		return a.UTC().Equal(b.UTC())
	}
}
