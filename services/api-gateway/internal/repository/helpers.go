package repository

import (
	"encoding/base64"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"
)

func pgUUID(id uuid.UUID) pgtype.UUID {
	return pgtype.UUID{Bytes: id, Valid: true}
}

func uuidFromPG(id pgtype.UUID) (uuid.UUID, error) {
	if !id.Valid {
		return uuid.Nil, ErrNotFound
	}
	return uuid.UUID(id.Bytes), nil
}

func encodeTimeCursor(ts time.Time, id uuid.UUID) string {
	return base64.RawURLEncoding.EncodeToString([]byte(fmt.Sprintf("%d|%s", ts.UnixNano(), id.String())))
}

func decodeTimeCursor(cursor string) (time.Time, uuid.UUID, error) {
	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return time.Time{}, uuid.Nil, err
	}

	parts := strings.Split(string(raw), "|")
	if len(parts) != 2 {
		return time.Time{}, uuid.Nil, fmt.Errorf("invalid cursor")
	}

	nanos, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil {
		return time.Time{}, uuid.Nil, err
	}
	id, err := uuid.Parse(parts[1])
	if err != nil {
		return time.Time{}, uuid.Nil, err
	}

	return time.Unix(0, nanos).UTC(), id, nil
}

func encodeFloatCursor(val float64, id uuid.UUID) string {
	return base64.RawURLEncoding.EncodeToString([]byte(fmt.Sprintf("%016x|%s", math.Float64bits(val), id.String())))
}

func decodeFloatCursor(cursor string) (float64, uuid.UUID, error) {
	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return 0, uuid.Nil, err
	}

	parts := strings.Split(string(raw), "|")
	if len(parts) != 2 {
		return 0, uuid.Nil, fmt.Errorf("invalid cursor")
	}

	bits, err := strconv.ParseUint(parts[0], 16, 64)
	if err != nil {
		return 0, uuid.Nil, err
	}
	id, err := uuid.Parse(parts[1])
	if err != nil {
		return 0, uuid.Nil, err
	}

	return math.Float64frombits(bits), id, nil
}

func encodeIDCursor(id uuid.UUID) string {
	return base64.RawURLEncoding.EncodeToString([]byte(id.String()))
}

func decodeIDCursor(cursor string) (uuid.UUID, error) {
	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return uuid.Nil, err
	}
	return uuid.Parse(string(raw))
}

func clampLimit(limit, fallback int) int {
	if limit <= 0 {
		return fallback
	}
	if limit > 100 {
		return 100
	}
	return limit
}
