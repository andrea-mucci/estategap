# Tasks: US Portal Spiders & Country-Specific ML Models

**Input**: Design documents from `specs/026-us-spiders-country-ml/`  
**Branch**: `026-us-spiders-country-ml`  
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Maps to user story from spec.md (US1–US4)
- All paths are relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependencies to existing service manifests. No new project structure needed — all new code lives inside existing services.

- [X] T001 Add `playwright-stealth`, `geopandas 0.14+` to `services/spider-workers/pyproject.toml` dependencies
- [X] T002 [P] Add `geopandas 0.14+`, `pyshp` to `services/pipeline/pyproject.toml` dependencies (zone importer)
- [X] T003 [P] Confirm `services/ml/pyproject.toml` already includes `lightgbm 4.3+`, `onnxruntime 1.18+`, `mlflow 2.x`, `shap`; add any missing entries

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema migration, shared utility module, and ML feature config infrastructure. All user story phases depend on this phase being complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Write Alembic migration `services/pipeline/alembic/versions/026_add_us_listing_fields.py` — add 8 nullable columns to `listings` (`hoa_fees_monthly_usd`, `lot_size_sqft`, `lot_size_m2`, `tax_assessed_value_usd`, `school_rating`, `zestimate_reference_usd`, `compete_score`, `mls_id`) and 3 columns to `model_versions` (`transfer_learned BOOL DEFAULT FALSE`, `base_country CHAR(2)`, `confidence TEXT DEFAULT 'full'`) with reversible `upgrade`/`downgrade`
- [X] T005 Create `services/spider-workers/estategap_spiders/spiders/us_utils.py` — implement `sqft_to_m2(sqft)` (factor `0.092903`), `extract_school_rating(raw)` (normalise to 0–10 float), `parse_hoa_cents(raw)` (string → int cents), `parse_tax_assessed_cents(raw)` (string → int cents)
- [X] T006 [P] Create `services/ml/estategap_ml/features/config.py` — define `EncodingRule(BaseModel)` and `CountryFeatureConfig(BaseModel)` with `all_features` property and `from_yaml(path)` classmethod; raise `FileNotFoundError` with descriptive message if file missing
- [X] T007 [P] Create `services/ml/estategap_ml/config/features_base.yaml` — base feature list shared by all countries: `area_m2`, `bedrooms`, `bathrooms`, `floor_number`, `building_age_years`, `zone_median_price_eur_m2`, `dist_to_center_km`, `dist_to_transit_km`, `property_type_encoded`, `photo_count`, `is_new_construction`
- [X] T008 [P] Create `services/ml/estategap_ml/config/features_es.yaml` — Spain: base + `energy_cert_encoded`, `has_elevator`, `community_fees_monthly`, `orientation_encoded`; onehot encoding for `energy_cert`, `orientation`
- [X] T009 [P] Create `services/ml/estategap_ml/config/features_it.yaml` — Italy: base + `ape_rating`, `omi_zone_min_price_eur_m2`, `omi_zone_max_price_eur_m2`; ordinal encoding for `ape_rating` (A4→G)
- [X] T010 [P] Create `services/ml/estategap_ml/config/features_fr.yaml` — France: base + `dpe_rating`, `dvf_median_transaction_price_eur_m2`, `pieces_count`; ordinal encoding for `dpe_rating` (A→G)
- [X] T011 [P] Create `services/ml/estategap_ml/config/features_gb.yaml` — UK: base + `council_tax_band_encoded`, `epc_rating`, `leasehold_flag`, `land_registry_last_price_gbp_m2`; ordinal encoding for `council_tax_band` (A→H) and `epc_rating` (A→G)
- [X] T012 [P] Create `services/ml/estategap_ml/config/features_us.yaml` — USA: base + `hoa_fees_monthly_usd`, `lot_size_m2`, `tax_assessed_value_usd`, `school_rating`, `zestimate_reference_usd`; `feature_drops` lists all EU-only features
- [X] T013 [P] Create `services/ml/estategap_ml/config/features_nl.yaml` — Netherlands: base features only (transfer from ES); note `transfer_learning: true` in metadata comment

