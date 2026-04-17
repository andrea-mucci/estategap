package models

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/shopspring/decimal"
)

func fixturePath(name string) string {
	return filepath.Join("..", "..", "..", "tests", "cross_language", "fixtures", name)
}

func loadFixtureBytes(t *testing.T, name string) []byte {
	t.Helper()

	payload, err := os.ReadFile(fixturePath(name))
	if err != nil {
		t.Fatalf("read fixture %s: %v", name, err)
	}
	return payload
}

func decodeJSONMap(t *testing.T, payload []byte) map[string]any {
	t.Helper()

	var decoded map[string]any
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("decode json: %v", err)
	}
	return decoded
}

func assertExpectedFields(t *testing.T, actual, expected map[string]any) {
	t.Helper()

	for key, expectedValue := range expected {
		actualValue, ok := actual[key]
		if !ok {
			t.Fatalf("missing expected key %q", key)
		}
		if !reflect.DeepEqual(actualValue, expectedValue) {
			t.Fatalf("unexpected value for %q: got %#v want %#v", key, actualValue, expectedValue)
		}
	}
}

func mustUUID(t *testing.T, raw string) pgtype.UUID {
	t.Helper()

	parsed, err := uuid.Parse(raw)
	if err != nil {
		t.Fatalf("parse uuid %s: %v", raw, err)
	}

	var value pgtype.UUID
	if err := value.Scan(parsed); err != nil {
		t.Fatalf("scan uuid %s: %v", raw, err)
	}
	return value
}

func mustTimestamptz(t *testing.T, raw string) pgtype.Timestamptz {
	t.Helper()

	parsed, err := time.Parse(time.RFC3339, raw)
	if err != nil {
		t.Fatalf("parse time %s: %v", raw, err)
	}

	var value pgtype.Timestamptz
	if err := value.Scan(parsed); err != nil {
		t.Fatalf("scan timestamptz %s: %v", raw, err)
	}
	return value
}

func mustDecimal(t *testing.T, raw string) decimal.Decimal {
	t.Helper()

	value, err := decimal.NewFromString(raw)
	if err != nil {
		t.Fatalf("parse decimal %s: %v", raw, err)
	}
	return value
}

type fakeRow struct {
	values []any
}

func (r fakeRow) Scan(dest ...any) error {
	if len(dest) != len(r.values) {
		return fmt.Errorf("scan arity mismatch: got %d destinations want %d", len(dest), len(r.values))
	}

	for index, destination := range dest {
		if err := assignScanValue(destination, r.values[index]); err != nil {
			return fmt.Errorf("assign destination %d: %w", index, err)
		}
	}
	return nil
}

func assignScanValue(destination any, value any) error {
	if destination == nil {
		return fmt.Errorf("destination is nil")
	}

	target := reflect.ValueOf(destination)
	if target.Kind() != reflect.Pointer || target.IsNil() {
		return fmt.Errorf("destination must be a non-nil pointer, got %T", destination)
	}

	return setValue(target.Elem(), value)
}

func setValue(target reflect.Value, value any) error {
	if value == nil {
		target.SetZero()
		return nil
	}

	if target.Kind() == reflect.Pointer {
		ptr := reflect.New(target.Type().Elem())
		if err := setValue(ptr.Elem(), value); err != nil {
			return err
		}
		target.Set(ptr)
		return nil
	}

	source := reflect.ValueOf(value)
	if source.Type().AssignableTo(target.Type()) {
		target.Set(source)
		return nil
	}
	if source.Type().ConvertibleTo(target.Type()) {
		target.Set(source.Convert(target.Type()))
		return nil
	}

	return fmt.Errorf("cannot assign %T to %s", value, target.Type())
}

func TestListingRoundTrip(t *testing.T) {
	fixtureBytes := loadFixtureBytes(t, "listing.json")

	var listing Listing
	if err := json.Unmarshal(fixtureBytes, &listing); err != nil {
		t.Fatalf("unmarshal listing fixture: %v", err)
	}

	if listing.Country != "ES" {
		t.Fatalf("unexpected country: %s", listing.Country)
	}
	if listing.DealTier == nil || *listing.DealTier != DealTierGoodDeal {
		t.Fatalf("unexpected deal tier: %#v", listing.DealTier)
	}
	if listing.DelistedAt != nil {
		t.Fatalf("expected nil delisted_at, got %#v", listing.DelistedAt)
	}

	actualBytes, err := json.Marshal(listing)
	if err != nil {
		t.Fatalf("marshal listing fixture: %v", err)
	}

	assertExpectedFields(t, decodeJSONMap(t, actualBytes), decodeJSONMap(t, fixtureBytes))
}

func TestScoringResultRoundTrip(t *testing.T) {
	fixtureBytes := loadFixtureBytes(t, "scoring_result.json")

	var result ScoringResult
	if err := json.Unmarshal(fixtureBytes, &result); err != nil {
		t.Fatalf("unmarshal scoring fixture: %v", err)
	}

	if result.DealTier != DealTierGoodDeal {
		t.Fatalf("unexpected deal tier: %v", result.DealTier)
	}
	if len(result.ShapFeatures) != 3 {
		t.Fatalf("unexpected shap feature count: %d", len(result.ShapFeatures))
	}

	actualBytes, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("marshal scoring fixture: %v", err)
	}

	assertExpectedFields(t, decodeJSONMap(t, actualBytes), decodeJSONMap(t, fixtureBytes))
}

