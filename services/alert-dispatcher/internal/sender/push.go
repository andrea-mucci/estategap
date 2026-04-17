package sender

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/model"
	"golang.org/x/oauth2/google"
)

var ErrPushTokenNotRegistered = errors.New("registration-token-not-registered")

type PushMessage struct {
	Token    string
	Title    string
	Body     string
	ImageURL string
	Link     string
}

type PushClient interface {
	Send(ctx context.Context, message PushMessage) error
}

type pushTokenCleaner interface {
	ClearPushToken(ctx context.Context, userID string) error
}

type PushSender struct {
	client   PushClient
	userRepo pushTokenCleaner
	baseURL  string
	now      func() time.Time
}

func NewPushSender(client PushClient, userRepo pushTokenCleaner, baseURL string) *PushSender {
	return &PushSender{
		client:   client,
		userRepo: userRepo,
		baseURL:  strings.TrimRight(strings.TrimSpace(baseURL), "/"),
		now:      func() time.Time { return time.Now().UTC() },
	}
}

func (s *PushSender) Send(ctx context.Context, event model.NotificationEvent, user *model.UserChannelProfile) (model.DeliveryResult, error) {
	if user == nil || user.PushToken == nil || strings.TrimSpace(*user.PushToken) == "" {
		return model.DeliveryResult{
			Success:      false,
			AttemptCount: 1,
			ErrorDetail:  "no push subscription",
		}, nil
	}

	message := PushMessage{
		Token:    strings.TrimSpace(*user.PushToken),
		Title:    pushTitle(event),
		Body:     pushBody(event),
		ImageURL: pushImageURL(event),
		Link:     fmt.Sprintf("%s/listings/%s", s.baseURL, url.PathEscape(strings.TrimSpace(derefListingID(event.ListingID, event.RuleID)))),
	}

	return withRetry(ctx, len(RetryDelays)+1, RetryDelays, func() (model.DeliveryResult, error) {
		if s.client == nil {
			return model.DeliveryResult{
				Success:     false,
				ErrorDetail: "push client not configured",
			}, nil
		}

		err := s.client.Send(ctx, message)
		if err != nil {
			if errors.Is(err, ErrPushTokenNotRegistered) {
				if clearErr := s.userRepo.ClearPushToken(ctx, user.UserID); clearErr != nil {
					return model.DeliveryResult{Success: false, ErrorDetail: clearErr.Error()}, clearErr
				}
				return model.DeliveryResult{
					Success:     false,
					ErrorDetail: "registration-token-not-registered",
				}, nil
			}
			return model.DeliveryResult{
				Success:     false,
				ErrorDetail: err.Error(),
			}, err
		}

		deliveredAt := s.now()
		return model.DeliveryResult{
			Success:     true,
			DeliveredAt: &deliveredAt,
		}, nil
	})
}

func pushTitle(event model.NotificationEvent) string {
	if event.ListingSummary != nil && strings.TrimSpace(event.ListingSummary.Title) != "" {
		return event.ListingSummary.Title
	}
	return "EstateGap alert"
}

func pushBody(event model.NotificationEvent) string {
	if event.ListingSummary != nil && strings.TrimSpace(event.ListingSummary.City) != "" {
		return fmt.Sprintf("%s - %s", event.ListingSummary.City, formatPrice(event.ListingSummary.PriceEUR))
	}
	return "New opportunity available."
}

func pushImageURL(event model.NotificationEvent) string {
	if event.ListingSummary == nil || event.ListingSummary.ImageURL == nil {
		return ""
	}
	return strings.TrimSpace(*event.ListingSummary.ImageURL)
}

type FCMHTTPClient struct {
	httpClient *http.Client
	endpoint   string
}

func NewFCMHTTPClient(ctx context.Context, credentialsJSON string) (*FCMHTTPClient, error) {
	config, err := google.JWTConfigFromJSON([]byte(credentialsJSON), "https://www.googleapis.com/auth/firebase.messaging")
	if err != nil {
		return nil, err
	}

	var creds struct {
		ProjectID string `json:"project_id"`
	}
	if err := json.Unmarshal([]byte(credentialsJSON), &creds); err != nil {
		return nil, err
	}
	if strings.TrimSpace(creds.ProjectID) == "" {
		return nil, fmt.Errorf("firebase credentials missing project_id")
	}

	return &FCMHTTPClient{
		httpClient: config.Client(ctx),
		endpoint:   fmt.Sprintf("https://fcm.googleapis.com/v1/projects/%s/messages:send", strings.TrimSpace(creds.ProjectID)),
	}, nil
}

func (c *FCMHTTPClient) Send(ctx context.Context, message PushMessage) error {
	payload := map[string]any{
		"message": map[string]any{
			"token": message.Token,
			"notification": map[string]string{
				"title": message.Title,
				"body":  message.Body,
			},
			"webpush": map[string]any{
				"fcm_options": map[string]string{
					"link": message.Link,
				},
			},
		},
	}
	if strings.TrimSpace(message.ImageURL) != "" {
		payload["message"].(map[string]any)["notification"].(map[string]string)["image"] = message.ImageURL
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return Permanent(err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.endpoint, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return nil
	}

	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if strings.Contains(string(respBody), "registration-token-not-registered") {
		return ErrPushTokenNotRegistered
	}
	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return Permanent(fmt.Errorf("fcm status %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody))))
	}
	return fmt.Errorf("fcm status %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
}
