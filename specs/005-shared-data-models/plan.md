# Implementation Plan: Shared Data Models

**Branch**: `005-shared-data-models` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-shared-data-models/spec.md`

## Summary

Bring existing stub models in `libs/common/estategap_common/models/` up to full specification (validators, corrected enums, missing models) and introduce a new `libs/pkg/models/` Go package with pgx-compatible structs and `shopspring/decimal` for prices. The two libraries share a JSON contract guaranteed by cross-language round-trip fixtures in `tests/cross_language/`.

## Technical Context

**Language/Version**: Python 3.12 (Pydantic v2), Go 1.23
**Primary Dependencies**:
- Python — `pydantic>=2`, `uv` (package manager)
- Go — `github.com/jackc/pgx/v5` (pgtype), `github.com/shopspring/decimal`, `github.com/google/uuid`

**Storage**: PostgreSQL 16 + PostGIS 3.4 (models mirror existing schema; no migrations in this feature)
**Testing**: Python — `pytest` + `mypy --strict`; Go — `go test` (table-driven)
**Target Platform**: Linux (Kubernetes), consumed by all Go and Python services
**Project Type**: Shared library (two packages — one per language)
**Performance Goals**: Model construction and validation < 1 ms per instance (not a hot path)
**Constraints**: JSON field names must be identical between Python `model_dump(mode="json")` and Go `json.Marshal`; no ORM in Go
**Scale/Scope**: ~15 Python models, ~6 Go structs; consumed by ~9 services

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Polyglot: shared code in `libs/` | ✅ Pass | Python → `libs/common`, Go → `libs/pkg` |
| II — Event-Driven: no direct HTTP between services | ✅ Pass | This feature adds no inter-service calls |
| III — Country-First: country partitioned, prices in EUR | ✅ Pass | All listing models carry `country`/`country_code`; prices stored in original and EUR |
| IV — ML: SHAP values + deal score included | ✅ Pass | `ScoringResult` and `ShapValue` models included |
| V — Code Quality: Pydantic v2, ruff+mypy strict, pgx, table-driven tests | ✅ Pass | `ConfigDict(strict=True)`, mypy strict, `pgtype` used throughout |
| VI — Security: no secrets, GDPR soft-delete field | ✅ Pass | `User.deleted_at` soft-delete field present; no secrets stored in models |
| VII — K8s native | ✅ Pass | Library only; no deployment manifests needed |

**Post-Design Re-check**: No violations introduced. Models are passive data containers.

## Project Structure

### Documentation (this feature)

```text
specs/005-shared-data-models/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── json-contract.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
libs/
├── common/                                    # Python shared library (exists)
│   ├── pyproject.toml                         # UPDATE: add pydantic-settings, strict mypy config
│   └── estategap_common/
│       └── models/
│           ├── __init__.py                    # UPDATE: export new/renamed symbols
│           ├── _base.py                       # UPDATE: strict=True, AwareDatetime, ISO validators
│           ├── listing.py                     # UPDATE: PropertyCategory, NormalizedListing, validators
│           ├── alert.py                       # UPDATE: typed AlertFilters
│           ├── conversation.py                # UPDATE: pending_dimensions field
│           ├── ml.py                          # no change
│           ├── reference.py                   # UPDATE: country/currency validators
│           ├── scoring.py                     # UPDATE: EstateGapModel base, DealTier, full fields
│           ├── user.py                        # UPDATE: SubscriptionTier values, add Subscription
│           └── zone.py                        # no change
└── pkg/                                       # Go shared library (exists)
    ├── go.mod                                 # UPDATE: add pgx/v5, decimal, uuid deps
    ├── go.sum                                 # auto-generated
    └── models/                                # NEW package
        ├── enums.go                           # PropertyCategory, DealTier, ListingStatus, SubscriptionTier
        ├── listing.go                         # Listing, PriceHistory structs
        ├── alert.go                           # AlertRule struct
        ├── scoring.go                         # ScoringResult, ShapValue structs
        ├── user.go                            # User, Subscription structs
        ├── zone.go                            # Zone struct
        ├── reference.go                       # Country, Portal structs
        └── models_test.go                     # Table-driven JSON round-trip + pgx scan tests

tests/
└── cross_language/
    ├── fixtures/
    │   ├── listing.json                       # Canonical JSON fixture
    │   ├── alert_rule.json
    │   ├── scoring_result.json
    │   └── user.json
    └── test_roundtrip.py                      # Python round-trip assertions
```

**Structure Decision**: Monorepo multi-package layout. Python package extends `libs/common/estategap_common/models/` in-place. Go package is a new `libs/pkg/models/` directory inside the existing `github.com/estategap/libs` module. Cross-language fixtures live at `tests/cross_language/`.

## Complexity Tracking

No constitution violations — table not required.