func TestAlertRuleRoundTrip(t *testing.T) {
	fixtureBytes := loadFixtureBytes(t, "alert_rule.json")

	var rule AlertRule
	if err := json.Unmarshal(fixtureBytes, &rule); err != nil {
		t.Fatalf("unmarshal alert fixture: %v", err)
	}

	if len(rule.Filters) == 0 {
		t.Fatal("expected non-empty filters")
	}
	if rule.LastTriggeredAt != nil {
		t.Fatalf("expected nil last_triggered_at, got %#v", rule.LastTriggeredAt)
	}

	actualBytes, err := json.Marshal(rule)
	if err != nil {
		t.Fatalf("marshal alert fixture: %v", err)
	}

	assertExpectedFields(t, decodeJSONMap(t, actualBytes), decodeJSONMap(t, fixtureBytes))
}

func TestListingPgxScan(t *testing.T) {
	listingID := mustUUID(t, "550e8400-e29b-41d4-a716-446655440000")
	zoneID := mustUUID(t, "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
	askingPrice := mustDecimal(t, "450000")
	askingPriceEUR := mustDecimal(t, "450000")
	pricePerM2 := mustDecimal(t, "5625")
	firstSeenAt := mustTimestamptz(t, "2026-04-03T09:15:00Z")
	lastSeenAt := mustTimestamptz(t, "2026-04-17T06:00:00Z")
	createdAt := mustTimestamptz(t, "2026-04-03T09:15:00Z")
	updatedAt := mustTimestamptz(t, "2026-04-17T06:00:00Z")
	propertyCategory := PropertyCategoryResidential
	status := ListingStatusActive
	dealTier := DealTierGoodDeal
	address := "Calle Mayor 1"
	city := "Madrid"

	row := fakeRow{
		values: []any{
			listingID,
			nil,
			"ES",
			"idealista",
			"abc-123",
			"https://www.idealista.com/inmueble/abc-123/",
			nil,
			address,
			city,
			zoneID,
			askingPrice,
			"EUR",
			askingPriceEUR,
			pricePerM2,
			propertyCategory,
			dealTier,
			status,
			firstSeenAt,
			lastSeenAt,
			createdAt,
			updatedAt,
		},
	}

	var listing Listing
	if err := row.Scan(
		&listing.ID,
		&listing.CanonicalID,
		&listing.Country,
		&listing.Source,
		&listing.SourceID,
		&listing.SourceURL,
		&listing.PortalID,
		&listing.Address,
		&listing.City,
		&listing.ZoneID,
		&listing.AskingPrice,
		&listing.Currency,
		&listing.AskingPriceEUR,
		&listing.PricePerM2EUR,
		&listing.PropertyCategory,
		&listing.DealTier,
		&listing.Status,
		&listing.FirstSeenAt,
		&listing.LastSeenAt,
		&listing.CreatedAt,
		&listing.UpdatedAt,
	); err != nil {
		t.Fatalf("scan listing: %v", err)
	}

	if listing.Country != "ES" {
		t.Fatalf("unexpected country: %s", listing.Country)
	}
	if listing.Address == nil || *listing.Address != "Calle Mayor 1" {
		t.Fatalf("unexpected address: %#v", listing.Address)
	}
	if listing.ZoneID == nil {
		t.Fatal("expected non-nil zone id")
	}
	if listing.AskingPrice == nil || !listing.AskingPrice.Equal(askingPrice) {
		t.Fatalf("unexpected asking price: %#v", listing.AskingPrice)
	}
	if listing.PropertyCategory == nil || *listing.PropertyCategory != PropertyCategoryResidential {
		t.Fatalf("unexpected property category: %#v", listing.PropertyCategory)
	}
	if listing.DealTier == nil || *listing.DealTier != DealTierGoodDeal {
		t.Fatalf("unexpected deal tier: %#v", listing.DealTier)
	}
}

func TestNullableFieldsMarshalNull(t *testing.T) {
	listing := Listing{
		ID:          mustUUID(t, "550e8400-e29b-41d4-a716-446655440000"),
		Country:     "ES",
		Source:      "idealista",
		SourceID:    "abc-123",
		SourceURL:   "https://www.idealista.com/inmueble/abc-123/",
		Currency:    "EUR",
		Status:      ListingStatusActive,
		ImagesCount: 0,
		FirstSeenAt: mustTimestamptz(t, "2026-04-03T09:15:00Z"),
		LastSeenAt:  mustTimestamptz(t, "2026-04-17T06:00:00Z"),
		CreatedAt:   mustTimestamptz(t, "2026-04-03T09:15:00Z"),
		UpdatedAt:   mustTimestamptz(t, "2026-04-17T06:00:00Z"),
	}

	payload, err := json.Marshal(listing)
	if err != nil {
		t.Fatalf("marshal listing: %v", err)
	}

	decoded := decodeJSONMap(t, payload)
	for _, field := range []string{"canonical_id", "portal_id", "asking_price", "delisted_at"} {
		if decoded[field] != nil {
			t.Fatalf("expected %s to be null, got %#v", field, decoded[field])
		}
	}
}
