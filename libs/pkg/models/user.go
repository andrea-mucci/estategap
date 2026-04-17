package models

import "github.com/jackc/pgx/v5/pgtype"

type User struct {
	ID                  pgtype.UUID         `json:"id" db:"id"`
	Email               string              `json:"email" db:"email"`
	PasswordHash        *string             `json:"password_hash" db:"password_hash"`
	OAuthProvider       *string             `json:"oauth_provider" db:"oauth_provider"`
	OAuthSubject        *string             `json:"oauth_subject" db:"oauth_subject"`
	DisplayName         *string             `json:"display_name" db:"display_name"`
	AvatarURL           *string             `json:"avatar_url" db:"avatar_url"`
	SubscriptionTier    SubscriptionTier    `json:"subscription_tier" db:"subscription_tier"`
	PreferredCurrency   string              `json:"preferred_currency" db:"preferred_currency"`
	OnboardingCompleted bool                `json:"onboarding_completed" db:"onboarding_completed"`
	AllowedCountries    []string            `json:"allowed_countries" db:"allowed_countries"`
	StripeCustomerID    *string             `json:"stripe_customer_id" db:"stripe_customer_id"`
	StripeSubID         *string             `json:"stripe_sub_id" db:"stripe_sub_id"`
	SubscriptionEndsAt  *pgtype.Timestamptz `json:"subscription_ends_at" db:"subscription_ends_at"`
	AlertLimit          int16               `json:"alert_limit" db:"alert_limit"`
	EmailVerified       bool                `json:"email_verified" db:"email_verified"`
	EmailVerifiedAt     *pgtype.Timestamptz `json:"email_verified_at" db:"email_verified_at"`
	LastLoginAt         *pgtype.Timestamptz `json:"last_login_at" db:"last_login_at"`
	DeletedAt           *pgtype.Timestamptz `json:"deleted_at" db:"deleted_at"`
	CreatedAt           pgtype.Timestamptz  `json:"created_at" db:"created_at"`
	UpdatedAt           pgtype.Timestamptz  `json:"updated_at" db:"updated_at"`
}

type Subscription struct {
	ID                 pgtype.UUID         `json:"id" db:"id"`
	UserID             pgtype.UUID         `json:"user_id" db:"user_id"`
	StripeCustomerID   string              `json:"stripe_customer_id" db:"stripe_customer_id"`
	StripeSubID        string              `json:"stripe_sub_id" db:"stripe_sub_id"`
	Tier               SubscriptionTier    `json:"tier" db:"tier"`
	Status             string              `json:"status" db:"status"`
	BillingPeriod      string              `json:"billing_period" db:"billing_period"`
	CurrentPeriodStart pgtype.Timestamptz  `json:"current_period_start" db:"current_period_start"`
	CurrentPeriodEnd   pgtype.Timestamptz  `json:"current_period_end" db:"current_period_end"`
	TrialEndAt         *pgtype.Timestamptz `json:"trial_end_at" db:"trial_end_at"`
	PaymentFailedAt    *pgtype.Timestamptz `json:"payment_failed_at" db:"payment_failed_at"`
	CreatedAt          pgtype.Timestamptz  `json:"created_at" db:"created_at"`
	UpdatedAt          pgtype.Timestamptz  `json:"updated_at" db:"updated_at"`
}
