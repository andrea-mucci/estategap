package models

import (
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/shopspring/decimal"
)

type ShapValue struct {
	FeatureName string  `json:"feature_name" db:"feature_name"`
	Value       float64 `json:"value" db:"value"`
}

type ScoringResult struct {
	ListingID      pgtype.UUID        `json:"listing_id" db:"listing_id"`
	Country        string             `json:"country" db:"country"`
	EstimatedPrice decimal.Decimal    `json:"estimated_price" db:"estimated_price"`
	DealScore      decimal.Decimal    `json:"deal_score" db:"deal_score"`
	DealTier       DealTier           `json:"deal_tier" db:"deal_tier"`
	ConfidenceLow  decimal.Decimal    `json:"confidence_low" db:"confidence_low"`
	ConfidenceHigh decimal.Decimal    `json:"confidence_high" db:"confidence_high"`
	ShapFeatures   []ShapValue        `json:"shap_features" db:"shap_features"`
	ModelVersion   string             `json:"model_version" db:"model_version"`
	ScoredAt       pgtype.Timestamptz `json:"scored_at" db:"scored_at"`
}
