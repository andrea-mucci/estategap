# Tasks: Shared Data Models

**Input**: Design documents from `/specs/005-shared-data-models/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Update dependency manifests and create shared test infrastructure before any model work begins.

- [X] T001 Update `libs/common/pyproject.toml` — add `[tool.mypy] strict = true`, add pytest config, add `pytest` and `pytest-asyncio` to dev deps
- [ ] T002 Add `github.com/jackc/pgx/v5`, `github.com/shopspring/decimal`, and `github.com/google/uuid` to `libs/pkg/go.mod` and run `go mod tidy`
- [X] T003 [P] Create `libs/common/tests/__init__.py` and `libs/common/tests/models/__init__.py` (empty, marks test package)
- [X] T004 [P] Create `tests/cross_language/fixtures/` directory and write all four canonical JSON fixture files: `listing.json`, `alert_rule.json`, `scoring_result.json`, `user.json` — exact content from `contracts/json-contract.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL models depend on. Must be complete before any user story implementation.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Update `libs/common/estategap_common/models/_base.py` — set `ConfigDict(strict=True, extra="forbid")`, define `ISO_3166_1_ALPHA2` frozenset (249 codes), define `ISO_4217` frozenset (~170 codes), expose `validate_country_code(v: str) -> str` and `validate_currency_code(v: str) -> str` helper functions, keep `EstateGapModel` as base class with `AwareDatetime` import documented for field typing
- [X] T006 [P] Create `libs/pkg/models/enums.go` — define Go string/int type aliases and constants for `PropertyCategory` (`residential | commercial | industrial | land`), `ListingStatus` (`active | delisted | sold`), `SubscriptionTier` (`free | basic | pro | global | api`), `DealTier` (int constants 1–4)

**Checkpoint**: `_base.py` validator helpers and Go enums are ready — user story work can now begin.

---

## Phase 3: User Story 1 — Pipeline Validates Listing Data (Priority: P1) 🎯 MVP

**Goal**: All three Python listing models exist with working validators; listing.json round-trip passes in both Python and Go.

**Independent Test**: `cd libs/common && uv run pytest tests/models/test_listing.py -v` passes; `cd libs/pkg && go test ./models/... -run TestListing -v` passes; `cd tests/cross_language && uv run pytest test_roundtrip.py::test_listing_roundtrip -v` passes.

### Implementation for User Story 1

