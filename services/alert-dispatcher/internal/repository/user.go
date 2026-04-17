package repository

import (
	"context"
	"errors"
	"strings"

	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

type userReader interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

type userWriter interface {
	Exec(ctx context.Context, sql string, arguments ...any) (pgconn.CommandTag, error)
}

type UserRepo struct {
	primary userWriter
	replica userReader
}

func NewUserRepo(primary, replica *pgxpool.Pool) *UserRepo {
	return &UserRepo{
		primary: primary,
		replica: replica,
	}
}

func NewUserRepoWithClients(primary userWriter, replica userReader) *UserRepo {
	return &UserRepo{
		primary: primary,
		replica: replica,
	}
}

func (r *UserRepo) GetChannelProfile(ctx context.Context, userID string) (*model.UserChannelProfile, error) {
	row := r.replica.QueryRow(ctx, `
		SELECT
			id::text,
			email,
			COALESCE(preferred_language, 'en'),
			telegram_chat_id,
			push_subscription_json,
			phone_e164,
			webhook_secret
		FROM users
		WHERE id = $1::uuid
		LIMIT 1
	`, userID)

	var profile model.UserChannelProfile
	var chatID pgtype.Int8
	var pushToken pgtype.Text
	var phoneE164 pgtype.Text
	var webhookSecret pgtype.Text

	if err := row.Scan(
		&profile.UserID,
		&profile.Email,
		&profile.PreferredLanguage,
		&chatID,
		&pushToken,
		&phoneE164,
		&webhookSecret,
	); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}

	profile.PreferredLanguage = normalizedLanguage(profile.PreferredLanguage)
	if chatID.Valid {
		value := chatID.Int64
		profile.TelegramChatID = &value
	}
	if pushToken.Valid && strings.TrimSpace(pushToken.String) != "" {
		value := strings.TrimSpace(pushToken.String)
		profile.PushToken = &value
	}
	if phoneE164.Valid && strings.TrimSpace(phoneE164.String) != "" {
		value := strings.TrimSpace(phoneE164.String)
		profile.PhoneE164 = &value
	}
	if webhookSecret.Valid {
		value := webhookSecret.String
		profile.WebhookSecret = &value
	}

	return &profile, nil
}

func (r *UserRepo) StoreTelegramChatID(ctx context.Context, userID string, chatID int64) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE users
		SET telegram_chat_id = $2,
			telegram_link_token = NULL
		WHERE id = $1::uuid
	`, userID, chatID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *UserRepo) StoreTelegramChatIDByToken(ctx context.Context, token string, chatID int64) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE users
		SET telegram_chat_id = $2,
			telegram_link_token = NULL
		WHERE telegram_link_token = $1
	`, token, chatID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *UserRepo) ClearPushToken(ctx context.Context, userID string) error {
	tag, err := r.primary.Exec(ctx, `
		UPDATE users
		SET push_subscription_json = NULL
		WHERE id = $1::uuid
	`, userID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func normalizedLanguage(value string) string {
	trimmed := strings.ToLower(strings.TrimSpace(value))
	if trimmed == "" {
		return "en"
	}
	return trimmed
}
