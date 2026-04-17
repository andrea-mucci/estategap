package sender

import (
	"context"
	"strings"
	"testing"

	"github.com/estategap/services/alert-dispatcher/internal/model"
)

type telegramAPIStub struct {
	request TelegramPhotoRequest
	calls   int
}

func (a *telegramAPIStub) SendPhoto(_ context.Context, req TelegramPhotoRequest) error {
	a.calls++
	a.request = req
	return nil
}

func (a *telegramAPIStub) GetUpdates(_ context.Context, _ int) ([]TelegramUpdate, error) {
	return nil, nil
}

func TestTelegramSenderRequiresLinkedAccount(t *testing.T) {
	t.Parallel()

	api := &telegramAPIStub{}
	sender := NewTelegramSender(context.Background(), api, nil, "https://app.estategap.test")
	result, err := sender.Send(context.Background(), model.NotificationEvent{}, &model.UserChannelProfile{})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if result.Success {
		t.Fatalf("Send() success = true, want false")
	}
	if result.ErrorDetail != "account not linked" {
		t.Fatalf("error detail = %q, want account not linked", result.ErrorDetail)
	}
	if api.calls != 0 {
		t.Fatalf("api calls = %d, want 0", api.calls)
	}
}

func TestTelegramSenderBuildsCaptionAndKeyboard(t *testing.T) {
	t.Parallel()

	api := &telegramAPIStub{}
	sender := NewTelegramSender(context.Background(), api, nil, "https://app.estategap.test")
	chatID := int64(1234)
	score := 0.88
	imageURL := "https://images.estategap.test/1.jpg"
	listingID := "listing-1"
	event := model.NotificationEvent{
		ListingID: &listingID,
		DealScore: &score,
		ListingSummary: &model.ListingSummary{
			PriceEUR: 320000,
			City:     "Berlin",
			ImageURL: &imageURL,
		},
	}
	user := &model.UserChannelProfile{TelegramChatID: &chatID}

	result, err := sender.Send(WithHistoryID(context.Background(), "history-99"), event, user)
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if !result.Success {
		t.Fatalf("Send() success = false")
	}
	if !strings.Contains(api.request.Caption, "*EUR 320,000*") {
		t.Fatalf("caption = %q, want bold price", api.request.Caption)
	}
	if !strings.Contains(api.request.Caption, "Deal score: *0\\.88*") {
		t.Fatalf("caption = %q, want bold deal score", api.request.Caption)
	}
	if len(api.request.ReplyMarkup.InlineKeyboard) != 1 || len(api.request.ReplyMarkup.InlineKeyboard[0]) != 3 {
		t.Fatalf("keyboard shape = %#v, want 3 buttons", api.request.ReplyMarkup)
	}
	if api.request.ReplyMarkup.InlineKeyboard[0][0].Text != "View Analysis" {
		t.Fatalf("first button = %q", api.request.ReplyMarkup.InlineKeyboard[0][0].Text)
	}
	if api.request.ReplyMarkup.InlineKeyboard[0][2].CallbackData != "dismiss:history-99" {
		t.Fatalf("dismiss callback = %q", api.request.ReplyMarkup.InlineKeyboard[0][2].CallbackData)
	}
}
