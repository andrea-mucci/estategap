package repository

import (
	"context"
	"errors"
	"time"

	"github.com/estategap/libs/models"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

const subscriptionColumns = `
id, user_id, stripe_customer_id, stripe_sub_id, tier, status, billing_period,
current_period_start, current_period_end, trial_end_at, payment_failed_at, created_at, updated_at
`

type subscriptionExecQuerier interface {
	Exec(ctx context.Context, sql string, arguments ...any) (pgconn.CommandTag, error)
}

type SubscriptionsRepo struct {
	primary *pgxpool.Pool
	replica *pgxpool.Pool
}

func NewSubscriptionsRepo(primary, replica *pgxpool.Pool) *SubscriptionsRepo {
	return &SubscriptionsRepo{primary: primary, replica: replica}
}

func (r *SubscriptionsRepo) BeginTx(ctx context.Context) (pgx.Tx, error) {
	return r.primary.BeginTx(ctx, pgx.TxOptions{})
}

func (r *SubscriptionsRepo) Create(ctx context.Context, sub *models.Subscription) error {
	return r.create(ctx, r.primary, sub)
}

func (r *SubscriptionsRepo) CreateTx(ctx context.Context, tx pgx.Tx, sub *models.Subscription) error {
	return r.create(ctx, tx, sub)
}

func (r *SubscriptionsRepo) GetByUserID(ctx context.Context, userID uuid.UUID) (*models.Subscription, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT `+subscriptionColumns+`
		FROM subscriptions
		WHERE user_id = $1 AND status != 'cancelled'
		ORDER BY created_at DESC
		LIMIT 1`, pgUUID(userID))
	if err != nil {
		return nil, err
	}
	item, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.Subscription])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return item, err
}

func (r *SubscriptionsRepo) GetByStripeSubID(ctx context.Context, stripeSubID string) (*models.Subscription, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT `+subscriptionColumns+`
		FROM subscriptions
		WHERE stripe_sub_id = $1
		LIMIT 1`, stripeSubID)
	if err != nil {
		return nil, err
	}
	item, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.Subscription])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return item, err
}

func (r *SubscriptionsRepo) UpdateStatus(
	ctx context.Context,
	stripeSubID string,
	tier models.SubscriptionTier,
	status,
	billingPeriod string,
	currentPeriodStart,
	currentPeriodEnd time.Time,
	trialEndAt *time.Time,
) error {
	return r.updateStatus(ctx, r.primary, stripeSubID, tier, status, billingPeriod, currentPeriodStart, currentPeriodEnd, trialEndAt)
}

func (r *SubscriptionsRepo) UpdateStatusTx(
	ctx context.Context,
	tx pgx.Tx,
	stripeSubID string,
	tier models.SubscriptionTier,
	status,
	billingPeriod string,
	currentPeriodStart,
	currentPeriodEnd time.Time,
	trialEndAt *time.Time,
) error {
	return r.updateStatus(ctx, tx, stripeSubID, tier, status, billingPeriod, currentPeriodStart, currentPeriodEnd, trialEndAt)
}

func (r *SubscriptionsRepo) SetPaymentFailed(ctx context.Context, stripeSubID string, failedAt time.Time) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE subscriptions
		SET status = 'past_due',
			payment_failed_at = $2,
			updated_at = NOW()
		WHERE stripe_sub_id = $1`, stripeSubID, failedAt.UTC())
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *SubscriptionsRepo) ClearPaymentFailed(ctx context.Context, stripeSubID string) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE subscriptions
		SET payment_failed_at = NULL,
			updated_at = NOW()
		WHERE stripe_sub_id = $1`, stripeSubID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *SubscriptionsRepo) Cancel(ctx context.Context, stripeSubID string) error {
	return r.cancel(ctx, r.primary, stripeSubID)
}

func (r *SubscriptionsRepo) CancelTx(ctx context.Context, tx pgx.Tx, stripeSubID string) error {
	return r.cancel(ctx, tx, stripeSubID)
}

func (r *SubscriptionsRepo) create(ctx context.Context, exec subscriptionExecQuerier, sub *models.Subscription) error {
	tag, err := exec.Exec(ctx, `
		INSERT INTO subscriptions (
			user_id, stripe_customer_id, stripe_sub_id, tier, status, billing_period,
			current_period_start, current_period_end, trial_end_at, payment_failed_at
		)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		sub.UserID,
		sub.StripeCustomerID,
		sub.StripeSubID,
		sub.Tier,
		sub.Status,
		sub.BillingPeriod,
		sub.CurrentPeriodStart,
		sub.CurrentPeriodEnd,
		sub.TrialEndAt,
		sub.PaymentFailedAt,
	)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *SubscriptionsRepo) updateStatus(
	ctx context.Context,
	exec subscriptionExecQuerier,
	stripeSubID string,
	tier models.SubscriptionTier,
	status,
	billingPeriod string,
	currentPeriodStart,
	currentPeriodEnd time.Time,
	trialEndAt *time.Time,
) error {
	tag, err := exec.Exec(ctx, `
		UPDATE subscriptions
		SET tier = $2,
			status = $3,
			billing_period = $4,
			current_period_start = $5,
			current_period_end = $6,
			trial_end_at = $7,
			payment_failed_at = CASE WHEN $3 = 'past_due' THEN payment_failed_at ELSE NULL END,
			updated_at = NOW()
		WHERE stripe_sub_id = $1`,
		stripeSubID,
		tier,
		status,
		billingPeriod,
		currentPeriodStart.UTC(),
		currentPeriodEnd.UTC(),
		trialEndAt,
	)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *SubscriptionsRepo) cancel(ctx context.Context, exec subscriptionExecQuerier, stripeSubID string) error {
	tag, err := exec.Exec(ctx, `
		UPDATE subscriptions
		SET status = 'cancelled',
			payment_failed_at = NULL,
			updated_at = NOW()
		WHERE stripe_sub_id = $1`, stripeSubID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}
