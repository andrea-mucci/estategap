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

const userColumns = `
id, email, password_hash, oauth_provider, oauth_subject, display_name, avatar_url,
subscription_tier, preferred_currency, allowed_countries, stripe_customer_id, stripe_sub_id, subscription_ends_at, alert_limit,
email_verified, email_verified_at, last_login_at, deleted_at, created_at, updated_at
`

type UsersRepo struct {
	primary *pgxpool.Pool
	replica *pgxpool.Pool
}

type userExecQuerier interface {
	Exec(ctx context.Context, sql string, arguments ...any) (pgconn.CommandTag, error)
}

func NewUsersRepo(primary, replica *pgxpool.Pool) *UsersRepo {
	return &UsersRepo{primary: primary, replica: replica}
}

func (r *UsersRepo) CreateUser(ctx context.Context, email, passwordHash string) (*models.User, error) {
	rows, err := r.primary.Query(ctx, `
		INSERT INTO users (email, password_hash)
		VALUES ($1, $2)
		RETURNING `+userColumns, email, passwordHash)
	if err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			return nil, ErrConflict
		}
		return nil, err
	}
	user, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.User])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return user, err
}

func (r *UsersRepo) GetUserByEmail(ctx context.Context, email string) (*models.User, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT `+userColumns+`
		FROM users
		WHERE email = $1 AND deleted_at IS NULL
		LIMIT 1`, email)
	if err != nil {
		return nil, err
	}
	user, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.User])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return user, err
}

func (r *UsersRepo) UpdateLastLogin(ctx context.Context, userID uuid.UUID) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE users
		SET last_login_at = NOW(), updated_at = NOW()
		WHERE id = $1 AND deleted_at IS NULL`, pgUUID(userID))
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *UsersRepo) GetUserByID(ctx context.Context, userID uuid.UUID) (*models.User, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT `+userColumns+`
		FROM users
		WHERE id = $1 AND deleted_at IS NULL
		LIMIT 1`, pgUUID(userID))
	if err != nil {
		return nil, err
	}
	user, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.User])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return user, err
}

func (r *UsersRepo) GetUserByOAuth(ctx context.Context, provider, subject string) (*models.User, error) {
	rows, err := r.replica.Query(ctx, `
		SELECT `+userColumns+`
		FROM users
		WHERE oauth_provider = $1 AND oauth_subject = $2 AND deleted_at IS NULL
		LIMIT 1`, provider, subject)
	if err != nil {
		return nil, err
	}
	user, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.User])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return user, err
}

func (r *UsersRepo) CreateOAuthUser(ctx context.Context, email, provider, subject, displayName, avatarURL string) (*models.User, error) {
	rows, err := r.primary.Query(ctx, `
		INSERT INTO users (email, oauth_provider, oauth_subject, display_name, avatar_url)
		VALUES ($1, $2, $3, NULLIF($4, ''), NULLIF($5, ''))
		RETURNING `+userColumns, email, provider, subject, displayName, avatarURL)
	if err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			return nil, ErrConflict
		}
		return nil, err
	}
	user, err := pgx.CollectOneRow(rows, pgx.RowToAddrOfStructByNameLax[models.User])
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return user, err
}

func (r *UsersRepo) LinkOAuth(ctx context.Context, userID uuid.UUID, provider, subject string) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE users
		SET oauth_provider = $2, oauth_subject = $3, updated_at = NOW()
		WHERE id = $1 AND deleted_at IS NULL`, pgUUID(userID), provider, subject)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *UsersRepo) UpdateSubscriptionTier(
	ctx context.Context,
	userID uuid.UUID,
	tier models.SubscriptionTier,
	stripeCustomerID,
	stripeSubID string,
	alertLimit int16,
	endsAt *time.Time,
) error {
	return r.updateSubscriptionTier(ctx, r.primary, userID, tier, stripeCustomerID, stripeSubID, alertLimit, endsAt)
}

func (r *UsersRepo) UpdateSubscriptionTierTx(
	ctx context.Context,
	tx pgx.Tx,
	userID uuid.UUID,
	tier models.SubscriptionTier,
	stripeCustomerID,
	stripeSubID string,
	alertLimit int16,
	endsAt *time.Time,
) error {
	return r.updateSubscriptionTier(ctx, tx, userID, tier, stripeCustomerID, stripeSubID, alertLimit, endsAt)
}

func (r *UsersRepo) DowngradeToFree(ctx context.Context, userID uuid.UUID) error {
	return r.downgradeToFree(ctx, r.primary, userID)
}

func (r *UsersRepo) DowngradeToFreeTx(ctx context.Context, tx pgx.Tx, userID uuid.UUID) error {
	return r.downgradeToFree(ctx, tx, userID)
}

func (r *UsersRepo) updateSubscriptionTier(
	ctx context.Context,
	exec userExecQuerier,
	userID uuid.UUID,
	tier models.SubscriptionTier,
	stripeCustomerID,
	stripeSubID string,
	alertLimit int16,
	endsAt *time.Time,
) error {
	tag, err := exec.Exec(ctx, `
		UPDATE users
		SET subscription_tier = $2,
			stripe_customer_id = NULLIF($3, ''),
			stripe_sub_id = NULLIF($4, ''),
			alert_limit = $5,
			subscription_ends_at = $6,
			updated_at = NOW()
		WHERE id = $1 AND deleted_at IS NULL`,
		pgUUID(userID), tier, stripeCustomerID, stripeSubID, alertLimit, endsAt)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *UsersRepo) downgradeToFree(ctx context.Context, exec userExecQuerier, userID uuid.UUID) error {
	tag, err := exec.Exec(ctx, `
		UPDATE users
		SET subscription_tier = 'free',
			alert_limit = 3,
			subscription_ends_at = NULL,
			updated_at = NOW()
		WHERE id = $1 AND deleted_at IS NULL`, pgUUID(userID))
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *UsersRepo) UpdatePreferredCurrency(ctx context.Context, userID uuid.UUID, currency string) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE users
		SET preferred_currency = $2,
			updated_at = NOW()
		WHERE id = $1 AND deleted_at IS NULL`,
		pgUUID(userID), currency)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}