**Checkpoint**: Migration applied, `us_utils.py` exists, all 7 YAML config files exist, `CountryFeatureConfig` loads cleanly from each.

---

## Phase 3: User Story 1 — Browse US Listings (Priority: P1) 🎯 MVP

**Goal**: Three US portal spiders publish normalised listings (with sqft→m² and USD→EUR) to the existing NATS ingestion stream. NYC metro sweep produces ≥ 1,000 listings per spider with ≥ 70% completeness.

**Independent Test**: Run each spider targeting ZIP codes `10001,10002,10003`. Verify listings appear in the `listings` table with `country='US'`, `built_area_m2` set, `asking_price_eur` set, and US-specific fields populated where available.

### Zillow Spider

- [X] T014 [P] [US1] Create `services/spider-workers/estategap_spiders/spiders/us_zillow_parser.py` — implement `parse_search_results(next_data: dict) -> list[dict]` extracting listing cards from `props.pageProps.searchPageState.cat1.searchResults.listResults`, and `parse_listing_detail(next_data: dict) -> dict` extracting full listing from `props.pageProps.componentProps.gdpClientCache`; include HOA fees, lot size sqft, Zestimate, tax history; use `us_utils` helpers
- [X] T015 [US1] Create `services/spider-workers/estategap_spiders/spiders/us_zillow.py` — `ZillowUSSpider(BaseSpider)` with `COUNTRY="US"`, `PORTAL="zillow"`, `RATE_LIMIT_SECONDS=3.0`, `REQUIRES_PLAYWRIGHT=True`, `USE_RESIDENTIAL_PROXY=True`; implement `scrape_search_page`, `scrape_listing_detail`, `detect_new_listings` using Playwright stealth page; parse `__NEXT_DATA__` via `us_zillow_parser`; depends on T014, T005

### Redfin Spider

- [X] T016 [P] [US1] Create `services/spider-workers/estategap_spiders/spiders/us_redfin_parser.py` — implement `parse_above_fold(payload: dict) -> dict` from `/api/home/details/aboveTheFold` response, and `parse_school_data(schools: list[dict]) -> float | None` computing average school rating (0–10); extract Compete Score from `mainHouseInfo.competeScore`
- [X] T017 [US1] Create `services/spider-workers/estategap_spiders/spiders/us_redfin.py` — `RedfinUSSpider(BaseSpider)` with `COUNTRY="US"`, `PORTAL="redfin"`, `RATE_LIMIT_SECONDS=2.0`; implement search via `/stingray/api/gis` and detail via `/api/home/details/aboveTheFold?propertyId={id}`; fetch school data from `/api/home/details/schoolsData`; use httpx; depends on T016, T005

### Realtor.com Spider

- [X] T018 [P] [US1] Create `services/spider-workers/estategap_spiders/spiders/us_realtor_parser.py` — implement `parse_json_ld(ld_blocks: list[dict]) -> dict` extracting `RealEstateListing` JSON-LD fields (price, floorSize, geo, address, schoolDistrict, mlsNumber), and `parse_window_data(html: str) -> dict` using regex on `window.__data__` for crime index
- [X] T019 [US1] Create `services/spider-workers/estategap_spiders/spiders/us_realtor.py` — `RealtorComUSSpider(BaseSpider)` with `COUNTRY="US"`, `PORTAL="realtor_com"`, `RATE_LIMIT_SECONDS=1.5`; use httpx + `load_json_ld_blocks()` from `_eu_utils`; depends on T018, T005

### Registration & Normalisation

