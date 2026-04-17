package sender

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/estategap/services/alert-dispatcher/internal/model"
)

type whatsAppAPIStub struct {
	message WhatsAppMessage
	calls   int
	errs    []error
}

func (a *whatsAppAPIStub) SendTemplate(_ context.Context, message WhatsAppMessage) error {
	a.calls++
	a.message = message
	if len(a.errs) == 0 {
		return nil
	}
	err := a.errs[0]
	a.errs = a.errs[1:]
	return err
}

func TestWhatsAppSenderRequiresPhoneNumber(t *testing.T) {
	t.Parallel()

	sender := NewWhatsAppSender(&whatsAppAPIStub{}, "+123", "template", "https://app.estategap.test")
	result, err := sender.Send(context.Background(), model.NotificationEvent{}, &model.UserChannelProfile{})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if result.Success {
		t.Fatalf("Send() success = true, want false")
	}
}

func TestWhatsAppSenderContentVariablesAndRetries(t *testing.T) {
	t.Parallel()

	phone := "+34612345678"
	score := 0.73
	listingID := "listing-9"
	api := &whatsAppAPIStub{
		errs: []error{errors.New("server exploded"), errors.New("server exploded"), nil},
	}
	sender := NewWhatsAppSender(api, "+14155238886", "template-1", "https://app.estategap.test")
	result, err := sender.Send(context.Background(), model.NotificationEvent{
		ListingID: &listingID,
		DealScore: &score,
		ListingSummary: &model.ListingSummary{
			City:     "Madrid",
			PriceEUR: 189500,
		},
	}, &model.UserChannelProfile{PhoneE164: &phone})
	if err != nil {
		t.Fatalf("Send() error = %v", err)
	}
	if !result.Success {
		t.Fatalf("Send() success = false")
	}
	if api.calls != 3 {
		t.Fatalf("calls = %d, want 3", api.calls)
	}
	if !strings.Contains(api.message.ContentVariables, "\"1\":\"Madrid\"") {
		t.Fatalf("ContentVariables = %q", api.message.ContentVariables)
	}
	if !strings.Contains(api.message.ContentVariables, "\"4\":\"https://app.estategap.test/listings/listing-9\"") {
		t.Fatalf("ContentVariables missing analysis url: %q", api.message.ContentVariables)
	}
}

func TestWhatsAppSenderStopsOnPermanentClientError(t *testing.T) {
	t.Parallel()

	phone := "+34612345678"
	api := &whatsAppAPIStub{errs: []error{Permanent(errors.New("bad request"))}}
	sender := NewWhatsAppSender(api, "+14155238886", "template-1", "https://app.estategap.test")
	result, err := sender.Send(context.Background(), model.NotificationEvent{}, &model.UserChannelProfile{PhoneE164: &phone})
	if err == nil {
		t.Fatalf("expected permanent error")
	}
	if result.Success {
		t.Fatalf("Send() success = true, want false")
	}
	if api.calls != 1 {
		t.Fatalf("calls = %d, want 1", api.calls)
	}
}
