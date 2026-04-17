# Research: Shared Data Models

**Feature**: 005-shared-data-models | **Date**: 2026-04-16

---

## Decision 1: Pydantic v2 Validator Pattern

**Decision**: Use `@field_validator` with `mode="before"` for coercion-free validators on primitive fields (str country codes, Decimal prices). Use `model_validator(mode="after")` only when cross-field logic is needed.

**Rationale**: Pydantic v2 `@field_validator` runs at field level with full type information already resolved (when `mode="after"`) or on raw input (`mode="before"`). For country/currency code validation an allowlist check in `mode="after"` is cleanest — the value is already a `str` by then. For numeric validators (`price > 0`) `mode="after"` works on the resolved `Decimal`.

**Alternatives considered**:
- `@model_validator(mode="after")`: Heavier; only needed when two fields interact.
- Annotated types with `Annotated[Decimal, Field(gt=0)]`: Works for simple gt/lt but cannot express allowlist validation cleanly.

---

## Decision 2: ISO 3166-1 Alpha-2 Allowlist

**Decision**: Hard-coded `frozenset` of 249 active ISO 3166-1 alpha-2 codes defined in `_base.py`. No external API call.

**Rationale**: The set of country codes changes at most once every few years (a new country or territory). Hard-coding avoids a network dependency at startup and is fast (O(1) lookup). The allowlist will be maintained alongside the constitution when new target markets are added.

**Alternatives considered**:
- `pycountry` library: Adds a dependency; the full dataset is overkill when EstateGap targets ~15 countries now and ~30 eventually.
- Runtime HTTP fetch: Fragile; fails in air-gapped environments and adds latency.

**Minimal allowlist for current markets** (extendable):
`ES, FR, IT, PT, DE, GB, NL, US, BE, AT, CH, PL, CZ, HU, RO, HR, BG, GR, SE, DK, NO, FI, IE, LU, SK, SI, LT, LV, EE, CY, MT` — plus all other 249 codes from ISO standard.

---

## Decision 3: ISO 4217 Currency Code Allowlist

**Decision**: Hard-coded `frozenset` of ~170 current ISO 4217 alphabetic codes in `_base.py`.

**Rationale**: Same reasoning as ISO 3166-1. Currency codes are even more stable.

---

## Decision 4: Timezone-Aware Datetime Enforcement

**Decision**: Add a `@field_validator("*", mode="before")` on the base class that raises `ValueError` for any `datetime` that is timezone-naive (`tzinfo is None`).

**Rationale**: Python's `datetime` is silently naive by default. Without enforcement a validator could pass a naive datetime and it would serialise without a timezone offset, breaking Go's RFC 3339 parser (which requires an offset).

**Implementation pattern**:
```python
from pydantic import model_validator
import datetime as dt

@model_validator(mode="before")
@classmethod
def _reject_naive_datetimes(cls, values: dict) -> dict:
    for k, v in values.items():
        if isinstance(v, dt.datetime) and v.tzinfo is None:
            raise ValueError(f"Field '{k}' must be timezone-aware")
    return values
```

**Alternatives considered**:
- `AwareDatetime` annotated type (Pydantic v2 built-in): Cleanest solution — use `datetime` fields typed as `AwareDatetime` from `pydantic`. Pydantic raises automatically for naive datetimes. **Selected approach** (simpler than a custom validator).

---

## Decision 5: Go Decimal Representation for Prices

**Decision**: Use `github.com/shopspring/decimal` (`decimal.Decimal`) for all monetary fields (`asking_price`, `asking_price_eur`, `price_per_m2_eur`, `estimated_price`, `confidence_low`, `confidence_high`). JSON marshals as a numeric string to preserve precision.

**Rationale**: `float64` cannot represent `NUMERIC(14,2)` exactly for large values (> 2^53 / 100). `shopspring/decimal` implements `json.Marshaler` producing a JSON number string e.g. `"123456.78"`, which Python's `Decimal` also accepts. The contract: both sides emit and accept decimal strings.

**Alternatives considered**:
- `float64`: Precision loss for prices > ~90 trillion cents. Rejected.
- `int64` (store as cents): Requires agreed multiplier between Python and Go; error-prone.
- `github.com/ericlagergren/decimal`: Smaller ecosystem, fewer pgx integration examples.

**Python side**: `Decimal` already used. JSON: `model_dump(mode="json")` emits `Decimal` as a string by default. Both sides must agree on string representation — confirmed compatible.

