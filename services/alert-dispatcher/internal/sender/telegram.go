package sender

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/model"
)

type TelegramButton struct {
	Text         string `json:"text"`
	URL          string `json:"url,omitempty"`
	CallbackData string `json:"callback_data,omitempty"`
}

type TelegramInlineKeyboardMarkup struct {
	InlineKeyboard [][]TelegramButton `json:"inline_keyboard"`
}

type TelegramPhotoRequest struct {
	ChatID      int64
	PhotoURL    string
	Caption     string
	ReplyMarkup TelegramInlineKeyboardMarkup
}

type TelegramChat struct {
	ID int64 `json:"id"`
}

type TelegramMessage struct {
	Text string       `json:"text"`
	Chat TelegramChat `json:"chat"`
}

type TelegramUpdate struct {
	UpdateID int              `json:"update_id"`
	Message  *TelegramMessage `json:"message,omitempty"`
}

type RetryAfterError struct {
	Delay time.Duration
}

func (e RetryAfterError) Error() string {
	return fmt.Sprintf("retry after %s", e.Delay)
}

type TelegramAPI interface {
	SendPhoto(ctx context.Context, req TelegramPhotoRequest) error
	GetUpdates(ctx context.Context, offset int) ([]TelegramUpdate, error)
}

type telegramTokenRepo interface {
	StoreTelegramChatIDByToken(ctx context.Context, token string, chatID int64) error
}

type TelegramSender struct {
	api      TelegramAPI
	userRepo telegramTokenRepo
	baseURL  string
	now      func() time.Time
}

func NewTelegramSender(ctx context.Context, api TelegramAPI, userRepo telegramTokenRepo, baseURL string) *TelegramSender {
	sender := &TelegramSender{
		api:      api,
		userRepo: userRepo,
		baseURL:  strings.TrimRight(strings.TrimSpace(baseURL), "/"),
		now:      func() time.Time { return time.Now().UTC() },
	}
	if api != nil && userRepo != nil {
		go sender.pollUpdates(ctx)
	}
	return sender
}