- [X] T007 [P] [US1] Update `libs/common/estategap_common/models/listing.py` — rename `ListingType` → `PropertyCategory` (import from `_base`), fix `ListingStatus` values to `active | delisted | sold`, add `NormalizedListing` model with `@field_validator` for `asking_price > 0`, `built_area_m2 > 0`, `country` allowlist, `currency` allowlist; all `datetime` fields typed as `AwareDatetime`; keep `RawListing` (add `country_code` allowlist validator); keep `Listing` (add `DealTier` field, import from scoring)
- [X] T008 [P] [US1] Update `libs/common/estategap_common/models/scoring.py` — change base class from `BaseModel` to `EstateGapModel`, add `DealTier` IntEnum (1–4), expand `ScoringResult` fields to match data-model.md (`listing_id: UUID`, `country: str`, `estimated_price: Decimal`, `deal_score: Decimal`, `deal_tier: DealTier`, `confidence_low: Decimal`, `confidence_high: Decimal`, `shap_features: list[ShapValue]`, `model_version: str`, `scored_at: AwareDatetime`)
- [X] T009 [P] [US1] Update `libs/common/estategap_common/models/reference.py` — add `@field_validator` for `Country.code` (ISO 3166-1) and `Country.currency` (ISO 4217), add `@field_validator` for `Portal.country_code` (ISO 3166-1); all `datetime` fields typed as `AwareDatetime`
- [X] T010 [P] [US1] Create `libs/pkg/models/listing.go` — `Listing` and `PriceHistory` structs with `json` and `db` struct tags exactly matching Python field names from data-model.md; use `pgtype.UUID`, `pgtype.Timestamptz`, `*decimal.Decimal`, pointer types for nullable fields, `json.RawMessage` for `shap_features`
- [X] T011 [P] [US1] Create `libs/pkg/models/scoring.go` — `ShapValue` and `ScoringResult` structs; `ScoringResult` uses `decimal.Decimal` (non-pointer) for required price fields and `pgtype.Timestamptz` for `scored_at`
- [X] T012 [P] [US1] Create `libs/pkg/models/reference.go` — `Country` and `Portal` structs with `json`/`db` tags; `Country.Config` and `Portal.Config` as `json.RawMessage`
- [X] T013 [US1] Write Python unit tests in `libs/common/tests/models/test_listing.py` — table-driven style covering: valid `NormalizedListing` construction; `ValidationError` on `asking_price <= 0`; `ValidationError` on `built_area_m2 <= 0`; `ValidationError` on invalid country code `"XX"`; `ValidationError` on invalid currency `"ZZZ"`; `ValidationError` on naive datetime; `RawListing` accepts any country with valid ISO code; `Listing.deal_tier` accepts `DealTier` enum values
- [X] T014 [US1] Write Python unit tests in `libs/common/tests/models/test_scoring.py` — valid `ScoringResult` with all fields; `ValidationError` on naive `scored_at`; `DealTier` enum serialises as int in JSON
- [X] T015 [US1] Create `tests/cross_language/test_roundtrip.py` — load `fixtures/listing.json`, deserialise into `Listing`, re-serialise with `model_dump_json()`, assert all key-value pairs match fixture (field-level comparison); load `fixtures/scoring_result.json`, same round-trip for `ScoringResult`
- [X] T016 [US1] Write Go tests in `libs/pkg/models/models_test.go` — `TestListingRoundTrip`: load `../../tests/cross_language/fixtures/listing.json`, unmarshal into `Listing`, marshal back, assert key fields (`ID`, `Country`, `AskingPrice`, `DealTier`, `ScoredAt`, `DelistedAt == null`); `TestScoringResultRoundTrip`: same for `scoring_result.json`

**Checkpoint**: User Story 1 fully functional — `NormalizedListing` rejects invalid data, listing JSON round-trips between Python and Go.

---

## Phase 4: User Story 2 — API Serialises Listing Responses (Priority: P2)

**Goal**: Go `Listing` and supporting structs scan correctly from mock pgx rows; all nullable fields marshal to `null`; timestamp fields produce RFC 3339 output.

**Independent Test**: `cd libs/pkg && go test ./models/... -run TestPgxScan -v` passes; `cd tests/cross_language && uv run pytest test_roundtrip.py::test_user_roundtrip -v` passes.

### Implementation for User Story 2

- [X] T017 [P] [US2] Create `libs/pkg/models/zone.go` — `Zone` struct with `json`/`db` tags; `ParentID *pgtype.UUID`, `AreaKm2 *decimal.Decimal`, geometry fields omitted (WKT handled as `*string` via `geometry_wkt` / `bbox_wkt` JSON fields)
- [X] T018 [P] [US2] Create `libs/pkg/models/user.go` — `User` and `Subscription` structs with `json`/`db` tags; all nullable timestamp fields as `*pgtype.Timestamptz`; `SubscriptionTier` as `string` with constants from `enums.go`
- [X] T019 [US2] Add pgx scan tests to `libs/pkg/models/models_test.go` — `TestListingPgxScan`: construct a `pgx.Rows` mock (or use `pgxmock`) scanning into `Listing`, assert non-nullable fields are populated; `TestNullableFieldsMarshalNull`: create a `Listing` with all pointer fields nil, marshal to JSON, assert `"delisted_at":null`, `"canonical_id":null`, etc.
- [X] T020 [US2] Extend `tests/cross_language/test_roundtrip.py` with `test_user_roundtrip` — load `fixtures/user.json`, deserialise into `User`, re-serialise, assert all fields match; verify `deleted_at` round-trips as `null`
- [X] T021 [US2] Write Python unit tests in `libs/common/tests/models/test_zone.py` — valid `Zone` construction; `ZoneLevel` enum values; nullable geometry fields accept `None`; `country_code` allowlist validated

**Checkpoint**: Go API service can scan a pgx row into `Listing` and marshal it to JSON with correct field names and null handling.

---

