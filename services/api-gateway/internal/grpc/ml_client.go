package grpc

import (
	"context"
	"crypto/tls"
	"errors"
	"os"
	"strings"
	"time"

	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

const retryServiceConfigJSON = `{"methodConfig":[{"name":[{"service":""}],"retryPolicy":{"maxAttempts":4,"initialBackoff":"0.1s","maxBackoff":"1s","backoffMultiplier":2.0,"retryableStatusCodes":["UNAVAILABLE"]},"timeout":"5s"}]}`

var ErrCircuitBreakerOpen = status.Error(codes.Unavailable, "ml circuit breaker open")

type MLClientConfig struct {
	Target      string
	Timeout     time.Duration
	CBThreshold int
	CBWindow    time.Duration
	CBCooldown  time.Duration
}

type MLClient struct {
	conn    *grpc.ClientConn
	client  estategapv1.MLScoringServiceClient
	timeout time.Duration
	cb      *CircuitBreaker
}

func NewMLClient(cfg MLClientConfig) (*MLClient, error) {
	conn, err := grpc.NewClient(cfg.Target, clientDialOptions(cfg.Target)...)
	if err != nil {
		return nil, err
	}

	return &MLClient{
		conn:    conn,
		client:  estategapv1.NewMLScoringServiceClient(conn),
		timeout: cfg.Timeout,
		cb:      NewCircuitBreaker(cfg.CBThreshold, int64(cfg.CBWindow/time.Second), int64(cfg.CBCooldown/time.Second)),
	}, nil
}

func (c *MLClient) ScoreListing(ctx context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
	if c.cb != nil && !c.cb.Allow() {
		return nil, ErrCircuitBreakerOpen
	}

	callCtx := ctx
	if c.timeout > 0 {
		var cancel context.CancelFunc
		callCtx, cancel = context.WithTimeout(ctx, c.timeout)
		defer cancel()
	}

	resp, err := c.client.ScoreListing(callCtx, req)
	if err != nil {
		if c.cb != nil {
			if isMLTransportFailure(err) {
				c.cb.RecordFailure()
			} else {
				c.cb.RecordSuccess()
			}
		}
		return nil, err
	}

	if c.cb != nil {
		c.cb.RecordSuccess()
	}
	return resp, nil
}

func (c *MLClient) Close() error {
	return c.conn.Close()
}

func clientDialOptions(target string) []grpc.DialOption {
	return []grpc.DialOption{
		grpc.WithTransportCredentials(transportCredentials(target)),
		grpc.WithDefaultServiceConfig(retryServiceConfigJSON),
	}
}

func transportCredentials(target string) credentials.TransportCredentials {
	if os.Getenv("CLUSTER_ENVIRONMENT") == "production" || strings.HasSuffix(target, ":443") {
		return credentials.NewTLS(&tls.Config{MinVersion: tls.VersionTLS12})
	}
	return insecure.NewCredentials()
}

func isMLTransportFailure(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return true
	}

	switch status.Code(err) {
	case codes.Unavailable, codes.DeadlineExceeded:
		return true
	default:
		return false
	}
}
