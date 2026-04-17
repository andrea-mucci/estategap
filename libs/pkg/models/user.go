package models

import "github.com/jackc/pgx/v5/pgtype"

type User struct {
	ID                 pgtype.UUID         `json:"id" db:"id"`
	Email              string              `json:"email" db:"email"`
	PasswordHash       *string             `json:"password_hash" db:"password_hash"`
	OAuthProvider      *string             `json:"oauth_provider" db:"oauth_provider"`
	OAuthSubject       *string             `json:"oauth_subject" db:"oauth_subject"`
	DisplayName        *string             `json:"display_name" db:"display_name"`
	AvatarURL          *string             `json:"avatar_url" db:"avatar_url"`
	SubscriptionTier   SubscriptionTier    `json:"subscription_tier" db:"subscription_tier"`
	StripeCustomerID   *string             `json:"stripe_customer_id" db:"stripe_customer_id"`
	StripeSubID        *string             `json:"stripe_sub_id" db:"stripe_sub_id"`
	SubscriptionEndsAt *pgtype.Timestamptz `json:"subscription_ends_at" db:"subscription_ends_at"`
	AlertLimit         int16               `json:"alert_limit" db:"alert_limit"`
	EmailVerified      bool                `json:"email_verified" db:"email_verified"`
	EmailVerifiedAt    *pgtype.Timestamptz `json:"email_verified_at" db:"email_verified_at"`
	LastLoginAt        *pgtype.Timestamptz `json:"last_login_at" db:"last_login_at"`
	DeletedAt          *pgtype.Timestamptz `json:"deleted_at" db:"deleted_at"`
	CreatedAt          pgtype.Timestamptz  `json:"created_at" db:"created_at"`
	UpdatedAt          pgtype.Timestamptz  `json:"updated_at" db:"updated_at"`
}

type Subscription struct {
	UserID           pgtype.UUID         `json:"user_id" db:"user_id"`
	Tier             SubscriptionTier    `json:"tier" db:"tier"`
	StripeCustomerID *string             `json:"stripe_customer_id" db:"stripe_customer_id"`
	StripeSubID      *string             `json:"stripe_sub_id" db:"stripe_sub_id"`
	StartsAt         pgtype.Timestamptz  `json:"starts_at" db:"starts_at"`
	EndsAt           *pgtype.Timestamptz `json:"ends_at" db:"ends_at"`
	AlertLimit       int16               `json:"alert_limit" db:"alert_limit"`
}
