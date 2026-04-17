package sender

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/estategap/services/alert-dispatcher/internal/model"
	templatespkg "github.com/estategap/services/alert-dispatcher/internal/templates"
	"github.com/shopspring/decimal"
)

type EmailMessage struct {
	To        string
	Subject   string
	HTMLBody  string
	TextBody  string
	FromName  string
	FromEmail string
}

type EmailClient interface {
	SendEmail(ctx context.Context, message EmailMessage) error
}

type EmailSender struct {
	client      EmailClient
	baseURL     string
	fromAddress string
	fromName    string
	templates   map[string]*template.Template
	now         func() time.Time
}

func NewEmailSender(client EmailClient, baseURL, fromAddress, fromName string) (*EmailSender, error) {
	langs := []string{"en", "es", "de", "fr", "pt"}
	parsed := make(map[string]*template.Template, len(langs))
	for _, lang := range langs {
		name := fmt.Sprintf("email_%s.html", lang)
		tmpl, err := template.ParseFS(templatespkg.FS, name)
		if err != nil {
			return nil, fmt.Errorf("parse %s: %w", name, err)
		}
		parsed[lang] = tmpl
	}

	return &EmailSender{
		client:      client,
		baseURL:     strings.TrimRight(strings.TrimSpace(baseURL), "/"),
		fromAddress: strings.TrimSpace(fromAddress),
		fromName:    strings.TrimSpace(fromName),
		templates:   parsed,
		now:         func() time.Time { return time.Now().UTC() },
	}, nil
}