- [X] T020 [US1] Update `services/spider-workers/estategap_spiders/spiders/__init__.py` — add `from . import us_zillow, us_redfin, us_realtor  # noqa: E402,F401` to trigger auto-registration; depends on T015, T017, T019
- [X] T021 [P] [US1] Create `services/pipeline/config/mappings/us_zillow.yaml` — map spider fields to unified listing schema: `price_usd_cents→asking_price`, `area_sqft→built_area_sqft`, `area_m2→built_area_m2`, `hoa_fees_monthly_usd_cents→hoa_fees_monthly_usd`, `lot_size_sqft→lot_size_sqft`, `lot_size_m2→lot_size_m2`, `zestimate_usd_cents→zestimate_reference_usd`; `expected_fields` list includes all US-specific columns
- [X] T022 [P] [US1] Create `services/pipeline/config/mappings/us_redfin.yaml` — same structure as T021 with Redfin-specific field names; include `compete_score` mapping
- [X] T023 [P] [US1] Create `services/pipeline/config/mappings/us_realtor.yaml` — same structure with Realtor.com field names; include `mls_id`, `school_rating` mappings

### Unit Tests

- [X] T024 [P] [US1] Create `services/spider-workers/tests/spiders/test_us_utils.py` — parametrised test: `[(1000, 92.90), (500, 46.45), (2500, 232.26), (0, 0.0)]`; assert `abs(result - expected) <= 0.01` for each
- [X] T025 [P] [US1] Create `services/spider-workers/tests/spiders/test_us_zillow_parser.py` — load fixture JSON from `tests/fixtures/zillow_next_data.json` (create minimal fixture); assert parser extracts price, area_m2, bedrooms, hoa_fees, zestimate; assert `None` returned for absent optional fields
- [X] T026 [P] [US1] Create `services/spider-workers/tests/spiders/test_us_redfin_parser.py` — load fixture from `tests/fixtures/redfin_above_fold.json`; assert Compete Score, school rating average, area_sqft→m² conversion
- [X] T027 [P] [US1] Create `services/spider-workers/tests/spiders/test_us_realtor_parser.py` — load fixture HTML from `tests/fixtures/realtor_listing.html` (minimal with JSON-LD block); assert MLS ID, school district, price extraction

**Checkpoint**: All three spiders register correctly (`REGISTRY[("us", "zillow")]` etc.), parsers pass unit tests, sqft conversion tests pass. Spider runner can be invoked dry-run without errors.

---

## Phase 4: User Story 2 — US Zone Hierarchy Navigation (Priority: P1)

**Goal**: TIGER/Line shapefiles for US state/county/city/ZIP/neighbourhood boundaries are importable into the existing `zones` table with correct 5-level hierarchy and PostGIS geometry.

**Independent Test**: Run importer with `--state-fips 36` (New York). Verify `zones` table contains ≥ 1 state, ≥ 62 counties, ≥ 500 places, and ≥ 300 ZIP codes with `country='US'` and non-null PostGIS geometry. Verify ZIP zones have `parent_id` pointing to a county zone.

- [X] T028 [US2] Create `services/pipeline/estategap_pipeline/zone_import/us_tiger.py` — CLI module (`python -m estategap_pipeline.zone_import.us_tiger`); download TIGER/Line shapefiles from `census.gov` URLs per level; load each with `geopandas.read_file()`; convert geometry to WKT (SRID 4326); bulk-upsert into `zones` table via asyncpg; resolve parent hierarchy using PostGIS `ST_Within(ST_Centroid(child.geom), parent.geom)` queries; support `--level`, `--state-fips`, `--database-url` args; depends on T004
- [X] T029 [US2] Create `services/spider-workers/tests/spiders/test_us_tiger_import.py` — integration test using a GeoJSON fixture for one New York county; assert zone record created with correct `level`, `country`, `code`, non-null `geometry`, and `parent_id` resolved

**Checkpoint**: Zone importer runs against local PostgreSQL with PostGIS; New York state import produces correct zone hierarchy. `ST_Within` lookup assigns US listings to correct ZIP zone.

---

## Phase 5: User Story 3 — Country-Specific Deal Scoring (Priority: P1)

**Goal**: Independent LightGBM models are trained for each country with ≥ 1,000 listings using country-specific YAML feature sets. The scorer automatically loads the correct model by `country` field. MAPE < 12% for Spain, Italy, France, UK, Netherlands, USA.

**Independent Test**: `python -m estategap_ml.trainer --country es` completes, uploads ONNX artefact to MinIO at `ml-models/es/champion/`, logs MAPE and per-city metrics to MLflow. Scorer `score_listing({"country": "US", ...})` returns `scoring_method="ml"` with a US model loaded.

