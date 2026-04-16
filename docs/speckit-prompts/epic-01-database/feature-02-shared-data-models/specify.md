# Feature: Shared Data Models

## /specify prompt

```
Create shared data models in both Python (Pydantic v2) and Go that mirror the database schema and are used across all services.

## What
Python (libs/common/models/):
- Listing, RawListing, NormalizedListing: full listing data with validators (price > 0, area > 0, valid country codes, valid currency codes)
- PriceHistory: single price change record
- Zone: geographic zone with hierarchy
- Country, Portal: reference data
- AlertRule: user alert configuration with JSONB filter structure
- ScoringResult: ML score output (estimated_price, deal_score, tier, confidence, SHAP top features)
- ConversationState: AI chat criteria state with pending dimensions
- User, Subscription: user account data

Go (pkg/models/):
- Equivalent structs for: Listing, AlertRule, ScoringResult, User, Zone, Country
- JSON tags matching Python output for API compatibility
- pgx-compatible types (pgtype.UUID, pgtype.Timestamptz, etc.)

## Why
A single source of truth for data structures prevents schema drift between services. Python models validate data at pipeline boundaries. Go models serialize API responses.

## Acceptance Criteria
- All Python models pass unit tests with valid and invalid data
- JSON serialization round-trips correctly between Python and Go
- Pydantic validators catch: negative prices, zero areas, invalid country codes, future dates
- Go structs scan correctly from pgx database rows
```