func (s *EmailSender) Send(ctx context.Context, event model.NotificationEvent, user *model.UserChannelProfile) (model.DeliveryResult, error) {
	if user == nil || strings.TrimSpace(user.Email) == "" {
		return model.DeliveryResult{
			Success:      false,
			AttemptCount: 1,
			ErrorDetail:  "no email address",
		}, nil
	}

	data := s.buildTemplateData(ctx, event)
	tmpl := s.resolveTemplate(user.PreferredLanguage)

	return withRetry(ctx, len(RetryDelays)+1, RetryDelays, func() (model.DeliveryResult, error) {
		var htmlBody bytes.Buffer
		if err := tmpl.ExecuteTemplate(&htmlBody, "email", data); err != nil {
			return model.DeliveryResult{
				Success:     false,
				ErrorDetail: err.Error(),
			}, Permanent(fmt.Errorf("render email template: %w", err))
		}

		message := EmailMessage{
			To:        user.Email,
			Subject:   s.subjectForEvent(event, data),
			HTMLBody:  htmlBody.String(),
			TextBody:  s.textFallback(data),
			FromName:  s.fromName,
			FromEmail: s.fromAddress,
		}

		if s.client == nil {
			return model.DeliveryResult{
				Success:     false,
				ErrorDetail: "email client not configured",
			}, nil
		}

		if err := s.client.SendEmail(ctx, message); err != nil {
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

func (s *EmailSender) resolveTemplate(language string) *template.Template {
	normalized := strings.ToLower(strings.TrimSpace(language))
	if tmpl, ok := s.templates[normalized]; ok {
		return tmpl
	}
	return s.templates["en"]
}

func (s *EmailSender) subjectForEvent(event model.NotificationEvent, data model.EmailTemplateData) string {
	if strings.TrimSpace(event.RuleName) != "" {
		return fmt.Sprintf("%s: %s", event.RuleName, data.Address)
	}
	return fmt.Sprintf("EstateGap Alert: %s", data.Address)
}

func (s *EmailSender) textFallback(data model.EmailTemplateData) string {
	if data.IsDigest {
		return fmt.Sprintf("%s: %d matches ready to review.", data.RuleName, data.TotalMatches)
	}
	return fmt.Sprintf("%s %s. Review: %s", data.Address, data.PriceFormatted, data.AnalysisURL)
}

func (s *EmailSender) buildTemplateData(ctx context.Context, event model.NotificationEvent) model.EmailTemplateData {
	historyID := HistoryIDFromContext(ctx)
	analysisURL := s.buildAnalysisURL(event)
	portalURL := s.buildPortalURL(event, analysisURL)
	address := s.buildAddress(event)

	data := model.EmailTemplateData{
		Address:            address,
		PriceFormatted:     formatPrice(priceForEvent(event)),
		DealScore:          derefFloat(event.DealScore),
		DealTier:           derefInt(event.DealTier),
		DealBadgeColor:     dealBadgeColor(derefInt(event.DealTier)),
		Features:           s.buildFeatures(event),
		AnalysisURL:        analysisURL,
		PortalURL:          portalURL,
		TrackOpenURL:       fmt.Sprintf("%s/api/v1/alerts/track?id=%s&action=open", s.baseURL, url.QueryEscape(historyID)),
		TrackClickAnalysis: s.buildTrackedClickURL(historyID, analysisURL),
		TrackClickPortal:   s.buildTrackedClickURL(historyID, portalURL),
		IsDigest:           event.IsDigest,
		TotalMatches:       derefIntPtr(event.TotalMatches, len(event.Listings)),
		RuleName:           strings.TrimSpace(event.RuleName),
		TriggeredAt:        event.TriggeredAt,
	}

	if summary := event.ListingSummary; summary != nil {
		if summary.ImageURL != nil {
			data.PhotoURL = strings.TrimSpace(*summary.ImageURL)
		}
	}

	if event.IsDigest {
		data.Listings = make([]model.DigestEmailListing, 0, len(event.Listings))
		for _, listing := range event.Listings {
			item := model.DigestEmailListing{
				Title:          listing.Title,
				City:           listing.City,
				PriceFormatted: formatPrice(listing.PriceEUR),
				DealScore:      fmt.Sprintf("%.2f", listing.DealScore),
				ImageURL:       derefStringValue(listing.ImageURL),
				AnalysisURL:    fmt.Sprintf("%s/listings/%s", s.baseURL, url.PathEscape(strings.TrimSpace(listing.ListingID))),
				PortalURL:      derefStringValue(listing.PortalURL),
			}
			if item.PortalURL == "" {
				item.PortalURL = item.AnalysisURL
			}
			data.Listings = append(data.Listings, item)
			if data.PhotoURL == "" {
				data.PhotoURL = item.ImageURL
			}
		}
	}

	return data
}

func (s *EmailSender) buildAddress(event model.NotificationEvent) string {
	if event.ListingSummary == nil {
		return strings.ToUpper(strings.TrimSpace(event.CountryCode))
	}
	parts := make([]string, 0, 2)
	if city := strings.TrimSpace(event.ListingSummary.City); city != "" {
		parts = append(parts, city)
	}
	if country := strings.TrimSpace(event.CountryCode); country != "" {
		parts = append(parts, strings.ToUpper(country))
	}
	if len(parts) == 0 {
		return "EstateGap"
	}
	return strings.Join(parts, ", ")
}

func (s *EmailSender) buildAnalysisURL(event model.NotificationEvent) string {
	if event.ListingID != nil && strings.TrimSpace(*event.ListingID) != "" {
		return fmt.Sprintf("%s/listings/%s", s.baseURL, url.PathEscape(strings.TrimSpace(*event.ListingID)))
	}
	return fmt.Sprintf("%s/alerts/%s", s.baseURL, url.PathEscape(strings.TrimSpace(event.RuleID)))
}

func (s *EmailSender) buildPortalURL(event model.NotificationEvent, fallback string) string {
	if event.ListingSummary == nil || event.ListingSummary.PortalURL == nil {
		return fallback
	}
	if value := strings.TrimSpace(*event.ListingSummary.PortalURL); value != "" {
		return value
	}
	return fallback
}

func (s *EmailSender) buildTrackedClickURL(historyID, destination string) string {
	encoded := base64.RawURLEncoding.EncodeToString([]byte(destination))
	return fmt.Sprintf(
		"%s/api/v1/alerts/track?id=%s&action=click&url=%s",
		s.baseURL,
		url.QueryEscape(historyID),
		url.QueryEscape(encoded),
	)
}

func (s *EmailSender) buildFeatures(event model.NotificationEvent) []string {
	features := make([]string, 0, 4)
	if event.ListingSummary == nil {
		return features
	}
	summary := event.ListingSummary
	if summary.AreaM2 > 0 {
		features = append(features, fmt.Sprintf("%.0f m2", summary.AreaM2))
	}
	if summary.Bedrooms != nil {
		features = append(features, fmt.Sprintf("%d bedrooms", *summary.Bedrooms))
	}
	features = append(features, summary.Features...)
	return features
}

func priceForEvent(event model.NotificationEvent) float64 {
	if event.ListingSummary == nil {
		return 0
	}
	return event.ListingSummary.PriceEUR
}

func formatPrice(value float64) string {
	amount := decimal.NewFromFloat(value).StringFixedBank(0)
	parts := strings.Split(amount, ".")
	whole := parts[0]
	if len(whole) <= 3 {
		return "EUR " + whole
	}

	var chunks []string
	for len(whole) > 3 {
		chunks = append([]string{whole[len(whole)-3:]}, chunks...)
		whole = whole[:len(whole)-3]
	}
	if whole != "" {
		chunks = append([]string{whole}, chunks...)
	}
	return "EUR " + strings.Join(chunks, ",")
}

func dealBadgeColor(tier int) string {
	switch tier {
	case 1:
		return "#22c55e"
	case 2:
		return "#84cc16"
	case 3:
		return "#f59e0b"
	default:
		return "#ef4444"
	}
}

func derefFloat(value *float64) float64 {
	if value == nil {
		return 0
	}
	return *value
}

func derefInt(value *int) int {
	if value == nil {
		return 4
	}
	return *value
}

func derefIntPtr(value *int, fallback int) int {
	if value == nil {
		return fallback
	}
	return *value
}

func derefStringValue(value *string) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(*value)
}

type SESEmailClient struct {
	httpClient  *http.Client
	region      string
	endpoint    string
	accessKeyID string
	secretKey   string
	session     string
	now         func() time.Time
}

func NewSESEmailClient(region string) *SESEmailClient {
	trimmedRegion := strings.TrimSpace(region)
	if trimmedRegion == "" {
		trimmedRegion = "eu-west-1"
	}
	return &SESEmailClient{
		httpClient:  &http.Client{Timeout: 10 * time.Second},
		region:      trimmedRegion,
		endpoint:    fmt.Sprintf("https://email.%s.amazonaws.com/v2/email/outbound-emails", trimmedRegion),
		accessKeyID: strings.TrimSpace(os.Getenv("AWS_ACCESS_KEY_ID")),
		secretKey:   strings.TrimSpace(os.Getenv("AWS_SECRET_ACCESS_KEY")),
		session:     strings.TrimSpace(os.Getenv("AWS_SESSION_TOKEN")),
		now:         func() time.Time { return time.Now().UTC() },
	}
}

func (c *SESEmailClient) SendEmail(ctx context.Context, message EmailMessage) error {
	if c.accessKeyID == "" || c.secretKey == "" {
		return Permanent(fmt.Errorf("aws credentials not configured"))
	}

	payload := map[string]any{
		"FromEmailAddress": formatMailbox(message.FromName, message.FromEmail),
		"Destination": map[string]any{
			"ToAddresses": []string{message.To},
		},
		"Content": map[string]any{
			"Simple": map[string]any{
				"Subject": map[string]string{"Data": message.Subject},
				"Body": map[string]any{
					"Html": map[string]string{"Data": message.HTMLBody},
					"Text": map[string]string{"Data": message.TextBody},
				},
			},
		},
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

	if err := c.sign(req, body); err != nil {
		return Permanent(err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return nil
	}

	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return Permanent(fmt.Errorf("ses status %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody))))
	}
	return fmt.Errorf("ses status %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
}

func (c *SESEmailClient) sign(req *http.Request, payload []byte) error {
	now := c.now()
	amzDate := now.Format("20060102T150405Z")
	shortDate := now.Format("20060102")
	payloadHash := sha256Hex(payload)
	req.Header.Set("X-Amz-Date", amzDate)
	if c.session != "" {
		req.Header.Set("X-Amz-Security-Token", c.session)
	}

	host := req.URL.Host
	req.Header.Set("Host", host)

	canonicalHeaders := strings.Builder{}
	canonicalHeaders.WriteString("content-type:")
	canonicalHeaders.WriteString(req.Header.Get("Content-Type"))
	canonicalHeaders.WriteString("\n")
	canonicalHeaders.WriteString("host:")
	canonicalHeaders.WriteString(host)
	canonicalHeaders.WriteString("\n")
	canonicalHeaders.WriteString("x-amz-date:")
	canonicalHeaders.WriteString(amzDate)
	canonicalHeaders.WriteString("\n")

	signedHeaders := "content-type;host;x-amz-date"
	if c.session != "" {
		canonicalHeaders.WriteString("x-amz-security-token:")
		canonicalHeaders.WriteString(c.session)
		canonicalHeaders.WriteString("\n")
		signedHeaders = "content-type;host;x-amz-date;x-amz-security-token"
	}

	canonicalRequest := strings.Join([]string{
		req.Method,
		req.URL.EscapedPath(),
		req.URL.RawQuery,
		canonicalHeaders.String(),
		signedHeaders,
		payloadHash,
	}, "\n")

	scope := fmt.Sprintf("%s/%s/ses/aws4_request", shortDate, c.region)
	stringToSign := strings.Join([]string{
		"AWS4-HMAC-SHA256",
		amzDate,
		scope,
		sha256Hex([]byte(canonicalRequest)),
	}, "\n")

	signingKey := awsSigningKey(c.secretKey, shortDate, c.region, "ses")
	signature := hex.EncodeToString(hmacSHA256(signingKey, stringToSign))
	req.Header.Set(
		"Authorization",
		fmt.Sprintf(
			"AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s",
			c.accessKeyID,
			scope,
			signedHeaders,
			signature,
		),
	)
	return nil
}

func formatMailbox(name, email string) string {
	if strings.TrimSpace(name) == "" {
		return strings.TrimSpace(email)
	}
	return fmt.Sprintf("%s <%s>", strings.TrimSpace(name), strings.TrimSpace(email))
}

func awsSigningKey(secret, date, region, service string) []byte {
	kDate := hmacSHA256([]byte("AWS4"+secret), date)
	kRegion := hmacSHA256(kDate, region)
	kService := hmacSHA256(kRegion, service)
	return hmacSHA256(kService, "aws4_request")
}

func hmacSHA256(key []byte, value string) []byte {
	hash := hmac.New(sha256.New, key)
	_, _ = hash.Write([]byte(value))
	return hash.Sum(nil)
}

func sha256Hex(value []byte) string {
	sum := sha256.Sum256(value)
	return hex.EncodeToString(sum[:])
}
