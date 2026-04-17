package unit

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/estategap/services/ws-server/internal/config"
	"github.com/estategap/services/ws-server/internal/handler"
	"github.com/estategap/services/ws-server/internal/hub"
	"github.com/golang-jwt/jwt/v5"
	"github.com/gorilla/websocket"
)

type noopChatClient struct{}

func (noopChatClient) OpenChatStream(context.Context, string, string, string, string, string, func([]byte)) error {
	return nil
}

func TestWSHandlerRejectsUnauthorizedRequests(t *testing.T) {
	cfg := &config.Config{
		JWTSecret:      "test-secret",
		MaxConnections: 2,
		PingInterval:   time.Second,
		PongTimeout:    time.Second,
		IdleTimeout:    time.Minute,
	}

	wsHandler := handler.NewWSHandler(hub.New(cfg.MaxConnections), noopChatClient{}, cfg, nil)
	server := httptest.NewServer(wsHandler)
	defer server.Close()

	baseURL := websocketURL(server.URL)
	tests := []struct {
		name     string
		token    string
		wantCode int
		wantBody string
	}{
		{
			name:     "missing token",
			wantCode: http.StatusUnauthorized,
			wantBody: `"reason":"missing token"`,
		},
		{
			name:     "expired token",
			token:    signedToken(t, cfg.JWTSecret, time.Now().Add(-time.Minute)),
			wantCode: http.StatusUnauthorized,
			wantBody: `"reason":"expired token"`,
		},
		{
			name:     "tampered token",
			token:    signedToken(t, cfg.JWTSecret, time.Now().Add(time.Hour)) + "tampered",
			wantCode: http.StatusUnauthorized,
			wantBody: `"reason":"invalid signature"`,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			url := baseURL
			if tc.token != "" {
				url += "?token=" + tc.token
			}

			conn, resp, err := websocket.DefaultDialer.Dial(url, nil)
			if conn != nil {
				_ = conn.Close()
			}
			if err == nil {
				t.Fatal("expected websocket dial to fail")
			}
			if resp == nil {
				t.Fatal("expected HTTP response")
			}
			if resp.StatusCode != tc.wantCode {
				t.Fatalf("status code = %d, want %d", resp.StatusCode, tc.wantCode)
			}
			body := readBody(t, resp)
			if !strings.Contains(body, tc.wantBody) {
				t.Fatalf("response body %q does not contain %q", body, tc.wantBody)
			}
		})
	}
}

func TestWSHandlerRejectsAtCapacity(t *testing.T) {
	cfg := &config.Config{
		JWTSecret:      "test-secret",
		MaxConnections: 1,
		PingInterval:   time.Second,
		PongTimeout:    time.Second,
		IdleTimeout:    time.Minute,
	}

	h := hub.New(cfg.MaxConnections)
	if err := h.Register(hub.NewConnection("already-connected", "basic", nil, cfg)); err != nil {
		t.Fatalf("seed hub capacity: %v", err)
	}

	wsHandler := handler.NewWSHandler(h, noopChatClient{}, cfg, nil)
	server := httptest.NewServer(wsHandler)
	defer server.Close()

	conn, resp, err := websocket.DefaultDialer.Dial(
		websocketURL(server.URL)+"?token="+signedToken(t, cfg.JWTSecret, time.Now().Add(time.Hour)),
		nil,
	)
	if conn != nil {
		_ = conn.Close()
	}
	if err == nil {
		t.Fatal("expected websocket dial to fail")
	}
	if resp == nil {
		t.Fatal("expected HTTP response")
	}
	if resp.StatusCode != http.StatusServiceUnavailable {
		t.Fatalf("status code = %d, want %d", resp.StatusCode, http.StatusServiceUnavailable)
	}
	if got := resp.Header.Get("Retry-After"); got != "5" {
		t.Fatalf("Retry-After = %q, want 5", got)
	}
	body := readBody(t, resp)
	if !strings.Contains(body, `"reason":"connection limit reached"`) {
		t.Fatalf("response body %q missing capacity reason", body)
	}
}

func signedToken(t *testing.T, secret string, expiresAt time.Time) string {
	t.Helper()

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"sub":   "user-123",
		"tier":  "pro_plus",
		"email": "user@example.com",
		"jti":   "token-123",
		"exp":   expiresAt.Unix(),
		"iat":   time.Now().Add(-time.Minute).Unix(),
	})
	signed, err := token.SignedString([]byte(secret))
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return signed
}

func websocketURL(httpURL string) string {
	return "ws" + strings.TrimPrefix(httpURL, "http")
}

func readBody(t *testing.T, resp *http.Response) string {
	t.Helper()
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read response body: %v", err)
	}
	return string(body)
}
