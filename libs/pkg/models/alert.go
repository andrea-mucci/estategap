package models

import (
	"encoding/json"

	"github.com/jackc/pgx/v5/pgtype"
)

type AlertRule struct {
	ID        pgtype.UUID        `json:"id" db:"id"`
	UserID    pgtype.UUID        `json:"user_id" db:"user_id"`
	Name      string             `json:"name" db:"name"`
	ZoneIDs   []pgtype.UUID      `json:"zone_ids" db:"zone_ids"`
	Category  string             `json:"category" db:"category"`
	Filter    json.RawMessage    `json:"filter" db:"filter"`
	Channels  json.RawMessage    `json:"channels" db:"channels"`
	IsActive  bool               `json:"is_active" db:"is_active"`
	Frequency string             `json:"frequency" db:"frequency"`
	CreatedAt pgtype.Timestamptz `json:"created_at" db:"created_at"`
	UpdatedAt pgtype.Timestamptz `json:"updated_at" db:"updated_at"`
}
