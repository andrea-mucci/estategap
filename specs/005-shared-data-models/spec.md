# Feature Specification: Shared Data Models

**Feature Branch**: `005-shared-data-models`
**Created**: 2026-04-16
**Status**: Draft
**Input**: User description: "Create shared data models in both Python (Pydantic v2) and Go that mirror the database schema and are used across all services."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pipeline Service Validates Listing Data (Priority: P1)

A pipeline developer writes a scraper that emits raw listing records. Before any record reaches the database, the shared Python model rejects invalid data — negative prices, zero areas, unrecognised country codes — so bad records never pollute downstream consumers.

**Why this priority**: Data quality at ingestion is the highest-value use of shared models. All other services depend on the guarantee that persisted listings are valid.

**Independent Test**: Instantiate a `RawListing` with invalid fields and confirm `ValidationError` is raised; instantiate a valid one and confirm it serialises to JSON that Go can unmarshal without error.

**Acceptance Scenarios**:

1. **Given** a raw listing payload with `asking_price = -500`, **When** a `RawListing` model is constructed, **Then** a validation error is raised citing the price constraint.
2. **Given** a raw listing payload with `country_code = "XX"` (invalid ISO 3166-1), **When** a `RawListing` model is constructed, **Then** a validation error is raised citing the country code constraint.
3. **Given** a fully valid raw listing payload, **When** a `RawListing` model is constructed and serialised to JSON, **Then** the JSON is parseable by the Go equivalent without error.

---

### User Story 2 - API Service Serialises Listing Responses (Priority: P2)

A Go API developer uses the shared `Listing` struct to scan a database row and immediately serialise it as a JSON response. JSON field names and null handling match exactly what the Python pipeline wrote, so no translation layer is needed.

**Why this priority**: The Go models are the outbound API contract. Consistency with Python output prevents field-name drift that would break API consumers.

**Independent Test**: Scan a mock `pgx` row into a `Listing` struct, marshal to JSON, and assert that field names, UUID format, and RFC 3339 timestamps match Python's serialised output.

**Acceptance Scenarios**:

1. **Given** a database row for an active listing, **When** the Go service scans the row into a `Listing` struct, **Then** all fields are populated without error.
2. **Given** an optional nullable field (e.g. `delisted_at`) that is NULL in the database, **When** the struct is marshalled to JSON, **Then** the field appears as `null` in the output, matching Python's `None` serialisation.

---

### User Story 3 - Alert Rule Filtering Uses Shared Model (Priority: P3)

A notification service (Python or Go) reads an `AlertRule` from the database and evaluates whether a listing matches its JSONB filter. The shared model provides a typed representation of the filter structure, preventing filter keys from being misread or silently ignored.

**Why this priority**: Alert correctness depends on the filter model being the same across services; this is lower priority than core listing models but critical for alert reliability.

**Independent Test**: Deserialise an `AlertRule` from a JSON fixture in both Python and Go; assert that the filter JSONB round-trips without data loss.

**Acceptance Scenarios**:

1. **Given** an `AlertRule` JSON fixture with nested filter conditions, **When** deserialised in Python and re-serialised to JSON, **Then** the output is byte-identical to the input (ignoring key order).
2. **Given** the same fixture, **When** deserialised in Go and marshalled to JSON, **Then** all filter keys and values are present.

---

### Edge Cases