## Phase 5: User Story 3 — Alert Rule Filtering Uses Shared Model (Priority: P3)

**Goal**: `AlertRule`, `User`, and `ConversationState` Python models are complete; `AlertRule` round-trips correctly in both languages.

**Independent Test**: `cd libs/common && uv run pytest tests/models/test_alert.py tests/models/test_user.py -v` passes; `cd libs/pkg && go test ./models/... -run TestAlertRule -v` passes; `cd tests/cross_language && uv run pytest test_roundtrip.py::test_alert_rule_roundtrip -v` passes.

### Implementation for User Story 3

- [X] T022 [P] [US3] Update `libs/common/estategap_common/models/alert.py` — `AlertRule.channels` typed as `dict[str, bool]`; all `datetime` fields typed as `AwareDatetime`; `AlertLog.status` typed as `Literal["pending", "sent", "failed"]`
- [X] T023 [P] [US3] Update `libs/common/estategap_common/models/conversation.py` — add `pending_dimensions: list[str]` field to `ConversationState`; all `datetime` fields typed as `AwareDatetime`; `ConversationState.status` typed as `Literal["active", "completed", "abandoned"]`
- [X] T024 [P] [US3] Update `libs/common/estategap_common/models/user.py` — correct `SubscriptionTier` values to `free | basic | pro | global | api`; add `Subscription` model (fields from data-model.md); all `datetime` fields typed as `AwareDatetime`
- [X] T025 [P] [US3] Create `libs/pkg/models/alert.go` — `AlertRule` struct; `Filters` and `Channels` as `json.RawMessage` (JSONB pass-through); `LastTriggeredAt *pgtype.Timestamptz`
- [X] T026 [US3] Write Python unit tests in `libs/common/tests/models/test_alert.py` — valid `AlertRule` construction; `channels` defaults to `{"email": True}`; `filters` accepts arbitrary dict; `ValidationError` on naive `created_at`; `AlertLog.status` rejects invalid value
- [X] T027 [US3] Write Python unit tests in `libs/common/tests/models/test_user.py` — valid `User` with all optional fields; `SubscriptionTier` enum serialises as lowercase string; `Subscription` construction; `ValidationError` on naive datetime; `deleted_at` round-trips as `null` in JSON
- [X] T028 [US3] Add alert round-trip tests to `libs/pkg/models/models_test.go` — `TestAlertRuleRoundTrip`: load `fixtures/alert_rule.json`, unmarshal into `AlertRule`, marshal back, assert `Filters` is non-empty `json.RawMessage`, `LastTriggeredAt` is nil
- [X] T029 [US3] Extend `tests/cross_language/test_roundtrip.py` with `test_alert_rule_roundtrip` — load `fixtures/alert_rule.json`, deserialise into `AlertRule`, re-serialise, assert `filters` JSONB survives round-trip without data loss

**Checkpoint**: All user stories complete — data validation, API serialisation, and alert filtering all independently verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Wire up exports, schema generation, and verify all quality gates pass end-to-end.

- [X] T030 [P] Update `libs/common/estategap_common/models/__init__.py` — export all new/renamed symbols: `PropertyCategory`, `DealTier`, `NormalizedListing`, `Subscription`; remove old `ListingType` export; confirm `__all__` is complete
- [X] T031 [P] Write `libs/common/tests/models/test_validators.py` — unit tests for shared validator helpers in `_base.py`: valid and invalid country codes (boundary cases: `"ES"` passes, `"XX"` fails, lowercase `"es"` fails under strict mode); valid and invalid currency codes; confirm `AwareDatetime` fields reject naive datetimes across multiple models
- [X] T032 [P] Create `libs/common/scripts/export_schemas.py` — script that imports all models and writes JSON Schema Draft 2020-12 files to `docs/schemas/<ModelName>.json` using `model.model_json_schema()`; create `docs/schemas/` directory
- [ ] T033 Verify `cd libs/common && uv run mypy estategap_common --strict` exits 0 — fix any type errors found
- [ ] T034 Verify `cd libs/common && uv run ruff check estategap_common` exits 0 — fix any lint errors found
- [ ] T035 Verify `cd libs/pkg && go vet ./models/...` exits 0 — fix any vet issues found
- [ ] T036 Verify `cd libs/pkg && go test ./models/... -v` all tests pass — fix any failures
- [ ] T037 Verify `cd libs/common && uv run pytest tests/ -v` all tests pass — fix any failures
- [ ] T038 Verify `cd tests/cross_language && uv run pytest test_roundtrip.py -v` all round-trip tests pass — fix any field name mismatches

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T003 and T004 are parallel
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Phase 2; T007–T012 are all parallel with each other; T013–T016 depend on T007–T012
- **US2 (Phase 4)**: Depends on Phase 2; T017–T018 parallel; T019–T021 depend on T017–T018
- **US3 (Phase 5)**: Depends on Phase 2; T022–T025 are all parallel; T026–T029 depend on T022–T025
- **Polish (Phase 6)**: Depends on all Phase 3–5 tasks; T030–T032 parallel; T033–T038 sequential (quality gates)

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational — no other story dependencies
- **US2 (P2)**: Depends only on Foundational — can run in parallel with US1
- **US3 (P3)**: Depends only on Foundational — can run in parallel with US1 and US2

