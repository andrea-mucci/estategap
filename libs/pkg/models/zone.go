package models

import (
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/shopspring/decimal"
)

type Zone struct {
	ID          pgtype.UUID         `json:"id" db:"id"`
	Name        string              `json:"name" db:"name"`
	NameLocal   *string             `json:"name_local" db:"name_local"`
	CountryCode string              `json:"country_code" db:"country_code"`
	Level       int16               `json:"level" db:"level"`
	ParentID    *pgtype.UUID        `json:"parent_id" db:"parent_id"`
	GeometryWKT *string             `json:"geometry_wkt" db:"geometry_wkt"`
	BBoxWKT     *string             `json:"bbox_wkt" db:"bbox_wkt"`
	Population  *int32              `json:"population" db:"population"`
	AreaKm2     *decimal.Decimal    `json:"area_km2" db:"area_km2"`
	Slug        *string             `json:"slug" db:"slug"`
	OsmID       *int64              `json:"osm_id" db:"osm_id"`
	CreatedAt   *pgtype.Timestamptz `json:"created_at" db:"created_at"`
	UpdatedAt   *pgtype.Timestamptz `json:"updated_at" db:"updated_at"`
}
