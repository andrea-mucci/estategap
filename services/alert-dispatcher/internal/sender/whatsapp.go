package sender

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/model"
)

type WhatsAppMessage struct {
	From             string
	To               string
	ContentSID       string
	ContentVariables string
}

type WhatsAppAPI interface {
	SendTemplate(ctx context.Context, message WhatsAppMessage) error
}

type WhatsAppSender struct {
	api         WhatsAppAPI
	from        string
	templateSID string
	baseURL     string
	now         func() time.Time
}

func NewWhatsAppSender(api WhatsAppAPI, from, templateSID, baseURL string) *WhatsAppSender {
	return &WhatsAppSender{
		api:         api,
		from:        strings.TrimSpace(from),
		templateSID: strings.TrimSpace(templateSID),
		baseURL:     strings.TrimRight(strings.TrimSpace(baseURL), "/"),
		now:         func() time.Time { return time.Now().UTC() },
	}
}

func (s *WhatsAppSender) Send(ctx context.Context, event model.NotificationEvent, user *model.UserChannelProfile) (model.DeliveryResult, error) {
	if user == nil || user.PhoneE164 == nil || strings.TrimSpace(*user.PhoneE164) == "" {
		return model.DeliveryResult{
			Success:      false,
			AttemptCount: 1,
			ErrorDetail:  "no phone number",
		}, nil
	}

	contentVariables, err := s.buildContentVariables(event)
	if err != nil {
		return model.DeliveryResult{Success: false, AttemptCount: 1, ErrorDetail: err.Error()}, Permanent(err)
	}

	message := WhatsAppMessage{
		From:             "whatsapp:" + s.from,
		To:               "whatsapp:" + strings.TrimSpace(*user.PhoneE164),
		ContentSID:       s.templateSID,
		ContentVariables: contentVariables,
	}

	return withRetry(ctx, len(RetryDelays)+1, RetryDelays, func() (model.DeliveryResult, error) {
		if s.api == nil {
			return model.DeliveryResult{
				Success:     false,
				ErrorDetail: "whatsapp client not configured",
			}, nil
		}

		err := s.api.SendTemplate(ctx, message)
		if err != nil {
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

func (s *WhatsAppSender) buildContentVariables(event model.NotificationEvent) (string, error) {
	address := s.buildAddress(event)
	price := formatPrice(priceForEvent(event))
	score := "0.00"
	if event.DealScore != nil {
		score = fmt.Sprintf("%.2f", *event.DealScore)
	}
	analysisURL := fmt.Sprintf("%s/listings/%s", s.baseURL, url.PathEscape(strings.TrimSpace(derefListingID(event.ListingID, event.RuleID))))

	payload := map[string]string{
		"1": address,
		"2": price,
		"3": score,
		"4": analysisURL,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	return string(body), nil
}

func (s *WhatsAppSender) buildAddress(event model.NotificationEvent) string {
	if event.ListingSummary == nil {
		return strings.ToUpper(strings.TrimSpace(event.CountryCode))
	}
	if city := strings.TrimSpace(event.ListingSummary.City); city != "" {
		return city
	}
	return strings.TrimSpace(event.ListingSummary.Title)
}

type WhatsAppHTTPClient struct {
	httpClient *http.Client
	accountSID string
	authToken  string
}

func NewWhatsAppHTTPClient(accountSID, authToken string) *WhatsAppHTTPClient {
	return &WhatsAppHTTPClient{
		httpClient: &http.Client{Timeout: 10 * time.Second},
		accountSID: strings.TrimSpace(accountSID),
		authToken:  strings.TrimSpace(authToken),
	}
}

func (c *WhatsAppHTTPClient) SendTemplate(ctx context.Context, message WhatsAppMessage) error {
	endpoint := fmt.Sprintf("https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json", c.accountSID)
	values := url.Values{}
	values.Set("From", message.From)
	values.Set("To", message.To)
	values.Set("ContentSid", message.ContentSID)
	values.Set("ContentVariables", message.ContentVariables)

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(values.Encode()))
	if err != nil {
		return err
	}
	req.SetBasicAuth(c.accountSID, c.authToken)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return nil
	}
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return Permanent(fmt.Errorf("twilio status %d: %s", resp.StatusCode, strings.TrimSpace(string(body))))
	}
	return fmt.Errorf("twilio status %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
}
