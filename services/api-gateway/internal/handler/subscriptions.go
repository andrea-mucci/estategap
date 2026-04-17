package handler

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/ctxkey"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/estategap/services/api-gateway/internal/service"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/redis/go-redis/v9"
	"github.com/stripe/stripe-go/v81"
)

const (
	stripeEventKeyPrefix       = "stripe:event:"
	stripePendingDowngradesKey = "stripe:pending_downgrades"
)

type SubscriptionsHandler struct {
	stripe      *service.StripeService
	subsRepo    *repository.SubscriptionsRepo
	usersRepo   *repository.UsersRepo
	redisClient *redis.Client
}

type subscriptionStateResponse struct {
	Tier             string  `json:"tier"`
	Status           string  `json:"status"`
	BillingPeriod    *string `json:"billing_period"`
	CurrentPeriodEnd *string `json:"current_period_end"`
	TrialEndAt       *string `json:"trial_end_at"`
}

type stripeCheckoutSessionPayload struct {
	ClientReferenceID string            `json:"client_reference_id"`
	Customer          json.RawMessage   `json:"customer"`
	Subscription      json.RawMessage   `json:"subscription"`
	Metadata          map[string]string `json:"metadata"`
}

type stripeSubscriptionPayload struct {
	ID                 string            `json:"id"`
	Customer           json.RawMessage   `json:"customer"`
	Status             string            `json:"status"`
	CurrentPeriodStart int64             `json:"current_period_start"`
	CurrentPeriodEnd   int64             `json:"current_period_end"`
	TrialEnd           *int64            `json:"trial_end"`
	Metadata           map[string]string `json:"metadata"`
	Items              struct {
		Data []struct {
			Price struct {
				Recurring struct {
					Interval string `json:"interval"`
				} `json:"recurring"`
			} `json:"price"`
		} `json:"data"`
	} `json:"items"`
}

type stripeInvoicePayload struct {
	Subscription json.RawMessage `json:"subscription"`
}

func NewSubscriptionsHandler(
	stripeService *service.StripeService,
	subsRepo *repository.SubscriptionsRepo,
	usersRepo *repository.UsersRepo,
	redisClient *redis.Client,
) *SubscriptionsHandler {
	return &SubscriptionsHandler{
		stripe:      stripeService,
		subsRepo:    subsRepo,
		usersRepo:   usersRepo,
		redisClient: redisClient,
	}
}

