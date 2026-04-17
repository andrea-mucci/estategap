package sender

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/redis/go-redis/v9"
)

type webhookRedis interface {
	Incr(ctx context.Context, key string) *redis.IntCmd
	Expire(ctx context.Context, key string, expiration time.Duration) *redis.BoolCmd
}

type WebhookSender struct {
	httpClient *http.Client
	redis      webhookRedis
	now        func() time.Time
}

func NewWebhookSender(httpClient *http.Client, redisClient webhookRedis) *WebhookSender {
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 10 * time.Second}
	}
	return &WebhookSender{
		httpClient: httpClient,
		redis:      redisClient,
		now:        func() time.Time { return time.Now().UTC() },
	}
}

func (s *WebhookSender) Send(ctx context.Context, event model.NotificationEvent, user *model.UserChannelProfile) (model.DeliveryResult, error) {
	if event.WebhookURL == nil || strings.TrimSpace(*event.WebhookURL) == "" {
		return model.DeliveryResult{
			Success:      false,
			AttemptCount: 1,
			ErrorDetail:  "no webhook URL",
		}, nil
	}

	body, err := json.Marshal(event)
	if err != nil {
		return model.DeliveryResult{Success: false, AttemptCount: 1, ErrorDetail: err.Error()}, Permanent(err)
	}

	historyID := HistoryIDFromContext(ctx)
	secret := ""
	if user != nil && user.WebhookSecret != nil {
		secret = *user.WebhookSecret
	} else {
		slog.Warn("webhook secret missing; signing with empty secret")
	}

	return withRetry(ctx, len(RetryDelays)+1, RetryDelays, func() (model.DeliveryResult, error) {
		if s.redis != nil && strings.TrimSpace(event.EventID) != "" {
			key := "webhook:retry:" + strings.TrimSpace(event.EventID)
			_ = s.redis.Incr(ctx, key)
			_ = s.redis.Expire(ctx, key, 300*time.Second)
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimSpace(*event.WebhookURL), bytes.NewReader(body))
		if err != nil {
			return model.DeliveryResult{Success: false, ErrorDetail: err.Error()}, Permanent(err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Estategap-Event", "alert.notification")
		req.Header.Set("X-Delivery-ID", historyID)
		req.Header.Set("X-Webhook-Signature", computeWebhookSignature(secret, body))

		resp, err := s.httpClient.Do(req)
		if err != nil {
			return model.DeliveryResult{Success: false, ErrorDetail: err.Error()}, err
		}
		defer resp.Body.Close()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			deliveredAt := s.now()
			return model.DeliveryResult{
				Success:     true,
				DeliveredAt: &deliveredAt,
			}, nil
		}

		respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		err = fmt.Errorf("webhook status %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
		if resp.StatusCode >= 400 && resp.StatusCode < 500 {
			return model.DeliveryResult{Success: false, ErrorDetail: err.Error()}, Permanent(err)
		}
		return model.DeliveryResult{Success: false, ErrorDetail: err.Error()}, err
	})
}

func computeWebhookSignature(secret string, payload []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write(payload)
	return "sha256=" + hex.EncodeToString(mac.Sum(nil))
}