### Feature Engineering

- [X] T030 [US3] Modify `services/ml/estategap_ml/features/engineer.py` — update `FeatureEngineer.__init__(country: str)` to call `CountryFeatureConfig.from_yaml(Path(f"config/features_{country.lower()}.yaml"))` and populate `self.features` and `self.encoding_rules`; fall back to `features_base.yaml` with a warning log if country file not found; depends on T006, T007–T013

### ML Trainer

- [X] T031 [US3] Modify `services/ml/estategap_ml/trainer/train.py` — replace hardcoded feature list with `FeatureEngineer(country=country).features`; add per-country training loop: `for country in get_active_countries(min_listings=1000)`; add per-city MAPE computation after evaluation (`group test set by city_slug, compute MAPE per group`); log per-city metrics to MLflow as `mape_city_{city_slug}`; depends on T030
- [X] T032 [US3] Modify `services/ml/estategap_ml/trainer/__main__.py` — add `--country COUNTRY` flag (train single country), `--countries-all` flag (train all active countries with ≥ 1,000 listings); validate `--country` against known ISO codes; depends on T031
- [X] T033 [US3] Modify `services/ml/estategap_ml/trainer/registry.py` — add `transfer_learned: bool`, `base_country: str | None`, `confidence: str` parameters to `register_model()` and `promote_model()` functions; persist to `model_versions` table; depends on T004

### Scorer Dispatch

- [X] T034 [US3] Modify `services/ml/estategap_ml/scorer/servicer.py` — replace single-model load with `get_champion_for_country(country: str) -> ModelVersion | None` DB query; add model cache keyed by `(country, version_tag)`; load ONNX + joblib from MinIO path `ml-models/{country}/champion/`; add `scoring_method` and `model_confidence` fields to `ScoredListing` response; depends on T033

### Trainer Tests

- [X] T035 [P] [US3] Create `services/ml/tests/trainer/test_feature_config.py` — test `CountryFeatureConfig.from_yaml` for each of the 6 country files; assert `all_features` contains expected country-specific columns; assert `features_base.yaml` fallback triggers warning log
- [X] T036 [P] [US3] Create `services/ml/tests/scorer/test_scorer_dispatch.py` — mock `get_champion_for_country` returning country-specific `ModelVersion` fixtures for ES, IT, FR, GB, US, NL; assert correct MinIO path constructed for each; assert `scoring_method="ml"` in response

**Checkpoint**: Trainer runs `--countries-all`, trains one model per country, uploads to MinIO. Scorer routes ES listing to ES model, US listing to US model, with zero misrouting on a 6-country fixture set.

---

## Phase 6: User Story 4 — Low-Data Country Fallback (Priority: P2)

**Goal**: Countries with 1,000–4,999 listings use transfer learning (init from Spain model, lr=0.01, 100 iterations). If resulting MAPE > 20%, the model is flagged `confidence="insufficient_data"` and the scorer returns zone-median estimate with `scoring_method="heuristic"`.

**Independent Test**: Synthesise a country with 2,000 listings where transfer-learned MAPE = 0.25. Assert `model_versions.confidence = "insufficient_data"`. Call scorer for a listing from that country and assert `scoring_method = "heuristic"`, `estimated_price_eur` ≈ `zone.median_price_eur_m2 × listing.area_m2`.

