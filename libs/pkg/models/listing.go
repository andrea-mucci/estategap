package models

import (
	"encoding/json"

	"github.com/jackc/pgx/v5/pgtype"
	"github.com/shopspring/decimal"
)

type Listing struct {
	ID                  pgtype.UUID         `json:"id" db:"id"`
	CanonicalID         *pgtype.UUID        `json:"canonical_id" db:"canonical_id"`
	Country             string              `json:"country" db:"country"`
	Source              string              `json:"source" db:"source"`
	SourceID            string              `json:"source_id" db:"source_id"`
	SourceURL           string              `json:"source_url" db:"source_url"`
	PortalID            *pgtype.UUID        `json:"portal_id" db:"portal_id"`
	Address             *string             `json:"address" db:"address"`
	Neighborhood        *string             `json:"neighborhood" db:"neighborhood"`
	District            *string             `json:"district" db:"district"`
	City                *string             `json:"city" db:"city"`
	Region              *string             `json:"region" db:"region"`
	PostalCode          *string             `json:"postal_code" db:"postal_code"`
	LocationWKT         *string             `json:"location_wkt,omitempty" db:"location_wkt"`
	ZoneID              *pgtype.UUID        `json:"zone_id" db:"zone_id"`
	AskingPrice         *decimal.Decimal    `json:"asking_price" db:"asking_price"`
	Currency            string              `json:"currency" db:"currency"`
	AskingPriceEUR      *decimal.Decimal    `json:"asking_price_eur" db:"asking_price_eur"`
	PriceConverted      *decimal.Decimal    `json:"price_converted,omitempty" db:"price_converted"`
	PricePerM2EUR       *decimal.Decimal    `json:"price_per_m2_eur" db:"price_per_m2_eur"`
	PropertyCategory    *PropertyCategory   `json:"property_category" db:"property_category"`
	PropertyType        *string             `json:"property_type" db:"property_type"`
	BuiltAreaM2         *decimal.Decimal    `json:"built_area_m2" db:"built_area_m2"`
	UsableAreaM2        *decimal.Decimal    `json:"usable_area_m2" db:"usable_area_m2"`
	PlotAreaM2          *decimal.Decimal    `json:"plot_area_m2" db:"plot_area_m2"`
	Bedrooms            *int16              `json:"bedrooms" db:"bedrooms"`
	Bathrooms           *int16              `json:"bathrooms" db:"bathrooms"`
	Toilets             *int16              `json:"toilets,omitempty" db:"toilets"`
	FloorNumber         *int16              `json:"floor_number,omitempty" db:"floor_number"`
	TotalFloors         *int16              `json:"total_floors,omitempty" db:"total_floors"`
	ParkingSpaces       *int16              `json:"parking_spaces,omitempty" db:"parking_spaces"`
	HasLift             *bool               `json:"has_lift,omitempty" db:"has_lift"`
	HasPool             *bool               `json:"has_pool,omitempty" db:"has_pool"`
	HasGarden           *bool               `json:"has_garden,omitempty" db:"has_garden"`
	TerraceAreaM2       *decimal.Decimal    `json:"terrace_area_m2,omitempty" db:"terrace_area_m2"`
	GarageAreaM2        *decimal.Decimal    `json:"garage_area_m2,omitempty" db:"garage_area_m2"`
	YearBuilt           *int16              `json:"year_built,omitempty" db:"year_built"`
	LastRenovated       *int16              `json:"last_renovated,omitempty" db:"last_renovated"`
	Condition           *string             `json:"condition,omitempty" db:"condition"`
	EnergyRating        *string             `json:"energy_rating,omitempty" db:"energy_rating"`
	EnergyRatingKWH     *decimal.Decimal    `json:"energy_rating_kwh,omitempty" db:"energy_rating_kwh"`
	CO2Rating           *string             `json:"co2_rating,omitempty" db:"co2_rating"`
	CO2KgM2             *decimal.Decimal    `json:"co2_kg_m2,omitempty" db:"co2_kg_m2"`
	FrontageM           *decimal.Decimal    `json:"frontage_m,omitempty" db:"frontage_m"`
	CeilingHeightM      *decimal.Decimal    `json:"ceiling_height_m,omitempty" db:"ceiling_height_m"`
	LoadingDocks        *int16              `json:"loading_docks,omitempty" db:"loading_docks"`
	PowerKW             *decimal.Decimal    `json:"power_kw,omitempty" db:"power_kw"`
	OfficeAreaM2        *decimal.Decimal    `json:"office_area_m2,omitempty" db:"office_area_m2"`
	WarehouseAreaM2     *decimal.Decimal    `json:"warehouse_area_m2,omitempty" db:"warehouse_area_m2"`
	BuildabilityIndex   *decimal.Decimal    `json:"buildability_index,omitempty" db:"buildability_index"`
	UrbanClassification *string             `json:"urban_classification,omitempty" db:"urban_classification"`
	LandUse             *string             `json:"land_use,omitempty" db:"land_use"`
	EstimatedPrice      *decimal.Decimal    `json:"estimated_price" db:"estimated_price_eur"`
	DealScore           *decimal.Decimal    `json:"deal_score" db:"deal_score"`
	DealTier            *DealTier           `json:"deal_tier" db:"deal_tier"`
	ConfidenceLow       *decimal.Decimal    `json:"confidence_low" db:"confidence_low_eur"`
	ConfidenceHigh      *decimal.Decimal    `json:"confidence_high" db:"confidence_high_eur"`
	ShapFeatures        json.RawMessage     `json:"shap_features" db:"shap_features"`
	ComparableIDs       []pgtype.UUID       `json:"comparable_ids,omitempty" db:"comparable_ids"`
	ModelVersion        *string             `json:"model_version" db:"model_version"`
	ScoredAt            *pgtype.Timestamptz `json:"scored_at" db:"scored_at"`
	DaysOnMarket        *int32              `json:"days_on_market" db:"days_on_market"`
	Status              ListingStatus       `json:"status" db:"status"`
	DescriptionOrig     *string             `json:"description_orig,omitempty" db:"description_orig"`
	DescriptionLang     *string             `json:"description_lang,omitempty" db:"description_lang"`
	ImagesCount         int16               `json:"images_count" db:"images_count"`
	FirstSeenAt         pgtype.Timestamptz  `json:"first_seen_at" db:"first_seen_at"`
	ExchangeRateDate    pgtype.Date         `json:"-" db:"exchange_rate_date"`
	LastSeenAt          pgtype.Timestamptz  `json:"last_seen_at" db:"last_seen_at"`
	PublishedAt         *pgtype.Timestamptz `json:"published_at" db:"published_at"`
	DelistedAt          *pgtype.Timestamptz `json:"delisted_at" db:"delisted_at"`
	RawHash             *string             `json:"raw_hash,omitempty" db:"raw_hash"`
	CreatedAt           pgtype.Timestamptz  `json:"created_at" db:"created_at"`
	UpdatedAt           pgtype.Timestamptz  `json:"updated_at" db:"updated_at"`
}

type PriceHistory struct {
	ID          int64              `json:"id" db:"id"`
	ListingID   pgtype.UUID        `json:"listing_id" db:"listing_id"`
	Country     string             `json:"country" db:"country"`
	OldPrice    *decimal.Decimal   `json:"old_price" db:"old_price"`
	NewPrice    decimal.Decimal    `json:"new_price" db:"new_price"`
	Currency    string             `json:"currency" db:"currency"`
	OldPriceEUR *decimal.Decimal   `json:"old_price_eur" db:"old_price_eur"`
	NewPriceEUR *decimal.Decimal   `json:"new_price_eur" db:"new_price_eur"`
	ChangeType  string             `json:"change_type" db:"change_type"`
	OldStatus   *ListingStatus     `json:"old_status" db:"old_status"`
	NewStatus   *ListingStatus     `json:"new_status" db:"new_status"`
	RecordedAt  pgtype.Timestamptz `json:"recorded_at" db:"recorded_at"`
	Source      *string            `json:"source" db:"source"`
}
