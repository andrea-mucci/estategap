# Tasks: Normalize & Deduplicate Pipeline

**Input**: Design documents from `specs/012-normalize-dedup-pipeline/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the sub-package skeleton and update dependencies.

- [X] T001 Create `services/pipeline/src/pipeline/normalizer/` sub-package with `__init__.py`
- [X] T002 [P] Create `services/pipeline/src/pipeline/deduplicator/` sub-package with `__init__.py`
- [X] T003 [P] Create `services/pipeline/config/mappings/` directory (add `.gitkeep`)
- [X] T004 [P] Add new dependencies to `services/pipeline/pyproject.toml`: `asyncpg>=0.29`, `nats-py>=2.6`, `rapidfuzz>=3.9`, `pyyaml>=6.0`, `pydantic-settings>=2.2`, `structlog>=24.1`, `prometheus-client>=0.20`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Write Alembic migration `services/pipeline/alembic/versions/014_pipeline_quarantine.py`: create `quarantine` table (columns: `id`, `source`, `source_id`, `country`, `portal`, `reason`, `error_detail`, `raw_payload JSONB`, `quarantined_at`) + index `(source, country, quarantined_at DESC)`; add `data_completeness NUMERIC(4,2)` column to `listings`
- [X] T006 [P] Create `services/pipeline/src/pipeline/normalizer/config.py`: `NormalizerSettings(BaseSettings)` with fields: `database_url`, `nats_url`, `batch_size=50`, `batch_timeout=1.0`, `mappings_dir`, `metrics_port=9101`
- [X] T007 [P] Create `services/pipeline/src/pipeline/deduplicator/config.py`: `DeduplicatorSettings(BaseSettings)` with fields: `database_url`, `nats_url`, `proximity_meters=50`, `area_tolerance=0.10`, `address_threshold=85`, `metrics_port=9102`
- [X] T008 [P] Create `services/pipeline/src/pipeline/metrics.py`: define shared Prometheus `Counter` and `Histogram` — `pipeline_messages_processed_total`, `pipeline_messages_quarantined_total`, `pipeline_batch_duration_seconds`, all labelled by `service`, `portal`, `country`; expose `start_metrics_server(port)` helper using `prometheus_client.start_http_server`
- [X] T009 Create `services/pipeline/src/pipeline/db/pool.py`: `create_pool(dsn: str) -> asyncpg.Pool` factory using `asyncpg.create_pool(dsn, min_size=2, max_size=10, command_timeout=30)`

**Checkpoint**: Migration applied, configs defined, metrics module ready, DB pool factory available — user story implementation can begin.

---

## Phase 3: User Story 1 — Raw Listings Converted to Unified Schema (Priority: P1) 🎯 MVP

**Goal**: A raw Idealista or Fotocasa NATS message is consumed, field-mapped to the unified schema, and upserted into the `listings` table. A normalized message is published to `normalized.listings.<country>`.

**Independent Test**: Feed a synthetic Idealista raw listing via `nats pub raw.listings.es <payload>`. Verify a row appears in `listings` with `source='idealista'` and all mapped fields populated. Verify a message is published to `normalized.listings.es`.

- [X] T010 [P] [US1] Create `services/pipeline/config/mappings/es_idealista.yaml` mapping config per `specs/012-normalize-dedup-pipeline/contracts/portal-mapping-schema.md` (all Idealista fields: `precio`, `tipologia`, `superficie`, `habitaciones`, `banos`, `planta`, `ascensor`, `garaje`, `terraza`, `anoConstruccion`, `estado`, `certificadoEnergetico`, `latitud`, `longitud`, `url`, `descripcion`, `numFotos`, `direccion`, `municipio`, `provincia`, `codigoPostal`)
- [X] T011 [P] [US1] Create `services/pipeline/config/mappings/es_fotocasa.yaml` mapping config (all Fotocasa fields: `price`, `propertyTypeId`, `surface`, `rooms`, `bathrooms`, `floor`, `hasLift`, `parkingIncluded`, `constructionYear`, `status`, `energyCertification`, `latitude`, `longitude`, `detailUrl`, `description`, `multimedia.images.count`, `address`, `city`, `province`, `postalCode`)
- [X] T012 [US1] Create `services/pipeline/src/pipeline/normalizer/mapper.py`: define `FieldMapping` and `PortalMapping` dataclasses; implement `PortalMapper` class with `load_all(mappings_dir: Path) -> dict[str, PortalMapping]` (load and validate all YAML files at startup) and `apply(mapping: PortalMapping, raw_json: dict) -> dict` (iterate field mappings, extract source values, call transform if specified, return unified dict)
- [X] T013 [US1] Create `services/pipeline/src/pipeline/normalizer/writer.py`: implement `ListingWriter` with `asyncpg.Pool`; `upsert_batch(rows: list[NormalizedListing]) -> None` using `executemany` and `INSERT INTO listings (...) ON CONFLICT (source, source_id, country) DO UPDATE SET ...` for all updatable columns; include `data_completeness` in the upserted values
- [X] T014 [US1] Create `services/pipeline/src/pipeline/normalizer/consumer.py`: implement async NATS JetStream push consumer on `raw.listings.*` with durable name `normalizer`; buffer messages up to `batch_size` or `batch_timeout` seconds; for each batch: parse `RawListing`, look up `PortalMapping` by `portal`, call `mapper.apply()`, build `NormalizedListing`, call `writer.upsert_batch()`; on success ACK all messages and publish each to `normalized.listings.<country_lower>`; on DB failure NAK all messages; add `__main__.py` entrypoint (`python -m pipeline.normalizer`)
- [X] T015 [US1] Create `services/pipeline/tests/integration/conftest.py`: pytest fixtures for `asyncpg` pool connected to a testcontainers PostgreSQL+PostGIS container (apply all Alembic migrations), and a local NATS test server (use `nats-server` subprocess or `pytest-nats`)
- [X] T016 [US1] Create `services/pipeline/tests/integration/test_normalizer_writer.py`: integration test — insert one `NormalizedListing` via `ListingWriter.upsert_batch()`; query `listings` table and assert all fields match; test upsert idempotency (same `source`/`source_id`/`country` updates rather than duplicates)

**Checkpoint**: User Story 1 fully functional — raw Idealista listing → DB row → `normalized.listings.es` message.

---

## Phase 4: User Story 2 — Prices and Areas Expressed in Standard Units (Priority: P1)

**Goal**: The normalizer applies currency-to-EUR and area-to-m² conversions, and maps France `pièces` to `bedrooms`, so all listings have `asking_price_eur` and `built_area_m2` in standard units regardless of source.

**Independent Test**: Submit raw listings with GBP prices and sqft areas; verify `asking_price_eur` matches the ECB rate from `exchange_rates` and `built_area_m2 = sqft * 0.092903`. Submit a French `pièces=4` listing; verify `bedrooms=3`.

- [X] T017 [P] [US2] Create `services/pipeline/src/pipeline/normalizer/transforms.py`: implement `currency_convert(amount: Decimal, from_currency: str, rates: dict[str, Decimal]) -> Decimal` — multiply by rate from dict; raises `ValueError` if currency not in dict
- [X] T018 [P] [US2] Implement `area_to_m2(value: Decimal, unit: str) -> Decimal` in `services/pipeline/src/pipeline/normalizer/transforms.py` — supports `"m2"`, `"sqft"`, `"ft2"` (factor `0.09290304`); raises `ValueError` for unknown unit
- [X] T019 [P] [US2] Implement `map_property_type(portal_type: str, type_map: dict[str, str]) -> str` in `services/pipeline/src/pipeline/normalizer/transforms.py` — looks up `portal_type` in `type_map`; raises `ValueError` if not found
- [X] T020 [P] [US2] Implement `map_condition(portal_condition: str, condition_map: dict[str, str]) -> str | None` in `services/pipeline/src/pipeline/normalizer/transforms.py` — returns mapped canonical condition or `None` if absent from map (non-fatal)
- [X] T021 [P] [US2] Implement `pieces_to_bedrooms(pieces: int) -> int` in `services/pipeline/src/pipeline/normalizer/transforms.py` — returns `max(0, pieces - 1)`
- [X] T022 [US2] Add `load_exchange_rates(pool: asyncpg.Pool) -> dict[str, Decimal]` to `services/pipeline/src/pipeline/normalizer/writer.py`: query `SELECT DISTINCT ON (currency) currency, rate_to_eur FROM exchange_rates ORDER BY currency, date DESC` to get the most recent rate per currency; cache result in the `ListingWriter` instance, refresh every 5 minutes
- [X] T023 [US2] Wire transforms into `services/pipeline/src/pipeline/normalizer/mapper.py` `apply()` method: build a transform function registry `{"currency_convert": transforms.currency_convert, "area_to_m2": transforms.area_to_m2, ...}`; after field extraction, call `compute_asking_price_eur()` using loaded rates, `area_to_m2()` on `built_area` + `area_unit`, `pieces_to_bedrooms()` if `country_uses_pieces=true`; assemble `location_wkt` from `_lat`/`_lon` accumulator keys as `POINT(<lon> <lat>)`
- [X] T024 [US2] Create `services/pipeline/tests/unit/test_transforms.py`: unit tests for all five transform functions — correct conversion values, edge cases (zero area, unknown unit, missing currency, pieces=1 → bedrooms=0), pure functions with no I/O

**Checkpoint**: Currency and area normalization correct for all supported portal/country combinations.

---

## Phase 5: User Story 3 — Invalid Listings Rejected Before Reaching the Database (Priority: P1)

**Goal**: Listings failing any validation rule are written to the `quarantine` table with a reason code and never appear in `listings`. NATS messages are ACKed on quarantine so they are not redelivered.

**Independent Test**: Send 10 synthetic raw listings (5 valid, 2 with price=0, 2 with no GPS, 1 with no mapping config). Verify 5 `listings` rows, 5 `quarantine` rows with correct `reason` values, and no consumer exceptions.

- [X] T025 [US3] Add `write_quarantine(record: QuarantineRecord) -> None` to `services/pipeline/src/pipeline/normalizer/writer.py`: `INSERT INTO quarantine (source, source_id, country, portal, reason, error_detail, raw_payload) VALUES (...)` using a single-row non-batched insert (quarantine events are low-volume and must be persisted immediately)
- [X] T026 [US3] Add validation guards to `services/pipeline/src/pipeline/normalizer/consumer.py` before calling `upsert_batch()`: (1) if `portal` not in loaded `PortalMapper` → quarantine with `reason="no_mapping_config"` and ACK; (2) if raw message body is not valid JSON → quarantine with `reason="invalid_json"` and ACK; (3) after `mapper.apply()`, if `asking_price` resolves to `0` or `None` → quarantine with `reason="invalid_price"` and ACK; (4) if both `location_wkt` is `None` and `address` is empty → quarantine with `reason="missing_location"` and ACK
- [X] T027 [US3] Add Pydantic validation error handler to `services/pipeline/src/pipeline/normalizer/consumer.py`: wrap `NormalizedListing(**mapped)` in try/except `pydantic.ValidationError`; on error → quarantine with `reason="validation_error"`, `error_detail=str(exc)`, and ACK
- [X] T028 [US3] Create `services/pipeline/tests/integration/test_normalizer_quarantine.py`: integration tests — (a) price=0 listing → `quarantine.reason='invalid_price'`, no `listings` row; (b) missing GPS listing → `quarantine.reason='missing_location'`; (c) unknown portal → `quarantine.reason='no_mapping_config'`; (d) malformed JSON → `quarantine.reason='invalid_json'`; (e) pydantic error (negative area) → `quarantine.reason='validation_error'`

**Checkpoint**: All invalid listing types are reliably quarantined; `listings` table contains only valid, fully-mapped rows.

---

## Phase 6: User Story 4 — Identical Property From Two Portals Appears Once (Priority: P1)

**Goal**: The deduplicator runs three-stage matching (PostGIS proximity → feature similarity → address Levenshtein) and stamps matched listings with a shared `canonical_id` equal to the earliest-inserted record's own `id`. A listing with no match gets `canonical_id = id`.

**Independent Test**: Seed `listings` with a known Idealista Madrid flat. Publish the same property from Fotocasa. After deduplication, verify both rows share the same `canonical_id` equal to the Idealista row's `id`.

- [X] T029 [P] [US4] Create `services/pipeline/src/pipeline/deduplicator/address.py`: implement `normalize_address(raw: str) -> str` — `unicodedata.normalize('NFD', raw)` → strip combining diacritics → `.lower()` → remove stopwords (`calle`, `c/`, `c.`, `avenida`, `av.`, `rue`, `via`, `street`, `st.`, `strasse`, `str.`, `plaza`, `pza.`) → `re.sub(r'\s+', ' ', s).strip()`
- [X] T030 [P] [US4] Create `services/pipeline/src/pipeline/deduplicator/matcher.py`: implement `find_proximity_candidates(pool: asyncpg.Pool, lon: float, lat: float, country: str, exclude_id: UUID) -> list[CandidateRow]` using `SELECT id, address, built_area_m2, bedrooms, property_type, canonical_id, created_at FROM listings WHERE ST_DWithin(location::geography, ST_SetSRID(ST_Point($1, $2), 4326)::geography, $3) AND country = $4 AND id != $5` with `$3 = proximity_meters`; define `CandidateRow` as a `TypedDict` or `dataclass`
- [X] T031 [US4] Implement `filter_by_features(candidate: CandidateRow, listing: NormalizedListing, area_tolerance: float) -> bool` in `services/pipeline/src/pipeline/deduplicator/matcher.py`: returns `True` if `abs(candidate.built_area_m2 - listing.built_area_m2) / listing.built_area_m2 < area_tolerance` AND `candidate.bedrooms == listing.bedrooms` AND `candidate.property_type == listing.property_type`
- [X] T032 [US4] Implement `is_address_match(addr_a: str, addr_b: str, threshold: int) -> bool` in `services/pipeline/src/pipeline/deduplicator/matcher.py`: `rapidfuzz.fuzz.ratio(normalize_address(addr_a), normalize_address(addr_b)) > threshold`
- [X] T033 [US4] Implement `resolve_canonical_id(pool: asyncpg.Pool, listing_id: UUID, candidates: list[CandidateRow]) -> UUID` in `services/pipeline/src/pipeline/deduplicator/matcher.py`: if no candidates match → return `listing_id`; if match found → find the `canonical_id` of the earliest-created matched record (`min(c.created_at)`); `UPDATE listings SET canonical_id = $1 WHERE id = $2 AND country = $3` for both the new listing and all existing records in the canonical group (`WHERE canonical_id = <old_canonical_id>`)
- [X] T034 [US4] Create `services/pipeline/src/pipeline/deduplicator/consumer.py`: implement async NATS JetStream push consumer on `normalized.listings.*` with durable name `deduplicator`; for each message: parse `NormalizedListing`, extract GPS from `location_wkt`, call `find_proximity_candidates()` → `filter_by_features()` → `is_address_match()` → `resolve_canonical_id()`; publish message with resolved `canonical_id` to `deduplicated.listings.<country_lower>`; ACK message after successful publish; NAK on any DB/NATS error; add `__main__.py` entrypoint (`python -m pipeline.deduplicator`)
- [X] T035 [US4] Create `services/pipeline/tests/unit/test_address.py`: unit tests for `normalize_address()` — Spanish addresses (accents, `calle`/`c./` prefix), French addresses (`rue`), English addresses (`street`/`st.`), empty string, already-clean string
- [X] T036 [US4] Create `services/pipeline/tests/integration/test_deduplicator_matcher.py`: integration tests — (a) two listings at same GPS, same area/rooms/type, similar address → same `canonical_id`; (b) same GPS but different rooms → distinct `canonical_id`; (c) three listings of same property → all share earliest `canonical_id`; (d) listing with no GPS (`location_wkt=None`) → `canonical_id = own id` (no PostGIS query attempted)

**Checkpoint**: Deduplicator correctly merges cross-portal duplicates; false-positive rate validated on test set.

---

## Phase 7: User Story 5 — Data Completeness Visible per Listing (Priority: P2)

**Goal**: Every listing in the database carries a `data_completeness` score (0.0–1.0) representing the fraction of the 26 defined schema fields that are non-null, enabling quality-based filtering by downstream consumers.

**Independent Test**: Insert a listing with only mandatory fields; verify `data_completeness < 0.5`. Insert a fully populated listing; verify `data_completeness = 1.0`.

- [X] T037 [P] [US5] Define `COMPLETENESS_FIELDS: list[str]` constant in `services/pipeline/src/pipeline/normalizer/writer.py` — list of 26 field names as specified in `specs/012-normalize-dedup-pipeline/data-model.md`
- [X] T038 [US5] Implement `compute_completeness(listing: NormalizedListing) -> float` in `services/pipeline/src/pipeline/normalizer/writer.py`: counts non-None values across `COMPLETENESS_FIELDS` using `getattr(listing, f, None)`; returns `count / len(COMPLETENESS_FIELDS)` rounded to 4 decimal places
- [X] T039 [US5] Wire `compute_completeness()` into `ListingWriter.upsert_batch()` in `services/pipeline/src/pipeline/normalizer/writer.py`: compute score per listing before building the `executemany` row tuple; include `data_completeness` in both INSERT and ON CONFLICT DO UPDATE clause
- [X] T040 [US5] Create `services/pipeline/tests/unit/test_completeness.py`: unit tests — all fields populated → `1.0`; only mandatory fields → score < `0.5`; add one optional field → score increases by `1/26`

**Checkpoint**: All listings written with a correct `data_completeness` score queryable via `WHERE data_completeness >= 0.7`.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Wire metrics and structured logging into all consumer loops; finalize deployment artifacts.

- [X] T041 [P] Wire Prometheus metrics into `services/pipeline/src/pipeline/normalizer/consumer.py`: increment `pipeline_messages_processed_total` per ACKed message; increment `pipeline_messages_quarantined_total` per quarantine write; observe `pipeline_batch_duration_seconds` per batch flush; call `start_metrics_server(settings.metrics_port)` at startup
- [X] T042 [P] Wire Prometheus metrics into `services/pipeline/src/pipeline/deduplicator/consumer.py`: same counters and histogram as normalizer; add `pipeline_dedup_matches_total` counter (label: `matched=true|false`)
- [X] T043 [P] Add `structlog.configure()` call in both `__main__.py` entrypoints (`services/pipeline/src/pipeline/normalizer/__main__.py` and `services/pipeline/src/pipeline/deduplicator/__main__.py`): JSON renderer, processors for `portal`, `country`, `source_id`, `trace_id` context vars; bind these fields via `structlog.contextvars.bind_contextvars()` at the start of each message handler
- [X] T044 Update `services/pipeline/Dockerfile`: add `CMD` comment block showing how to override the default command to run `python -m pipeline.normalizer` or `python -m pipeline.deduplicator` (the Kubernetes Deployment manifest sets the command per pod, not in the Dockerfile directly)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational — mapper + writer + consumer core
- **US2 (Phase 4)**: Depends on US1 (transforms wire into mapper.apply()); `transforms.py` tasks [P] can start after Foundational
- **US3 (Phase 5)**: Depends on US1 (adds quarantine path to existing consumer)
- **US4 (Phase 6)**: Depends on Foundational only — deduplicator is a separate consumer; `address.py` and `matcher.py Stage 1` tasks [P] can start after Foundational
- **US5 (Phase 7)**: Depends on US1 (wires into existing writer); `COMPLETENESS_FIELDS` [P] can start after Foundational
- **Polish (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Foundational complete — no other story dependency
- **US2 (P1)**: Foundational complete + US1 mapper structure exists (wires into `apply()`)
- **US3 (P1)**: Foundational complete + US1 consumer loop exists (adds error branches)
- **US4 (P1)**: Foundational complete only — fully independent deduplicator service
- **US5 (P2)**: Foundational complete + US1 writer exists (adds completeness computation)

### Within Each User Story

- YAML config files [P] can be written alongside mapper code
- Transform functions [P] within US2 are all independent of each other
- `address.py` [P] and `matcher.py Stage 1` [P] within US4 are independent

### Parallel Opportunities

```bash
# Phase 1 — all in parallel after kickoff:
T001  T002  T003  T004

