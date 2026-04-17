//go:build integration

package integration

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"github.com/estategap/services/ws-server/internal/config"
	grpcclient "github.com/estategap/services/ws-server/internal/grpc"
	"github.com/estategap/services/ws-server/internal/handler"
	"github.com/estategap/services/ws-server/internal/hub"
	"github.com/estategap/services/ws-server/internal/metrics"
	wsnats "github.com/estategap/services/ws-server/internal/nats"
	"github.com/estategap/services/ws-server/internal/protocol"
	"github.com/golang-jwt/jwt/v5"
	"github.com/gorilla/websocket"
	"github.com/nats-io/nats.go"
	"github.com/prometheus/client_golang/prometheus/testutil"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
	ggrpc "google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
)

type fakeChatServer struct {
	estategapv1.UnimplementedAIChatServiceServer
	mu        sync.Mutex
	requests  []*estategapv1.ChatRequest
	metadata  metadata.MD
	responses []*estategapv1.ChatResponse
}

func (s *fakeChatServer) Chat(stream ggrpc.BidiStreamingServer[estategapv1.ChatRequest, estategapv1.ChatResponse]) error {
	md, _ := metadata.FromIncomingContext(stream.Context())
	req, err := stream.Recv()
	if err != nil {
		return err
	}

	s.mu.Lock()
	s.requests = append(s.requests, req)
	s.metadata = md
	responses := append([]*estategapv1.ChatResponse(nil), s.responses...)
	s.mu.Unlock()

	for _, resp := range responses {
		if err := stream.Send(resp); err != nil {
			return err
		}
	}
	return nil
}

type noopChatClient struct{}

func (noopChatClient) OpenChatStream(context.Context, string, string, string, string, string, func([]byte)) error {
	return nil
}

func TestChatStreamingIntegration(t *testing.T) {
	fakeServer := &fakeChatServer{
		responses: []*estategapv1.ChatResponse{
			{ConversationId: "session-1", Chunk: "Hello", IsFinal: false},
			{ConversationId: "session-1", Chunk: " from", IsFinal: false},
			{ConversationId: "session-1", Chunk: " ws-server", IsFinal: false},
			{ConversationId: "session-1", Chunk: "", IsFinal: true},
		},
	}
	grpcAddr, stopGRPC := startGRPCServer(t, fakeServer)
	defer stopGRPC()

	grpcConn, err := ggrpc.NewClient(
		grpcAddr,
		ggrpc.WithTransportCredentials(insecure.NewCredentials()),
		ggrpc.WithDefaultCallOptions(ggrpc.WaitForReady(true)),
	)
	if err != nil {
		t.Fatalf("create grpc client: %v", err)
	}
	defer grpcConn.Close()

	cfg := testConfig()
	cfg.AIChatGRPCAddr = grpcAddr

	serverURL, cleanup := startWSServer(t, cfg, grpcclient.New(grpcConn))
	defer cleanup()

	before := testutil.ToFloat64(metrics.MessagesSentTotal.WithLabelValues("text_chunk"))
	conn := connectWS(t, serverURL, cfg.JWTSecret)
	defer conn.Close()

	if err := conn.WriteJSON(protocol.Envelope{
		Type:      "chat_message",
		SessionID: "",
		Payload: mustRawJSON(t, protocol.ChatMessagePayload{
			UserMessage: "find flats",
			CountryCode: "IT",
		}),
	}); err != nil {
		t.Fatalf("write chat_message: %v", err)
	}

	var chunks []protocol.TextChunkPayload
	for i := 0; i < 4; i++ {
		env := readEnvelope(t, conn)
		if env.Type != "text_chunk" {
			t.Fatalf("message type = %s, want text_chunk", env.Type)
		}
		var payload protocol.TextChunkPayload
		if err := json.Unmarshal(env.Payload, &payload); err != nil {
			t.Fatalf("unmarshal payload: %v", err)
		}
		chunks = append(chunks, payload)
	}

	if len(chunks) != 4 || !chunks[3].IsFinal {
		t.Fatalf("unexpected chunk stream: %+v", chunks)
	}
	after := testutil.ToFloat64(metrics.MessagesSentTotal.WithLabelValues("text_chunk"))
	if after <= before {
		t.Fatalf("expected ws_messages_sent_total{text_chunk} to increase")
	}

	fakeServer.mu.Lock()
	defer fakeServer.mu.Unlock()
	if got := fakeServer.metadata.Get("x-user-id"); len(got) == 0 || got[0] != "user-123" {
		t.Fatalf("missing x-user-id metadata: %#v", fakeServer.metadata)
	}
	if got := fakeServer.metadata.Get("x-subscription-tier"); len(got) == 0 || got[0] != "pro_plus" {
		t.Fatalf("missing x-subscription-tier metadata: %#v", fakeServer.metadata)
	}
}