func (s *TelegramSender) Send(ctx context.Context, event model.NotificationEvent, user *model.UserChannelProfile) (model.DeliveryResult, error) {
	if user == nil || user.TelegramChatID == nil {
		return model.DeliveryResult{
			Success:      false,
			AttemptCount: 1,
			ErrorDetail:  "account not linked",
		}, nil
	}

	request := TelegramPhotoRequest{
		ChatID:      *user.TelegramChatID,
		PhotoURL:    telegramPhotoURL(event),
		Caption:     s.buildCaption(event),
		ReplyMarkup: s.buildKeyboard(ctx, event),
	}

	return withRetry(ctx, len(RetryDelays)+1, RetryDelays, func() (model.DeliveryResult, error) {
		if s.api == nil {
			return model.DeliveryResult{
				Success:     false,
				ErrorDetail: "telegram client not configured",
			}, nil
		}

		err := s.api.SendPhoto(ctx, request)
		if err != nil {
			var retryAfter RetryAfterError
			if errors.As(err, &retryAfter) {
				if waitErr := sleepWithContext(ctx, retryAfter.Delay); waitErr != nil {
					return model.DeliveryResult{Success: false, ErrorDetail: waitErr.Error()}, waitErr
				}
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

func (s *TelegramSender) buildCaption(event model.NotificationEvent) string {
	address := "EstateGap"
	price := "EUR 0"
	dealScore := "0.00"
	if event.ListingSummary != nil {
		address = strings.TrimSpace(event.ListingSummary.City)
		if address == "" {
			address = strings.TrimSpace(event.ListingSummary.Title)
		}
		price = formatPrice(event.ListingSummary.PriceEUR)
	}
	if event.DealScore != nil {
		dealScore = fmt.Sprintf("%.2f", *event.DealScore)
	}

	return strings.Join([]string{
		"*" + escapeTelegramMarkdown(price) + "*",
		escapeTelegramMarkdown(address),
		"Deal score: *" + escapeTelegramMarkdown(dealScore) + "*",
	}, "\n")
}

func (s *TelegramSender) buildKeyboard(ctx context.Context, event model.NotificationEvent) TelegramInlineKeyboardMarkup {
	historyID := HistoryIDFromContext(ctx)
	analysisURL := fmt.Sprintf("%s/listings/%s", s.baseURL, url.PathEscape(strings.TrimSpace(derefListingID(event.ListingID, event.RuleID))))
	portalURL := analysisURL
	if event.ListingSummary != nil && event.ListingSummary.PortalURL != nil && strings.TrimSpace(*event.ListingSummary.PortalURL) != "" {
		portalURL = strings.TrimSpace(*event.ListingSummary.PortalURL)
	}

	return TelegramInlineKeyboardMarkup{
		InlineKeyboard: [][]TelegramButton{{
			{Text: "View Analysis", URL: analysisURL},
			{Text: "View on Portal", URL: portalURL},
			{Text: "Dismiss", CallbackData: "dismiss:" + historyID},
		}},
	}
}

func (s *TelegramSender) pollUpdates(ctx context.Context) {
	offset := 0
	for {
		if ctx.Err() != nil {
			return
		}

		updates, err := s.api.GetUpdates(ctx, offset)
		if err != nil {
			slog.Warn("telegram polling failed", "error", err)
			if sleepErr := sleepWithContext(ctx, 2*time.Second); sleepErr != nil {
				return
			}
			continue
		}

		for _, update := range updates {
			offset = update.UpdateID + 1
			if update.Message == nil {
				continue
			}
			token := extractStartToken(update.Message.Text)
			if token == "" {
				continue
			}
			if err := s.userRepo.StoreTelegramChatIDByToken(ctx, token, update.Message.Chat.ID); err != nil {
				slog.Warn("telegram account link failed", "error", err)
			}
		}
	}
}

func telegramPhotoURL(event model.NotificationEvent) string {
	if event.ListingSummary == nil || event.ListingSummary.ImageURL == nil {
		return ""
	}
	return strings.TrimSpace(*event.ListingSummary.ImageURL)
}

func derefListingID(listingID *string, fallback string) string {
	if listingID != nil && strings.TrimSpace(*listingID) != "" {
		return strings.TrimSpace(*listingID)
	}
	return fallback
}

func extractStartToken(text string) string {
	text = strings.TrimSpace(text)
	if !strings.HasPrefix(text, "/start") {
		return ""
	}
	parts := strings.Fields(text)
	if len(parts) < 2 {
		return ""
	}
	return strings.TrimSpace(parts[1])
}

func escapeTelegramMarkdown(value string) string {
	replacer := strings.NewReplacer(
		"_", "\\_",
		"*", "\\*",
		"[", "\\[",
		"]", "\\]",
		"(", "\\(",
		")", "\\)",
		"~", "\\~",
		"`", "\\`",
		">", "\\>",
		"#", "\\#",
		"+", "\\+",
		"-", "\\-",
		"=", "\\=",
		"|", "\\|",
		"{", "\\{",
		"}", "\\}",
		".", "\\.",
		"!", "\\!",
	)
	return replacer.Replace(value)
}

type TelegramHTTPClient struct {
	httpClient *http.Client
	baseURL    string
}

func NewTelegramHTTPClient(token string) *TelegramHTTPClient {
	return &TelegramHTTPClient{
		httpClient: &http.Client{Timeout: 35 * time.Second},
		baseURL:    fmt.Sprintf("https://api.telegram.org/bot%s", strings.TrimSpace(token)),
	}
}

func (c *TelegramHTTPClient) SendPhoto(ctx context.Context, req TelegramPhotoRequest) error {
	replyMarkup, err := json.Marshal(req.ReplyMarkup)
	if err != nil {
		return Permanent(err)
	}

	values := url.Values{}
	values.Set("chat_id", fmt.Sprintf("%d", req.ChatID))
	values.Set("photo", req.PhotoURL)
	values.Set("caption", req.Caption)
	values.Set("parse_mode", "MarkdownV2")
	values.Set("reply_markup", string(replyMarkup))

	httpReq, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		c.baseURL+"/sendPhoto",
		strings.NewReader(values.Encode()),
	)
	if err != nil {
		return err
	}
	httpReq.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	return parseTelegramResponse(resp)
}

func (c *TelegramHTTPClient) GetUpdates(ctx context.Context, offset int) ([]TelegramUpdate, error) {
	query := url.Values{}
	query.Set("timeout", "30")
	if offset > 0 {
		query.Set("offset", fmt.Sprintf("%d", offset))
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/getUpdates?"+query.Encode(), nil)
	if err != nil {
		return nil, err
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var payload struct {
		OK          bool             `json:"ok"`
		Result      []TelegramUpdate `json:"result"`
		Description string           `json:"description"`
		Parameters  struct {
			RetryAfter int `json:"retry_after"`
		} `json:"parameters"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}
	if !payload.OK {
		if payload.Parameters.RetryAfter > 0 {
			return nil, RetryAfterError{Delay: time.Duration(payload.Parameters.RetryAfter) * time.Second}
		}
		if resp.StatusCode >= 400 && resp.StatusCode < 500 {
			return nil, Permanent(fmt.Errorf("telegram getUpdates failed: %s", payload.Description))
		}
		return nil, fmt.Errorf("telegram getUpdates failed: %s", payload.Description)
	}
	return payload.Result, nil
}

func parseTelegramResponse(resp *http.Response) error {
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	var payload struct {
		OK          bool   `json:"ok"`
		Description string `json:"description"`
		Parameters  struct {
			RetryAfter int `json:"retry_after"`
		} `json:"parameters"`
	}
	if len(body) > 0 {
		_ = json.Unmarshal(body, &payload)
	}
	if payload.OK {
		return nil
	}
	if payload.Parameters.RetryAfter > 0 {
		return RetryAfterError{Delay: time.Duration(payload.Parameters.RetryAfter) * time.Second}
	}
	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return Permanent(fmt.Errorf("telegram status %d: %s", resp.StatusCode, strings.TrimSpace(payload.Description)))
	}
	return fmt.Errorf("telegram status %d: %s", resp.StatusCode, strings.TrimSpace(payload.Description))
}

func sleepWithContext(ctx context.Context, delay time.Duration) error {
	if delay <= 0 {
		return nil
	}
	timer := time.NewTimer(delay)
	defer timer.Stop()

	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}
