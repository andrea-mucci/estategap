package grpcserver

import (
	"context"
	"strings"
	"testing"
	"time"

	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"github.com/estategap/services/proxy-manager/internal/blacklist"
	"github.com/estategap/services/proxy-manager/internal/pool"
	"github.com/estategap/services/proxy-manager/internal/sticky"
)

func TestServerGetProxyAndStickySession(t *testing.T) {
	t.Parallel()

	proxyPool := pool.New(0.5)
	first := proxyForServer("proxy-1", "IT", "brightdata", "10.0.0.1:8000")
	second := proxyForServer("proxy-2", "IT", "brightdata", "10.0.0.2:8000")
	proxyPool.LoadForTest("IT", first, second)

	server := NewServer(nil, proxyPool, blacklist.New(nil), sticky.New(nil, time.Minute), time.Minute)

	firstResp, err := server.GetProxy(context.Background(), &estategapv1.GetProxyRequest{
		CountryCode: "IT",
		SessionId:   "session-1",
	})
	if err != nil {
		t.Fatalf("GetProxy() error = %v", err)
	}
	secondResp, err := server.GetProxy(context.Background(), &estategapv1.GetProxyRequest{
		CountryCode: "IT",
		SessionId:   "session-1",
	})
	if err != nil {
		t.Fatalf("GetProxy() error = %v", err)
	}

	if firstResp.ProxyId != secondResp.ProxyId {
		t.Fatalf("sticky GetProxy() returned %q then %q", firstResp.ProxyId, secondResp.ProxyId)
	}
	if !strings.Contains(firstResp.ProxyUrl, "session-1") {
		t.Fatalf("expected sticky session in proxy URL, got %q", firstResp.ProxyUrl)
	}
}

func TestServerReportResultBlacklistsProxy(t *testing.T) {
	t.Parallel()

	proxyPool := pool.New(0.5)
	first := proxyForServer("proxy-1", "IT", "brightdata", "10.0.0.1:8000")
	second := proxyForServer("proxy-2", "IT", "brightdata", "10.0.0.2:8000")
	proxyPool.LoadForTest("IT", first, second)

	bl := blacklist.New(nil)
	server := NewServer(nil, proxyPool, bl, sticky.New(nil, time.Minute), time.Minute)

	if _, err := server.ReportResult(context.Background(), &estategapv1.ReportResultRequest{
		ProxyId:    first.ID,
		Success:    false,
		StatusCode: 429,
	}); err != nil {
		t.Fatalf("ReportResult() error = %v", err)
	}

	resp, err := server.GetProxy(context.Background(), &estategapv1.GetProxyRequest{CountryCode: "IT"})
	if err != nil {
		t.Fatalf("GetProxy() error = %v", err)
	}
	if resp.ProxyId == first.ID {
		t.Fatalf("expected blacklisted proxy %q to be skipped", first.ID)
	}
}

func proxyForServer(id, country, providerName, endpoint string) *pool.Proxy {
	return &pool.Proxy{
		ID:       id,
		Country:  country,
		Provider: providerName,
		Endpoint: endpoint,
		Username: "user",
		Password: "pass",
		Adapter:  providerForTest(providerName),
		Health:   &pool.HealthWindow{},
	}
}

type providerForTest string

func (p providerForTest) BuildProxyURL(username, password, endpoint, sessionID string) string {
	if sessionID != "" {
		return "http://" + username + "-session-" + sessionID + ":" + password + "@" + endpoint
	}
	return "http://" + username + ":" + password + "@" + endpoint
}

func (p providerForTest) Name() string { return string(p) }
