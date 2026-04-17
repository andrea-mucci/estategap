package handler

import (
	"context"
	"encoding/json"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/estategap/libs/models"
	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	grpcclient "github.com/estategap/services/api-gateway/internal/grpc"
	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
)

type stubListingReader struct {
	listing *models.Listing
	err     error
}

func (s *stubListingReader) GetListingByID(_ context.Context, _ uuid.UUID) (*models.Listing, error) {
	if s.err != nil {
		return nil, s.err
	}
	return s.listing, nil
}

type mlScorerFunc func(ctx context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error)

func (f mlScorerFunc) ScoreListing(ctx context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
	return f(ctx, req)
}

type testMLScoringServer struct {
	estategapv1.UnimplementedMLScoringServiceServer
	scoreFn func(ctx context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error)
}

func (s *testMLScoringServer) ScoreListing(ctx context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
	return s.scoreFn(ctx, req)
}

func TestMLHandlerEstimate(t *testing.T) {
	t.Parallel()

	listingID := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	handler := NewMLHandler(
		newBufconnMLScorer(t, func(_ context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
			if req.GetListingId() != listingID.String() {
				return nil, status.Errorf(codes.InvalidArgument, "unexpected listing_id %s", req.GetListingId())
			}
			return &estategapv1.ScoreListingResponse{
				ListingId: listingID.String(),
				DealScore: 87,
				ShapValues: []*estategapv1.ShapValue{
					{FeatureName: "price_eur", Contribution: 0.42},
				},
				ModelVersion: "v2.3.1-de",
			}, nil
		}),
		&stubListingReader{
			listing: &models.Listing{
				Country:        "DE",
				EstimatedPrice: decimalPtr("487500"),
			},
		},
		5*time.Second,
	)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/model/estimate?listing_id="+listingID.String(), nil)
	rec := httptest.NewRecorder()

	handler.Estimate(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
	}

	var payload map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("Unmarshal() error = %v", err)
	}

	if got := payload["listing_id"]; got != listingID.String() {
		t.Fatalf("listing_id = %v, want %q", got, listingID.String())
	}
	if got := payload["currency"]; got != "EUR" {
		t.Fatalf("currency = %v, want %q", got, "EUR")
	}
	if got := payload["model_version"]; got != "v2.3.1-de" {
		t.Fatalf("model_version = %v, want %q", got, "v2.3.1-de")
	}
}

func TestMLHandlerEstimateUnavailable(t *testing.T) {
	t.Parallel()

	listingID := uuid.New()
	handler := NewMLHandler(
		newBufconnMLScorer(t, func(_ context.Context, _ *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
			return nil, status.Error(codes.Unavailable, "ml scorer down")
		}),
		&stubListingReader{listing: &models.Listing{Country: "DE"}},
		50*time.Millisecond,
	)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/model/estimate?listing_id="+listingID.String(), nil)
	rec := httptest.NewRecorder()

	handler.Estimate(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusServiceUnavailable)
	}
	if body := rec.Body.String(); !strings.Contains(body, "ML_SCORER_UNAVAILABLE") {
		t.Fatalf("body = %s, want ML_SCORER_UNAVAILABLE", body)
	}
}

func TestMLHandlerEstimateTimeout(t *testing.T) {
	t.Parallel()

	listingID := uuid.New()
	handler := NewMLHandler(
		newBufconnMLScorer(t, func(ctx context.Context, _ *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
			<-ctx.Done()
			return nil, status.Error(codes.DeadlineExceeded, ctx.Err().Error())
		}),
		&stubListingReader{listing: &models.Listing{Country: "DE"}},
		10*time.Millisecond,
	)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/model/estimate?listing_id="+listingID.String(), nil)
	rec := httptest.NewRecorder()

	handler.Estimate(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusServiceUnavailable)
	}
}

func TestMLHandlerEstimateInvalidUUID(t *testing.T) {
	t.Parallel()

	handler := NewMLHandler(mlScorerFunc(func(context.Context, *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
		t.Fatal("ScoreListing should not be called for invalid UUID")
		return nil, nil
	}), &stubListingReader{}, time.Second)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/model/estimate?listing_id=not-a-uuid", nil)
	rec := httptest.NewRecorder()

	handler.Estimate(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusBadRequest)
	}
}

func TestMLHandlerEstimateCircuitBreakerOpen(t *testing.T) {
	t.Parallel()

	listingID := uuid.New()
	scorer := &circuitBreakingScorer{
		cb: grpcclient.NewCircuitBreaker(5, 30, 30),
	}
	handler := NewMLHandler(
		scorer,
		&stubListingReader{listing: &models.Listing{Country: "DE"}},
		time.Second,
	)

	for i := 0; i < 6; i++ {
		req := httptest.NewRequest(http.MethodGet, "/api/v1/model/estimate?listing_id="+listingID.String(), nil)
		rec := httptest.NewRecorder()
		handler.Estimate(rec, req)

		if rec.Code != http.StatusServiceUnavailable {
			t.Fatalf("request %d status = %d, want %d", i+1, rec.Code, http.StatusServiceUnavailable)
		}
	}

	if scorer.hits != 5 {
		t.Fatalf("upstream hits = %d, want 5 before breaker opens", scorer.hits)
	}
}

type circuitBreakingScorer struct {
	cb   *grpcclient.CircuitBreaker
	hits int
}

func (s *circuitBreakingScorer) ScoreListing(_ context.Context, _ *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
	if !s.cb.Allow() {
		return nil, grpcclient.ErrCircuitBreakerOpen
	}
	s.hits++
	s.cb.RecordFailure()
	return nil, status.Error(codes.Unavailable, "ml scorer down")
}

func newBufconnMLScorer(t *testing.T, scoreFn func(context.Context, *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error)) MLScorer {
	t.Helper()

	listener := bufconn.Listen(1 << 20)
	server := grpc.NewServer()
	estategapv1.RegisterMLScoringServiceServer(server, &testMLScoringServer{scoreFn: scoreFn})

	go func() {
		_ = server.Serve(listener)
	}()

	t.Cleanup(func() {
		server.Stop()
		_ = listener.Close()
	})

	conn, err := grpc.DialContext(
		context.Background(),
		"bufnet",
		grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) {
			return listener.Dial()
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("DialContext() error = %v", err)
	}

	t.Cleanup(func() {
		_ = conn.Close()
	})

	client := estategapv1.NewMLScoringServiceClient(conn)
	return mlScorerFunc(func(ctx context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
		return client.ScoreListing(ctx, req)
	})
}

func decimalPtr(value string) *decimal.Decimal {
	decimalValue := decimal.RequireFromString(value)
	return &decimalValue
}