- [X] T037 [US4] Modify `services/ml/estategap_ml/trainer/train.py` — add transfer learning branch: when `1000 <= listing_count < 5000`, load Spain champion `.txt` from MinIO `ml-models/es/champion/model.txt`, pass as `init_model` to LightGBM `train()`, set `learning_rate=0.01`, `n_estimators=100`; after training evaluate MAPE on held-out set; if `mape > 0.20` set `confidence="insufficient_data"` else `confidence="transfer"`; pass `transfer_learned=True`, `base_country="ES"` to registry; depends on T031, T033
- [X] T038 [US4] Modify `services/ml/estategap_ml/scorer/servicer.py` — add heuristic fallback: when `champion is None or champion.confidence == "insufficient_data"`, compute `estimated_price_eur = zone.median_price_eur_m2 * listing.area_m2`; return `scoring_method="heuristic"`, `model_confidence="insufficient_data"`; query zone median from existing `zones` enrichment data; depends on T034
- [X] T039 [US4] Create `services/ml/tests/trainer/test_transfer_learning.py` — fixture: 2,000-row synthetic listing DataFrame for country `"XX"`; mock MinIO Spain model load; run transfer training call; assert `lgb.train` called with `init_model` arg and `learning_rate=0.01`, `n_estimators=100`; assert `confidence="transfer"` when mocked MAPE = 0.12; assert `confidence="insufficient_data"` when mocked MAPE = 0.25
- [X] T040 [US4] Create `services/ml/tests/scorer/test_heuristic_fallback.py` — mock DB returning `ModelVersion(confidence="insufficient_data")`; assert scorer returns `scoring_method="heuristic"` and price ≈ `zone_median × area` within 1 EUR tolerance

**Checkpoint**: Netherlands model trains via transfer learning and flags correctly. Scorer returns heuristic estimate for any country with `confidence="insufficient_data"` without raising exceptions.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration validation, rate-limit config, and documentation hooks.

- [X] T041 [P] Add Zillow, Redfin, Realtor.com entries to `services/spider-workers/estategap_spiders/config.py` `RATE_LIMITS` dict: `{"zillow": 3.0, "redfin": 2.0, "realtor_com": 1.5}`; add `USE_RESIDENTIAL_PROXY` per-portal flag
- [X] T042 [P] Add env vars `ZILLOW_RATE_LIMIT_SECONDS`, `REDFIN_RATE_LIMIT_SECONDS`, `ML_TRANSFER_MIN_LISTINGS`, `ML_TRANSFER_MAPE_MAX`, `ML_TRANSFER_BASE_COUNTRY` to `services/spider-workers/estategap_spiders/settings.py` and `services/ml/estategap_ml/settings.py` with documented defaults per `quickstart.md`
- [X] T043 Create `services/spider-workers/tests/spiders/fixtures/zillow_next_data.json` — minimal `__NEXT_DATA__` fixture with 3 listing cards and 1 detail record for parser unit tests (T025)
- [X] T044 [P] Create `services/spider-workers/tests/spiders/fixtures/redfin_above_fold.json` — minimal above-fold API response fixture for T026
- [X] T045 [P] Create `services/spider-workers/tests/spiders/fixtures/realtor_listing.html` — minimal HTML page with JSON-LD `RealEstateListing` block for T027
- [X] T046 Create end-to-end integration test `services/spider-workers/tests/integration/test_us_spider_to_nats.py` — use testcontainers (NATS + PostgreSQL + PostGIS); run Redfin spider with mocked httpx responses; assert listing arrives on NATS `listings.raw.ingested` subject with `country="US"`, `built_area_m2` computed correctly
- [ ] T047 Run `uv run ruff check . && uv run mypy --strict` in `services/spider-workers/` and fix any errors in new files
- [ ] T048 [P] Run `uv run ruff check . && uv run mypy --strict` in `services/ml/` and fix any errors in new/modified files
- [ ] T049 [P] Run `uv run ruff check . && uv run mypy --strict` in `services/pipeline/` and fix any errors in new migration and zone importer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T001–T003 all parallel
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user story phases**
  - T004 (migration) must complete before US1/US2 spider storage works
  - T005 (us_utils) must complete before T014–T019 (spider implementations)
  - T006 + T007–T013 (feature configs) must complete before T030 (FeatureEngineer)
- **Phase 3 (US1)**: Depends on Phase 2 — parsers (T014, T016, T018) parallelise with YAML files (T021–T023)
- **Phase 4 (US2)**: Depends on Phase 2 (T004 migration) — independent of Phase 3
- **Phase 5 (US3)**: Depends on Phase 2 (T006, T007–T013) — independent of Phase 3 and 4
- **Phase 6 (US4)**: Depends on Phase 5 (T031, T033, T034)
- **Phase 7 (Polish)**: Depends on Phases 3–6 complete