func TestDealAlertIntegration(t *testing.T) {
	ctx := context.Background()
	natsContainer, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "nats:2.10-alpine",
			ExposedPorts: []string{"4222/tcp"},
			Cmd:          []string{"-js"},
			WaitingFor:   wait.ForListeningPort("4222/tcp"),
		},
		Started: true,
	})
	if err != nil {
		t.Fatalf("start nats container: %v", err)
	}
	defer testcontainers.TerminateContainer(natsContainer)

	host, _ := natsContainer.Host(ctx)
	port, _ := natsContainer.MappedPort(ctx, "4222/tcp")
	natsURL := fmt.Sprintf("nats://%s:%s", host, port.Port())

	natsConn, err := nats.Connect(natsURL)
	if err != nil {
		t.Fatalf("connect nats: %v", err)
	}
	defer natsConn.Close()

	js, err := natsConn.JetStream()
	if err != nil {
		t.Fatalf("jetstream: %v", err)
	}
	if _, err := js.AddStream(&nats.StreamConfig{
		Name:     "ALERTS",
		Subjects: []string{"alerts.notifications.>"},
	}); err != nil {
		t.Fatalf("add alerts stream: %v", err)
	}

	cfg := testConfig()
	cfg.NATSAddr = natsURL

	h := hub.New(cfg.MaxConnections)
	consumer := wsnats.New(js, h, cfg)
	if err := consumer.Setup(); err != nil {
		t.Fatalf("consumer setup: %v", err)
	}

	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	go func() {
		_ = consumer.Start(runCtx)
	}()
	defer consumer.Stop()

	wsHandler := handler.NewWSHandler(h, noopChatClient{}, cfg, nil)
	server := httptest.NewServer(wsHandler)
	defer server.Close()

	conn := connectWS(t, websocketURL(server.URL), cfg.JWTSecret)
	defer conn.Close()

	payload, err := json.Marshal(map[string]any{
		"event_id":   "event-1",
		"user_id":    "user-123",
		"rule_name":  "Best deals",
		"listing_id": "listing-1",
		"deal_score": 0.91,
		"deal_tier":  1,
		"listing_summary": map[string]any{
			"title":        "Great flat",
			"price_eur":    250000,
			"area_m2":      82,
			"city":         "Milan",
			"image_url":    "https://example.com/photo.jpg",
			"address":      "Milan",
			"analysis_url": "https://example.com/analysis",
		},
		"triggered_at": time.Now().UTC().Format(time.RFC3339),
	})
	if err != nil {
		t.Fatalf("marshal event: %v", err)
	}
	if _, err := js.Publish("alerts.notifications.IT", payload); err != nil {
		t.Fatalf("publish event: %v", err)
	}

	env := readEnvelope(t, conn)
	if env.Type != "deal_alert" {
		t.Fatalf("message type = %s, want deal_alert", env.Type)
	}

	var alert protocol.DealAlertPayload
	if err := json.Unmarshal(env.Payload, &alert); err != nil {
		t.Fatalf("unmarshal deal alert: %v", err)
	}
	if alert.ListingID != "listing-1" || alert.DealScore != 0.91 {
		t.Fatalf("unexpected alert payload: %+v", alert)
	}
}