# Phase 2 — T005 first, then all others in parallel:
T005 → T006  T007  T008  T009

# Phase 3 — T010 and T011 in parallel, then sequential:
T010  T011  →  T012  →  T013  →  T014  →  T015  T016

# Phase 4 — all transform tasks in parallel, then wire + test:
T017  T018  T019  T020  T021  →  T022  →  T023  →  T024

# Phase 6 — address and Stage-1 matcher in parallel:
T029  T030  →  T031  →  T032  →  T033  →  T034  →  T035  T036

# Phase 8 — all polish tasks in parallel:
T041  T042  T043  T044
```

---

## Implementation Strategy

### MVP First (User Stories 1–3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (run `alembic upgrade head` to verify migration)
3. Complete Phase 3: US1 — verify Idealista raw listing → DB row end-to-end
4. Complete Phase 4: US2 — verify EUR conversion and m² conversion
5. Complete Phase 5: US3 — verify quarantine for all invalid listing types
6. **STOP and VALIDATE**: Run `pytest tests/integration/` — all normalizer tests pass
7. **SHIP MVP**: Normalizer service is production-ready

### Incremental Delivery

1. **MVP**: Phases 1–3 → normalizer core functional
2. **+Standard Units**: Phase 4 → all currency/area conversions correct
3. **+Data Quality**: Phase 5 → quarantine fully operational
4. **+Deduplication**: Phase 6 → cross-portal dedup working (independent service)
5. **+Completeness**: Phase 7 → ML-ready quality scoring
6. **+Observability**: Phase 8 → metrics and structured logs in production

### Parallel Team Strategy

With two developers after Foundational is complete:

- **Developer A**: Phases 3 → 4 → 5 (normalizer pipeline)
- **Developer B**: Phase 6 (deduplicator — fully independent)
- Developer A and B converge on Phase 7 and 8

---

## Notes

- [P] tasks operate on different files with no shared mutable state
- NATS ACK policy: ACK after DB write for valid listings; ACK on quarantine for invalid ones; NAK on transient infra failures
- `transforms.py` functions are pure (no I/O) — test with plain `pytest`, no fixtures needed
- `normalize_address()` is pure — unit tests need no infra
- Integration tests use testcontainers: Docker must be available in the test environment
- The deduplicator skips PostGIS query for listings with `location_wkt=None` (sets `canonical_id=own id` immediately)
- Commit after each completed phase checkpoint to keep the branch history clean