func (h *SubscriptionsHandler) Checkout(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Tier          string `json:"tier"`
		BillingPeriod string `json:"billing_period"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}

	tier, ok := parsePaidSubscriptionTier(req.Tier)
	if !ok {
		writeError(w, r, http.StatusBadRequest, "invalid_tier")
		return
	}

	period := strings.ToLower(strings.TrimSpace(req.BillingPeriod))
	if period != "monthly" && period != "annual" {
		writeError(w, r, http.StatusBadRequest, "invalid_billing_period")
		return
	}

	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	if current, err := h.subsRepo.GetByUserID(r.Context(), userID); err == nil {
		if current.Status == "active" || current.Status == "trialing" {
			writeError(w, r, http.StatusBadRequest, "already_subscribed")
			return
		}
	} else if !errors.Is(err, repository.ErrNotFound) {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load subscription")
		return
	}

	email := strings.TrimSpace(ctxkey.String(r.Context(), ctxkey.UserEmail))
	if email == "" {
		writeError(w, r, http.StatusUnauthorized, "missing user email")
		return
	}

	session, err := h.stripe.CreateCheckoutSession(userID.String(), email, string(tier), period)
	if err != nil {
		writeError(w, r, http.StatusInternalServerError, "stripe_error")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]string{"checkout_url": session.URL})
}

func (h *SubscriptionsHandler) StripeWebhook(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid_payload")
		return
	}

	event, err := h.stripe.ParseWebhookEvent(body, r.Header.Get("Stripe-Signature"))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid_signature")
		return
	}

	dedupeKey := stripeEventKeyPrefix + event.ID
	locked, err := h.redisClient.SetNX(r.Context(), dedupeKey, "1", 7*24*time.Hour).Result()
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to record webhook")
		return
	}
	if !locked {
		respond.JSON(w, http.StatusOK, map[string]any{})
		return
	}

	if err := h.processStripeEvent(r.Context(), event); err != nil {
		if delErr := h.redisClient.Del(r.Context(), dedupeKey).Err(); delErr != nil {
			slog.Error("failed to clear Stripe event dedupe key", "event_id", event.ID, "error", delErr)
		}
		slog.Error("failed to process Stripe event", "event_id", event.ID, "type", string(event.Type), "error", err)
		writeError(w, r, http.StatusInternalServerError, "stripe_error")
		return
	}

	slog.Info("processed Stripe event", "event_id", event.ID, "type", string(event.Type))
	respond.JSON(w, http.StatusOK, map[string]any{})
}

func (h *SubscriptionsHandler) Portal(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	user, err := h.usersRepo.GetUserByID(r.Context(), userID)
	if err != nil {
		writeError(w, r, http.StatusNotFound, "user not found")
		return
	}
	if user.StripeCustomerID == nil || strings.TrimSpace(*user.StripeCustomerID) == "" {
		writeError(w, r, http.StatusBadRequest, "no_subscription")
		return
	}

	session, err := h.stripe.CreatePortalSession(*user.StripeCustomerID, h.stripe.DefaultPortalReturnURL())
	if err != nil {
		writeError(w, r, http.StatusInternalServerError, "stripe_error")
		return
	}

	respond.JSON(w, http.StatusOK, map[string]string{"portal_url": session.URL})
}

func (h *SubscriptionsHandler) Me(w http.ResponseWriter, r *http.Request) {
	userID, err := parseUserID(r.Context())
	if err != nil {
		writeError(w, r, http.StatusUnauthorized, "missing user")
		return
	}

	sub, err := h.subsRepo.GetByUserID(r.Context(), userID)
	if errors.Is(err, repository.ErrNotFound) {
		respond.JSON(w, http.StatusOK, subscriptionStateResponse{
			Tier:   string(models.SubscriptionTierFree),
			Status: "free",
		})
		return
	}
	if err != nil {
		writeError(w, r, http.StatusServiceUnavailable, "failed to load subscription")
		return
	}

	respond.JSON(w, http.StatusOK, subscriptionStateResponse{
		Tier:             string(sub.Tier),
		Status:           sub.Status,
		BillingPeriod:    stringPtrOrNil(sub.BillingPeriod),
		CurrentPeriodEnd: formatPGTime(&sub.CurrentPeriodEnd),
		TrialEndAt:       formatPGTime(sub.TrialEndAt),
	})
}

func (h *SubscriptionsHandler) processStripeEvent(ctx context.Context, event stripe.Event) error {
	switch string(event.Type) {
	case "checkout.session.completed":
		return h.handleCheckoutSessionCompleted(ctx, event.Data.Raw)
	case "customer.subscription.updated":
		return h.handleCustomerSubscriptionUpdated(ctx, event.Data.Raw)
	case "customer.subscription.deleted":
		return h.handleCustomerSubscriptionDeleted(ctx, event.Data.Raw)
	case "invoice.payment_failed":
		return h.handleInvoicePaymentFailed(ctx, event.Data.Raw)
	case "invoice.payment_succeeded":
		return h.handleInvoicePaymentSucceeded(ctx, event.Data.Raw)
	default:
		return nil
	}
}

func (h *SubscriptionsHandler) handleCheckoutSessionCompleted(ctx context.Context, raw []byte) error {
	var payload stripeCheckoutSessionPayload
	if err := json.Unmarshal(raw, &payload); err != nil {
		return err
	}

	userID, err := uuid.Parse(strings.TrimSpace(payload.ClientReferenceID))
	if err != nil {
		return err
	}

	stripeCustomerID, err := expandableID(payload.Customer)
	if err != nil {
		return err
	}
	stripeSubID, err := expandableID(payload.Subscription)
	if err != nil {
		return err
	}
	if stripeCustomerID == "" || stripeSubID == "" {
		return errors.New("missing Stripe identifiers on checkout session")
	}

	tier, ok := parsePaidSubscriptionTier(payload.Metadata["tier"])
	if !ok {
		return errors.New("missing subscription tier metadata")
	}

	stripeSub, err := h.stripe.GetSubscription(stripeSubID)
	if err != nil {
		return err
	}

	subscriptionRecord, endsAt, err := subscriptionModelFromStripe(userID, stripeCustomerID, stripeSubID, tier, payload.Metadata["billing_period"], stripeSub)
	if err != nil {
		return err
	}

	tx, err := h.subsRepo.BeginTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if err := h.subsRepo.CreateTx(ctx, tx, subscriptionRecord); err != nil {
		return err
	}
	if err := h.usersRepo.UpdateSubscriptionTierTx(
		ctx,
		tx,
		userID,
		tier,
		stripeCustomerID,
		stripeSubID,
		service.TierAlertLimit[tier],
		endsAt,
	); err != nil {
		return err
	}

	return tx.Commit(ctx)
}

func (h *SubscriptionsHandler) handleCustomerSubscriptionUpdated(ctx context.Context, raw []byte) error {
	var payload stripeSubscriptionPayload
	if err := json.Unmarshal(raw, &payload); err != nil {
		return err
	}

	status, ok := mapStripeSubscriptionStatus(payload.Status)
	if !ok {
		return nil
	}

	currentSub, err := h.subsRepo.GetByStripeSubID(ctx, strings.TrimSpace(payload.ID))
	if err != nil {
		return err
	}
	userID, err := uuidFromPGType(currentSub.UserID)
	if err != nil {
		return err
	}

	tier, ok := parsePaidSubscriptionTier(payload.Metadata["tier"])
	if !ok {
		tier = currentSub.Tier
	}

	billingPeriod := billingPeriodFromWebhookSubscription(payload)
	if billingPeriod == "" {
		billingPeriod = currentSub.BillingPeriod
	}
	if billingPeriod == "" {
		return errors.New("missing billing period")
	}

	currentPeriodStart, err := requiredUnixTime(payload.CurrentPeriodStart)
	if err != nil {
		return err
	}
	currentPeriodEnd, err := requiredUnixTime(payload.CurrentPeriodEnd)
	if err != nil {
		return err
	}
	trialEndAt := optionalUnixTime(payload.TrialEnd)

	stripeCustomerID, err := expandableID(payload.Customer)
	if err != nil {
		return err
	}
	if stripeCustomerID == "" {
		stripeCustomerID = currentSub.StripeCustomerID
	}

	tx, err := h.subsRepo.BeginTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if err := h.subsRepo.UpdateStatusTx(
		ctx,
		tx,
		payload.ID,
		tier,
		status,
		billingPeriod,
		currentPeriodStart,
		currentPeriodEnd,
		trialEndAt,
	); err != nil {
		return err
	}
	if err := h.usersRepo.UpdateSubscriptionTierTx(
		ctx,
		tx,
		userID,
		tier,
		stripeCustomerID,
		payload.ID,
		service.TierAlertLimit[tier],
		&currentPeriodEnd,
	); err != nil {
		return err
	}
	if err := tx.Commit(ctx); err != nil {
		return err
	}

	if status != "past_due" {
		if err := h.redisClient.ZRem(ctx, stripePendingDowngradesKey, userID.String()).Err(); err != nil {
			return err
		}
	}
	return nil
}

func (h *SubscriptionsHandler) handleCustomerSubscriptionDeleted(ctx context.Context, raw []byte) error {
	var payload stripeSubscriptionPayload
	if err := json.Unmarshal(raw, &payload); err != nil {
		return err
	}

	currentSub, err := h.subsRepo.GetByStripeSubID(ctx, strings.TrimSpace(payload.ID))
	if err != nil {
		return err
	}
	userID, err := uuidFromPGType(currentSub.UserID)
	if err != nil {
		return err
	}

	tx, err := h.subsRepo.BeginTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if err := h.subsRepo.CancelTx(ctx, tx, payload.ID); err != nil {
		return err
	}
	if err := h.usersRepo.DowngradeToFreeTx(ctx, tx, userID); err != nil {
		return err
	}
	if err := tx.Commit(ctx); err != nil {
		return err
	}

	return h.redisClient.ZRem(ctx, stripePendingDowngradesKey, userID.String()).Err()
}

func (h *SubscriptionsHandler) handleInvoicePaymentFailed(ctx context.Context, raw []byte) error {
	var payload stripeInvoicePayload
	if err := json.Unmarshal(raw, &payload); err != nil {
		return err
	}

	stripeSubID, err := expandableID(payload.Subscription)
	if err != nil {
		return err
	}

	currentSub, err := h.subsRepo.GetByStripeSubID(ctx, stripeSubID)
	if err != nil {
		return err
	}
	userID, err := uuidFromPGType(currentSub.UserID)
	if err != nil {
		return err
	}

	now := time.Now().UTC()
	if err := h.subsRepo.SetPaymentFailed(ctx, stripeSubID, now); err != nil {
		return err
	}
	return h.redisClient.ZAdd(ctx, stripePendingDowngradesKey, redis.Z{
		Score:  float64(now.Add(72 * time.Hour).Unix()),
		Member: userID.String(),
	}).Err()
}

func (h *SubscriptionsHandler) handleInvoicePaymentSucceeded(ctx context.Context, raw []byte) error {
	var payload stripeInvoicePayload
	if err := json.Unmarshal(raw, &payload); err != nil {
		return err
	}

	stripeSubID, err := expandableID(payload.Subscription)
	if err != nil {
		return err
	}

	currentSub, err := h.subsRepo.GetByStripeSubID(ctx, stripeSubID)
	if err != nil {
		return err
	}
	userID, err := uuidFromPGType(currentSub.UserID)
	if err != nil {
		return err
	}

	if err := h.subsRepo.ClearPaymentFailed(ctx, stripeSubID); err != nil {
		return err
	}
	return h.redisClient.ZRem(ctx, stripePendingDowngradesKey, userID.String()).Err()
}

func parsePaidSubscriptionTier(raw string) (models.SubscriptionTier, bool) {
	switch tier := models.SubscriptionTier(strings.ToLower(strings.TrimSpace(raw))); tier {
	case models.SubscriptionTierBasic, models.SubscriptionTierPro, models.SubscriptionTierGlobal, models.SubscriptionTierAPI:
		return tier, true
	default:
		return "", false
	}
}

func mapStripeSubscriptionStatus(status string) (string, bool) {
	switch strings.ToLower(strings.TrimSpace(status)) {
	case "trialing":
		return "trialing", true
	case "active":
		return "active", true
	case "past_due", "unpaid":
		return "past_due", true
	case "canceled", "cancelled":
		return "cancelled", true
	default:
		return "", false
	}
}

func subscriptionModelFromStripe(
	userID uuid.UUID,
	stripeCustomerID,
	stripeSubID string,
	tier models.SubscriptionTier,
	fallbackBillingPeriod string,
	sub *stripe.Subscription,
) (*models.Subscription, *time.Time, error) {
	if sub == nil {
		return nil, nil, errors.New("missing Stripe subscription")
	}

	status, ok := mapStripeSubscriptionStatus(string(sub.Status))
	if !ok {
		return nil, nil, errors.New("unsupported Stripe subscription status")
	}

	currentPeriodStart, err := requiredUnixTime(sub.CurrentPeriodStart)
	if err != nil {
		return nil, nil, err
	}
	currentPeriodEnd, err := requiredUnixTime(sub.CurrentPeriodEnd)
	if err != nil {
		return nil, nil, err
	}

	billingPeriod := billingPeriodFromStripeSubscription(sub)
	if billingPeriod == "" {
		billingPeriod = normalizeBillingPeriod(fallbackBillingPeriod)
	}
	if billingPeriod == "" {
		return nil, nil, errors.New("missing billing period")
	}

	record := &models.Subscription{
		UserID:             pgUUIDValue(userID),
		StripeCustomerID:   stripeCustomerID,
		StripeSubID:        stripeSubID,
		Tier:               tier,
		Status:             status,
		BillingPeriod:      billingPeriod,
		CurrentPeriodStart: pgTimeValue(currentPeriodStart),
		CurrentPeriodEnd:   pgTimeValue(currentPeriodEnd),
		TrialEndAt:         pgTimePointer(optionalUnixTime(&sub.TrialEnd)),
	}
	return record, &currentPeriodEnd, nil
}

func billingPeriodFromWebhookSubscription(payload stripeSubscriptionPayload) string {
	for _, item := range payload.Items.Data {
		if period := normalizeStripeInterval(item.Price.Recurring.Interval); period != "" {
			return period
		}
	}
	return normalizeBillingPeriod(payload.Metadata["billing_period"])
}

func billingPeriodFromStripeSubscription(sub *stripe.Subscription) string {
	if sub == nil || sub.Items == nil {
		return ""
	}
	for _, item := range sub.Items.Data {
		if item == nil || item.Price == nil || item.Price.Recurring == nil {
			continue
		}
		if period := normalizeStripeInterval(string(item.Price.Recurring.Interval)); period != "" {
			return period
		}
	}
	return ""
}

func normalizeBillingPeriod(raw string) string {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "monthly":
		return "monthly"
	case "annual":
		return "annual"
	default:
		return ""
	}
}

func normalizeStripeInterval(raw string) string {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "month":
		return "monthly"
	case "year":
		return "annual"
	default:
		return ""
	}
}

func expandableID(raw json.RawMessage) (string, error) {
	if len(raw) == 0 || string(raw) == "null" {
		return "", nil
	}

	var id string
	if err := json.Unmarshal(raw, &id); err == nil {
		return strings.TrimSpace(id), nil
	}

	var obj struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(raw, &obj); err == nil {
		return strings.TrimSpace(obj.ID), nil
	}

	return "", errors.New("invalid expandable id")
}

func requiredUnixTime(raw int64) (time.Time, error) {
	if raw <= 0 {
		return time.Time{}, errors.New("missing timestamp")
	}
	return time.Unix(raw, 0).UTC(), nil
}

func optionalUnixTime(raw *int64) *time.Time {
	if raw == nil || *raw <= 0 {
		return nil
	}
	value := time.Unix(*raw, 0).UTC()
	return &value
}

func pgUUIDValue(id uuid.UUID) pgtype.UUID {
	return pgtype.UUID{Bytes: id, Valid: true}
}

func pgTimeValue(value time.Time) pgtype.Timestamptz {
	return pgtype.Timestamptz{Time: value.UTC(), Valid: true}
}

func pgTimePointer(value *time.Time) *pgtype.Timestamptz {
	if value == nil {
		return nil
	}
	ts := pgtype.Timestamptz{Time: value.UTC(), Valid: true}
	return &ts
}

func uuidFromPGType(id pgtype.UUID) (uuid.UUID, error) {
	if !id.Valid {
		return uuid.Nil, errors.New("invalid UUID")
	}
	return uuid.UUID(id.Bytes), nil
}

func stringPtrOrNil(value string) *string {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	cleaned := strings.TrimSpace(value)
	return &cleaned
}

func formatPGTime(value *pgtype.Timestamptz) *string {
	if value == nil || !value.Valid {
		return nil
	}
	formatted := value.Time.UTC().Format(time.RFC3339)
	return &formatted
}