func TestConnectionKeepaliveAndIdleTimeout(t *testing.T) {
	cfg := testConfig()
	cfg.PingInterval = 100 * time.Millisecond
	cfg.PongTimeout = 100 * time.Millisecond
	cfg.IdleTimeout = 250 * time.Millisecond

	serverURL, cleanup := startWSServer(t, cfg, noopChatClient{})
	defer cleanup()

	t.Run("missed pong closes connection", func(t *testing.T) {
		conn := connectWS(t, serverURL, cfg.JWTSecret)
		defer conn.Close()

		var pingCount atomic.Int32
		respondToPing := atomic.Bool{}
		respondToPing.Store(true)
		readErrCh := make(chan error, 1)

		conn.SetPingHandler(func(appData string) error {
			pingCount.Add(1)
			if respondToPing.Load() {
				return conn.WriteControl(websocket.PongMessage, []byte(appData), time.Now().Add(time.Second))
			}
			return nil
		})

		go func() {
			for {
				if _, _, err := conn.ReadMessage(); err != nil {
					readErrCh <- err
					return
				}
			}
		}()

		deadline := time.Now().Add(500 * time.Millisecond)
		for time.Now().Before(deadline) && pingCount.Load() < 2 {
			time.Sleep(10 * time.Millisecond)
		}
		if pingCount.Load() < 2 {
			t.Fatalf("expected at least two ping frames, got %d", pingCount.Load())
		}

		respondToPing.Store(false)
		select {
		case err := <-readErrCh:
			if websocket.CloseStatus(err) != websocket.CloseGoingAway {
				t.Fatalf("close status = %d, want %d", websocket.CloseStatus(err), websocket.CloseGoingAway)
			}
		case <-time.After(500 * time.Millisecond):
			t.Fatal("expected websocket close after missed pong")
		}
	})

	t.Run("idle timeout closes even when pongs continue", func(t *testing.T) {
		conn := connectWS(t, serverURL, cfg.JWTSecret)
		defer conn.Close()

		readErrCh := make(chan error, 1)
		conn.SetPingHandler(func(appData string) error {
			return conn.WriteControl(websocket.PongMessage, []byte(appData), time.Now().Add(time.Second))
		})

		go func() {
			for {
				if _, _, err := conn.ReadMessage(); err != nil {
					readErrCh <- err
					return
				}
			}
		}()

		select {
		case err := <-readErrCh:
			if websocket.CloseStatus(err) != websocket.CloseGoingAway {
				t.Fatalf("close status = %d, want %d", websocket.CloseStatus(err), websocket.CloseGoingAway)
			}
		case <-time.After(700 * time.Millisecond):
			t.Fatal("expected websocket close after idle timeout")
		}
	})
}

func startGRPCServer(t *testing.T, srv estategapv1.AIChatServiceServer) (string, func()) {
	t.Helper()

	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen grpc: %v", err)
	}

	server := ggrpc.NewServer()
	estategapv1.RegisterAIChatServiceServer(server, srv)
	go func() {
		_ = server.Serve(listener)
	}()

	return listener.Addr().String(), func() {
		server.Stop()
		_ = listener.Close()
	}
}

func startWSServer(t *testing.T, cfg *config.Config, chatClient protocol.ChatStreamer) (string, func()) {
	t.Helper()

	wsHandler := handler.NewWSHandler(hub.New(cfg.MaxConnections), chatClient, cfg, nil)
	server := httptest.NewServer(wsHandler)
	return websocketURL(server.URL), server.Close
}

func connectWS(t *testing.T, serverURL, secret string) *websocket.Conn {
	t.Helper()

	conn, resp, err := websocket.DefaultDialer.Dial(serverURL+"?token="+signedToken(t, secret), nil)
	if err != nil {
		if resp != nil {
			defer resp.Body.Close()
			body, _ := io.ReadAll(resp.Body)
			t.Fatalf("dial websocket: %v (status=%d body=%s)", err, resp.StatusCode, body)
		}
		t.Fatalf("dial websocket: %v", err)
	}
	return conn
}

func signedToken(t *testing.T, secret string) string {
	t.Helper()

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"sub":   "user-123",
		"tier":  "pro_plus",
		"email": "user@example.com",
		"jti":   "token-123",
		"exp":   time.Now().Add(time.Hour).Unix(),
		"iat":   time.Now().Add(-time.Minute).Unix(),
	})
	signed, err := token.SignedString([]byte(secret))
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return signed
}

func mustRawJSON(t *testing.T, payload any) json.RawMessage {
	t.Helper()
	raw, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}
	return raw
}

func readEnvelope(t *testing.T, conn *websocket.Conn) protocol.Envelope {
	t.Helper()

	if err := conn.SetReadDeadline(time.Now().Add(5 * time.Second)); err != nil {
		t.Fatalf("set read deadline: %v", err)
	}

	var env protocol.Envelope
	if err := conn.ReadJSON(&env); err != nil {
		t.Fatalf("read websocket message: %v", err)
	}
	return env
}

func websocketURL(httpURL string) string {
	return "ws" + strings.TrimPrefix(httpURL, "http")
}

func testConfig() *config.Config {
	return &config.Config{
		Port:            8081,
		JWTSecret:       "test-secret",
		RedisAddr:       "localhost:6379",
		AIChatGRPCAddr:  "127.0.0.1:50053",
		NATSAddr:        "nats://localhost:4222",
		MaxConnections:  100,
		PingInterval:    time.Second,
		PongTimeout:     time.Second,
		IdleTimeout:     time.Minute,
		ShutdownTimeout: 2 * time.Second,
		NATSWorkers:     1,
		LogLevel:        "DEBUG",
	}
}
