package models

import (
	"encoding/json"

	"github.com/jackc/pgx/v5/pgtype"
)

type AlertRule struct {
	ID              pgtype.UUID         `json:"id" db:"id"`
	UserID          pgtype.UUID         `json:"user_id" db:"user_id"`
	Name            string              `json:"name" db:"name"`
	Filters         json.RawMessage     `json:"filters" db:"filters"`
	Channels        json.RawMessage     `json:"channels" db:"channels"`
	Active          bool                `json:"active" db:"active"`
	LastTriggeredAt *pgtype.Timestamptz `json:"last_triggered_at" db:"last_triggered_at"`
	TriggerCount    int32               `json:"trigger_count" db:"trigger_count"`
	CreatedAt       pgtype.Timestamptz  `json:"created_at" db:"created_at"`
	UpdatedAt       pgtype.Timestamptz  `json:"updated_at" db:"updated_at"`
}