- What happens when a listing has `area_m2 = 0`? → Must be rejected (validator requires `> 0`).
- How does the model handle a `currency_code` outside ISO 4217? → Must be rejected by the currency validator.
- What happens when a `zone_id` FK is present but the referenced zone does not exist in the local test context? → Model accepts the UUID value; referential integrity is the database's concern.
- How are timezone-naive datetimes handled? → Rejected at model construction; all datetimes must be timezone-aware (RFC 3339 with offset).
- What happens when Go receives a Python-serialised `Decimal` price (e.g. `"123456.78"` as string vs number)? → JSON numeric format must be agreed: Python emits a JSON number, Go parses with `shopspring/decimal`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Python library MUST provide `RawListing`, `NormalizedListing`, and `Listing` models with validators that reject `asking_price <= 0`, `area_m2 <= 0`, invalid ISO 3166-1 alpha-2 country codes, and invalid ISO 4217 currency codes.
- **FR-002**: The Python library MUST provide `PriceHistory`, `Zone`, `Country`, `Portal`, `AlertRule`, `ScoringResult`, `ConversationState`, `User`, and `Subscription` models.
- **FR-003**: All Python models MUST use timezone-aware datetimes and reject naive datetimes.
- **FR-004**: The Python library MUST export a JSON Schema document for each model to support documentation and contract testing.
- **FR-005**: The Python library MUST define `PropertyCategory`, `DealTier`, `ListingStatus`, and `SubscriptionTier` enumerations used across services.
- **FR-006**: The Go library MUST provide equivalent structs for `Listing`, `AlertRule`, `ScoringResult`, `User`, `Zone`, and `Country` with `json` and `db` struct tags matching Python serialisation field names.
- **FR-007**: Go structs MUST use `pgtype.UUID` and `pgtype.Timestamptz` for PostgreSQL-compatible scanning.
- **FR-008**: Go structs MUST represent monetary values using `shopspring/decimal` to avoid floating-point precision errors.
- **FR-009**: JSON produced by Python models MUST be parseable by Go's `json.Unmarshal` into the corresponding Go struct, and vice versa, with no data loss.
- **FR-010**: Date/time values MUST be serialised as RFC 3339 strings in both languages.
- **FR-011**: UUID values MUST be serialised in standard `8-4-4-4-12` hyphenated format.
- **FR-012**: Null/None values MUST serialise as JSON `null` in both languages; Go structs MUST use pointer types for nullable fields.

### Key Entities

- **RawListing**: Unvalidated listing as received from a scraper; source URL, portal reference, raw price, raw area, country code.
- **NormalizedListing**: Cleaned listing with EUR-converted price, validated fields, geometry point, zone assignment.
- **Listing**: Fully persisted listing including ML scores, deal tier, SHAP features, and lifecycle timestamps.
- **PriceHistory**: A single price-change event linked to a listing: old price, new price, change type, timestamp.
- **Zone**: Geographic zone with hierarchical parent, geometry, administrative level, country code.
- **Country**: Reference record for a supported country: ISO code, name, default currency, configuration blob.
- **Portal**: Scraper portal definition: country code, spider class name, base URL, active flag.
- **AlertRule**: User-defined alert with a JSONB filter, notification channel configuration, and trigger metadata.
- **ScoringResult**: ML model output for a listing: estimated price, deal score, deal tier, confidence interval, top SHAP features, model version.
- **ConversationState**: AI chat session state: criteria collected so far, pending dimensions, session ID.
- **User**: Registered user account: email, OAuth identity, subscription tier, Stripe identifiers.
- **Subscription**: User subscription record linking tier, Stripe subscription ID, and validity window.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All Python model unit tests pass for both valid and invalid inputs, with 100% of defined validators exercised.
- **SC-002**: A round-trip test serialises a Python model instance to JSON and deserialises it into the corresponding Go struct with zero field-value discrepancies.
- **SC-003**: Pydantic validators catch 100% of the following invalid inputs in automated tests: negative price, zero area, invalid country code (non-ISO 3166-1), naive datetime, invalid currency code (non-ISO 4217).
- **SC-004**: Go struct tests confirm that scanning a mock database row populates all non-nullable fields without error.
- **SC-005**: JSON Schema documents are generated for all Python models and are valid against the JSON Schema Draft 2020-12 meta-schema.

## Assumptions

- The Python models live under `libs/common/models/` within the existing monorepo; a `pyproject.toml` for `common` already exists or will be created as part of this feature.
- The Go models live under `pkg/models/` within the monorepo Go workspace; the `go.work` file will be updated if needed.
- ISO 3166-1 alpha-2 validation uses a hard-coded allowlist of the ~250 active country codes; an external API is not required.
- ISO 4217 validation uses a hard-coded allowlist of common currency codes; exhaustive coverage of all ~170 codes is assumed sufficient.
- The `ConversationState` model is a value object persisted as JSONB; it does not have its own database table.
- `ScoringResult` mirrors the ML output fields already present in the `listings` table (estimated_price, deal_score, deal_tier, confidence_low/high, shap_features, model_version).
- Cross-language round-trip tests are implemented as a small integration fixture (JSON files checked into the test suite) rather than a live service call.
- The Go models do not implement full ORM behaviour; scanning from `pgx` rows is the primary database interaction pattern.