### Within Each User Story

- Python model updates before Python test tasks
- Go struct files before Go test tasks
- All model/struct tasks before round-trip integration tasks

---

## Parallel Execution Examples

### Phase 1 Parallel Batch

```
T001 (pyproject.toml) — independent
T002 (go.mod)         — independent
T003 (test __init__)  — independent
T004 (fixtures)       — independent
```

### Phase 2 Parallel Batch

```
T005 (_base.py)   — Python foundation
T006 (enums.go)   — Go foundation
```

### Phase 3 (US1) Parallel Batch 1 — Python and Go models

```
T007 (listing.py)    — Python
T008 (scoring.py)    — Python
T009 (reference.py)  — Python
T010 (listing.go)    — Go
T011 (scoring.go)    — Go
T012 (reference.go)  — Go
```

### Phase 3 (US1) Parallel Batch 2 — Tests

```
T013 (test_listing.py)     — Python unit tests
T014 (test_scoring.py)     — Python unit tests
T015 (test_roundtrip.py)   — Cross-language
T016 (models_test.go)      — Go tests
```

### Phase 4 (US2) Parallel Batch

```
T017 (zone.go)   — Go struct
T018 (user.go)   — Go struct
```

### Phase 5 (US3) Parallel Batch

```
T022 (alert.py)          — Python
T023 (conversation.py)   — Python
T024 (user.py)           — Python
T025 (alert.go)          — Go
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T006)
3. Complete Phase 3: US1 (T007–T016)
4. **STOP and VALIDATE**: `pytest tests/models/test_listing.py && go test ./models/... -run TestListing`
5. Pipeline service can now use validated `NormalizedListing`

### Incremental Delivery

1. Phase 1 + 2 → foundation ready
2. Phase 3 (US1) → pipeline validation works → deploy/demo
3. Phase 4 (US2) → Go API serialisation works → deploy/demo
4. Phase 5 (US3) → alert filtering works → deploy/demo
5. Phase 6 (Polish) → all quality gates green → merge to `main`

### Parallel Team Strategy

With multiple developers after Phase 1+2:
- Developer A: Phase 3 (US1) — listing pipeline models
- Developer B: Phase 4 (US2) — Go API structs
- Developer C: Phase 5 (US3) — alert/user models

All three merge independently; Phase 6 polish runs after all stories are in.

---

## Notes

- `[P]` tasks touch different files and have no unresolved dependencies — safe to run in parallel
- `[Story]` label maps each task to its user story for traceability
- Fixtures in `tests/cross_language/fixtures/` are the single source of truth for the JSON contract — do not change field names without updating all consumers
- `AwareDatetime` (from `pydantic`) is the preferred type annotation for datetime fields — it is stricter than `datetime` and rejects naive values automatically
- Go `pgtype.UUID` and `pgtype.Timestamptz` implement `pgx.Scanner` — use them directly in `rows.Scan(...)` calls
- `decimal.Decimal` in Go marshals to a JSON number string — Python's `Decimal` also serialises as a number in `model_dump_json()` — both parse the same way