### User Story Dependencies

| Story | Depends On | Can Parallelise With |
|-------|-----------|---------------------|
| US1 (Browse US Listings) | Phase 2 complete | US2 (entirely), US3 start |
| US2 (Zone Hierarchy) | T004 only | US1, US3 |
| US3 (Country ML Scoring) | T006, T007–T013 | US1, US2 |
| US4 (Low-Data Fallback) | US3 complete (T031, T033, T034) | — |

### Within Each User Story

- Parser module before spider implementation (T014 before T015, T016 before T017, T018 before T019)
- Spider implementations before `__init__.py` registration (T015, T017, T019 before T020)
- `FeatureEngineer` (T030) before trainer modifications (T031)
- Trainer registry (T033) before scorer dispatch (T034)
- Scorer dispatch (T034) before heuristic fallback (T038)

---

## Parallel Opportunities

### Phase 2 Parallel Batch (after Phase 1)

```
T004 DB migration
T005 us_utils.py
T006 CountryFeatureConfig model     ← all run simultaneously
T007 features_base.yaml
T008 features_es.yaml
T009 features_it.yaml
T010 features_fr.yaml
T011 features_gb.yaml
T012 features_us.yaml
T013 features_nl.yaml
```

### Phase 3 Parallel Batches (after Phase 2)

```
Batch A — parsers (no dependencies on each other):
  T014 us_zillow_parser.py
  T016 us_redfin_parser.py          ← run simultaneously
  T018 us_realtor_parser.py

Batch B — after Batch A:
  T015 us_zillow.py (needs T014)
  T017 us_redfin.py (needs T016)    ← run simultaneously
  T019 us_realtor.py (needs T018)

Batch C — after Batch B:
  T020 __init__.py (needs T015, T017, T019)

Batch D — parallel with Batch A/B/C:
  T021 us_zillow.yaml
  T022 us_redfin.yaml               ← run simultaneously
  T023 us_realtor.yaml

Batch E — unit test fixtures + tests (parallel with Batch A/B):
  T024 test_us_utils.py
  T025 test_us_zillow_parser.py
  T026 test_us_redfin_parser.py     ← run simultaneously
  T027 test_us_realtor_parser.py
```

### Phase 5 Parallel Batch (after T006, T007–T013)

```
T035 test_feature_config.py         ← parallel with T030
T030 FeatureEngineer YAML load
  → T031 train.py multi-country
    → T032 __main__.py CLI flags
    → T033 registry.py new columns
      → T034 scorer dispatch
        → T036 test_scorer_dispatch.py
```

---

## Implementation Strategy

### MVP (User Story 1 + Foundation only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T013)
3. Complete Phase 3: US1 spiders (T014–T027)
4. **STOP and VALIDATE**: Run Redfin spider dry-run against NYC ZIPs; verify ≥ 1,000 listings with correct m² and EUR values in DB
5. Deploy spider-workers with US portals active

### Incremental Delivery

1. Foundation + US1 → NYC metro listings live (MVP)
2. + US2 zone import → ZIP/city/state navigation works for US
3. + US3 country ML → per-country deal scores, MAPE < 12% per market
4. + US4 transfer learning → Netherlands + future thin markets covered

### Parallel Team Strategy

With two developers after Phase 2 completes:
- **Dev A**: US1 (Phases 3) — spider work
- **Dev B**: US2 + US3 setup (Phases 4–5 foundations) — zone import + feature configs / trainer

---

## Notes

- `[P]` tasks have no shared file conflicts and can be assigned to separate agents/developers
- All new Python files must pass `ruff check` and `mypy --strict` before marking complete
- Commit after each checkpoint (Phase boundary or logical group)
- Stop after US1 checkpoint to run a real dry-run against NYC ZIPs before proceeding
- Zillow spider requires `PROXY_US_URL` set; skip in unit tests via `USE_RESIDENTIAL_PROXY=False` env override
- Spain champion model must exist in MinIO before Phase 6 (US4 transfer learning) can be tested end-to-end
