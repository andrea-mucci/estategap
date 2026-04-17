package grpcserver

import (
	"context"
	"strings"
	"time"

	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"github.com/estategap/services/proxy-manager/internal/blacklist"
	"github.com/estategap/services/proxy-manager/internal/metrics"
	"github.com/estategap/services/proxy-manager/internal/pool"
	"github.com/estategap/services/proxy-manager/internal/redisclient"
	"github.com/estategap/services/proxy-manager/internal/sticky"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type Server struct {
	estategapv1.UnimplementedProxyServiceServer

	redisClient  *redisclient.Client
	pool         *pool.ProxyPool
	blacklist    *blacklist.Blacklist
	sticky       *sticky.Sticky
	blacklistTTL time.Duration
}

func NewServer(redisClient *redisclient.Client, proxyPool *pool.ProxyPool, bl *blacklist.Blacklist, stickyStore *sticky.Sticky, blacklistTTL time.Duration) *Server {
	return &Server{
		redisClient:  redisClient,
		pool:         proxyPool,
		blacklist:    bl,
		sticky:       stickyStore,
		blacklistTTL: blacklistTTL,
	}
}

func (s *Server) GetProxy(ctx context.Context, req *estategapv1.GetProxyRequest) (*estategapv1.GetProxyResponse, error) {
	country := strings.ToUpper(strings.TrimSpace(req.GetCountryCode()))
	if country == "" {
		return nil, status.Error(codes.InvalidArgument, "country_code is required")
	}

	selected, err := s.pool.Select(ctx, country, s.redisClient, s.blacklist, req.GetSessionId(), s.sticky)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}

	return &estategapv1.GetProxyResponse{
		ProxyUrl: selected.Adapter.BuildProxyURL(selected.Username, selected.Password, selected.Endpoint, req.GetSessionId()),
		ProxyId:  selected.ID,
	}, nil
}

func (s *Server) ReportResult(ctx context.Context, req *estategapv1.ReportResultRequest) (*estategapv1.ReportResultResponse, error) {
	proxyID := strings.TrimSpace(req.GetProxyId())
	if proxyID == "" {
		return nil, status.Error(codes.InvalidArgument, "proxy_id is required")
	}

	selected, ok := s.pool.GetByID(proxyID)
	if !ok {
		return nil, status.Error(codes.NotFound, "proxy not found")
	}

	selected.Health.Record(req.GetSuccess())
	if req.GetStatusCode() == 403 || req.GetStatusCode() == 429 {
		if err := s.blacklist.Blacklist(ctx, selected.Host(), s.blacklistTTL); err != nil {
			return nil, status.Errorf(codes.Internal, "blacklist proxy: %v", err)
		}
	}

	total, healthy, blocked, err := s.pool.Stats(ctx, s.blacklist, selected.Country, selected.Provider)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "update metrics: %v", err)
	}
	blockRatio := 0.0
	if total > 0 {
		blockRatio = float64(blocked) / float64(total)
	}
	metrics.Update(selected.Country, selected.Provider, total, healthy, blockRatio)

	return &estategapv1.ReportResultResponse{Acknowledged: true}, nil
}
