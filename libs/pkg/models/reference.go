package models

import (
	"encoding/json"

	"github.com/jackc/pgx/v5/pgtype"
)

type Country struct {
	Code      string             `json:"code" db:"code"`
	Name      string             `json:"name" db:"name"`
	Currency  string             `json:"currency" db:"currency"`
	Active    bool               `json:"active" db:"active"`
	Config    json.RawMessage    `json:"config" db:"config"`
	CreatedAt pgtype.Timestamptz `json:"created_at" db:"created_at"`
	UpdatedAt pgtype.Timestamptz `json:"updated_at" db:"updated_at"`
}

type Portal struct {
	ID          pgtype.UUID        `json:"id" db:"id"`
	Name        string             `json:"name" db:"name"`
	CountryCode string             `json:"country_code" db:"country_code"`
	BaseURL     string             `json:"base_url" db:"base_url"`
	SpiderClass string             `json:"spider_class" db:"spider_class"`
	Enabled     bool               `json:"enabled" db:"enabled"`
	Config      json.RawMessage    `json:"config" db:"config"`
	CreatedAt   pgtype.Timestamptz `json:"created_at" db:"created_at"`
	UpdatedAt   pgtype.Timestamptz `json:"updated_at" db:"updated_at"`
}