---

## Decision 6: Go Nullable Fields — Pointer Types vs pgtype.Text

**Decision**: Use Go pointer types (`*string`, `*decimal.Decimal`, `*time.Time`) for nullable application fields. Use `pgtype.UUID` and `pgtype.Timestamptz` only for primary keys and foreign keys scanned directly from pgx rows, where the pgtype null-indicator is most useful.

**Rationale**: Pointer types (`*T`) marshal to JSON `null` naturally via `encoding/json`, matching Python `None → null`. `pgtype.Text` and `pgtype.Numeric` do not marshal to JSON `null` cleanly without custom marshalers. Mixing approaches per field type keeps JSON clean while still supporting pgx scan for UUID/timestamp fields.

**Alternatives considered**:
- All `pgtype.*` fields: Requires custom JSON marshaling for every nullable type — too much boilerplate.
- `sql.NullString` etc.: Not pgx-native; doesn't work with `pgx.Row.Scan`.

---

## Decision 7: `PropertyCategory` vs `ListingType` Naming

**Decision**: Rename `ListingType` → `PropertyCategory` in Python to match the spec and the DB column name `property_category`. Keep `ListingStatus` as-is (already aligned with DB `status` column).

**Rationale**: The DB column is `property_category VARCHAR(20)`. Using `PropertyCategory` as the enum name avoids confusion with a hypothetical `ListingType` (which could mean residential vs commercial listing record type).

**Values**: `residential | commercial | industrial | land` — matches DB `CHECK` intent and constitution Principle III.

---

## Decision 8: `SubscriptionTier` Enum Values

**Decision**: Replace existing `STARTER / ENTERPRISE` with `basic | pro | global | api` (plus `free`) to match the spec.

**Rationale**: The spec explicitly names these tiers and they will be persisted in `users.subscription_tier VARCHAR(20)`. Changing the enum now (before any production data) avoids a data migration later. The DB column has no CHECK constraint — safe to change.

---

## Decision 9: Cross-Language Round-Trip Test Strategy

**Decision**: Commit static JSON fixtures to `tests/cross_language/fixtures/`. Python tests load each fixture, deserialise into the model, re-serialise, and assert round-trip identity. Go tests load the same fixtures, unmarshal into Go structs, marshal back, and assert field-level equality.

**Rationale**: A static fixture approach is deterministic, runs in CI without live services, and is the simplest way to verify cross-language compatibility. Field-level assertion (not byte-level) is used because JSON key ordering may differ.

**Alternatives considered**:
- Live integration test (Python service emits → Go service parses): Too complex for a library feature; would require two running processes.
- Property-based testing (Hypothesis/Go fuzz): Valuable but secondary; static fixtures cover the contract first.

---

## Decision 10: `NormalizedListing` vs `RawListing` vs `Listing`

**Decision**: Three distinct models with increasing strictness:
- `RawListing`: Permissive — `raw_json: dict | str`, no price validators (raw input from spider)
- `NormalizedListing`: Validated — price/area/country validators active, EUR-converted prices present, `area_m2` required
- `Listing`: Full DB record — includes ML scores, lifecycle timestamps, `deal_tier`, `shap_features`

**Rationale**: The pipeline transforms data through these three stages. Separate models enforce correct data state at each boundary rather than using optional fields with mixed semantics.

**Alternatives considered**:
- Single `Listing` model with all optional fields: Allows invalid intermediate states; harder to test validators.
- Two models only (Raw + Full): Loses the validated-but-unscored intermediate state needed by the pipeline.

---

## Decision 11: `ScoringResult` Field Alignment with DB

**Decision**: `ScoringResult` contains: `listing_id (UUID)`, `country (str)`, `estimated_price (Decimal)`, `deal_score (Decimal)`, `deal_tier (DealTier)`, `confidence_low (Decimal)`, `confidence_high (Decimal)`, `shap_features (list[ShapValue])`, `model_version (str)`, `scored_at (AwareDatetime)`.

**Rationale**: Directly mirrors the scoring columns in the `listings` table. The ML scorer produces this object and the pipeline merges it into the listing record. Having a dedicated `ScoringResult` model prevents the scorer from needing to know the full `Listing` schema.

**`DealTier` enum**: `int` enum with values `1 (great deal) | 2 (good deal) | 3 (fair) | 4 (overpriced)` — maps directly to `deal_tier SMALLINT` DB column.
