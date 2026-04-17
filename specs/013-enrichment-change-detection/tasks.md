# Tasks: Enrichment & Change Detection Services

**Input**: Design documents from `specs/013-enrichment-change-detection/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new package directories and register dependencies. No logic yet.

- [X] T001 Create package skeleton `services/pipeline/src/pipeline/enricher/` with `__init__.py`, `__main__.py` (stub), `config.py` (stub), `service.py` (stub), `base.py` (stub), `catastro.py` (stub), `poi.py` (stub), `poi_loader.py` (stub)
- [X] T002 Create package skeleton `services/pipeline/src/pipeline/change_detector/` with `__init__.py`, `__main__.py` (stub), `config.py` (stub), `consumer.py` (stub), `detector.py` (stub)
- [X] T003 Add new dependencies to `services/pipeline/pyproject.toml`: `lxml>=5.0`, `shapely>=2.0`, `pyosmium>=3.7`, `cachetools>=5.0`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB schema migration, shared model additions, and service configuration — must be complete before any user story implementation can begin.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Write Alembic migration `services/pipeline/alembic/versions/015_enrichment.py`: `ALTER TABLE listings ADD COLUMN` for all 11 enrichment columns (`cadastral_ref`, `official_built_area_m2`, `area_discrepancy_flag`, `building_geometry_wkt`, `enrichment_status`, `enrichment_attempted_at`, `dist_metro_m`, `dist_train_m`, `dist_airport_m`, `dist_park_m`, `dist_beach_m`) and `CREATE TABLE pois` with GiST spatial index and `(country, category)` B-tree index (see `data-model.md` for full DDL)
- [X] T005 [P] Add enrichment fields (all `Optional`, default `None`) to `NormalizedListing` in `libs/common/estategap_common/models/listing.py`: `cadastral_ref`, `official_built_area_m2`, `area_discrepancy_flag`, `building_geometry_wkt`, `enrichment_status`, `enrichment_attempted_at`, `dist_metro_m`, `dist_train_m`, `dist_airport_m`, `dist_park_m`, `dist_beach_m`
- [X] T006 [P] Add `PriceChangeEvent` Pydantic model to `libs/common/estategap_common/models/listing.py` (fields: `listing_id`, `country`, `portal`, `old_price`, `new_price`, `currency`, `old_price_eur`, `new_price_eur`, `drop_percentage`, `recorded_at`) and export from `libs/common/estategap_common/models/__init__.py`
- [X] T007 [P] Add `ScrapeCycleEvent` Pydantic model to `libs/common/estategap_common/models/listing.py` (fields: `cycle_id`, `portal`, `country`, `completed_at`, `listing_ids: list[str] = []`) and export from `libs/common/estategap_common/models/__init__.py`
- [X] T008 Implement `EnricherSettings` in `services/pipeline/src/pipeline/enricher/config.py` using `pydantic-settings` `BaseSettings`: fields `database_url`, `nats_url`, `catastro_rate_limit` (default `1.0`), `overpass_url`, `overpass_cache_ttl` (default `300`), `metrics_port` (default `9103`), `log_level` (default `"INFO"`); `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`
- [X] T009 [P] Implement `ChangeDetectorSettings` in `services/pipeline/src/pipeline/change_detector/config.py` using `pydantic-settings` `BaseSettings`: fields `database_url`, `nats_url`, `cycle_window_hours` (default `6`), `fallback_interval_h` (default `12`), `metrics_port` (default `9104`), `log_level` (default `"INFO"`); `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`

**Checkpoint**: Migration applied, shared models extended, configs defined — user story implementation can now begin.

---

## Phase 3: User Story 1 — Cadastral Data Enrichment for Spain (Priority: P1) 🎯 MVP

**Goal**: Spanish listings are automatically enriched with official Catastro cadastral data (ref, area, year, geometry) and area discrepancy is flagged when portal area differs >10% from official.

**Independent Test**: Insert a Spanish listing with a geocoded location, publish it to `listings.deduplicated.es`, run the enricher, and assert the listing row has `cadastral_ref`, `official_built_area_m2`, `enrichment_status='completed'`, and `area_discrepancy_flag` correctly set or unset.

- [X] T010 [P] [US1] Implement `BaseEnricher` ABC and `EnrichmentResult` dataclass in `services/pipeline/src/pipeline/enricher/base.py`: abstract `async def enrich(self, listing: NormalizedListing) -> EnrichmentResult`; `EnrichmentResult` has fields `status: Literal["completed","partial","no_match","failed"]`, `updates: dict[str, object]`, `error: str | None = None`; add `_REGISTRY: dict[str, list[type[BaseEnricher]]] = {}` and `@register_enricher(country: str)` class decorator
- [X] T011 [US1] Implement `SpainCatastroEnricher` in `services/pipeline/src/pipeline/enricher/catastro.py`: decorate with `@register_enricher("ES")`; `async def enrich()` builds 30m bounding box from `listing.location_wkt`, calls Catastro WFS `GetFeature` endpoint via `httpx.AsyncClient`, parses GML 3.2 response with `lxml` using the namespace map in `data-model.md`, extracts `cadastral_ref`/`official_built_area_m2`/`year_built`/`building_geometry_wkt` (WKT via `shapely`); computes `area_discrepancy_flag = abs(portal_area - official_area) / official_area > 0.10`; returns `EnrichmentResult(status="completed", updates={...})` or `status="no_match"` if WFS returns zero features; wraps all errors returning `status="failed"`
- [X] T012 [US1] Add `asyncio.Semaphore(1)` rate limiter to `SpainCatastroEnricher` in `services/pipeline/src/pipeline/enricher/catastro.py`: acquire semaphore before each `httpx` call, `await asyncio.sleep(1.0)` before release so throughput never exceeds 1 req/s regardless of concurrency
- [X] T013 [US1] Implement `EnricherService` in `services/pipeline/src/pipeline/enricher/service.py`: NATS JetStream consumer subscribed to `listings.deduplicated.{country}` (durable `enricher`, `AckPolicy.EXPLICIT`, `max_deliver=5`, `ack_wait=60s`, `max_ack_pending=100`); for each message parse `NormalizedListing`, look up `REGISTRY.get(country, [])`, run enrichers with `asyncio.gather`, merge `updates` dicts, call `_apply_updates(pool, listing_id, merged)` to `UPDATE listings SET ... WHERE id=$1 AND country=$2`, publish updated listing JSON to `listings.enriched.{country_lower}`, ack
- [X] T014 [US1] Implement `_apply_updates` DB writer in `services/pipeline/src/pipeline/enricher/service.py`: build parameterised `UPDATE listings SET col=$N, ... WHERE id=$1 AND country=$2` from the `updates` dict; always sets `enrichment_status` and `enrichment_attempted_at`; uses the existing asyncpg pool pattern from `services/pipeline/src/pipeline/db/pool.py`
- [X] T015 [US1] Implement `__main__.py` entry point in `services/pipeline/src/pipeline/enricher/__main__.py`: load `EnricherSettings`, configure `structlog` JSON renderer (same pattern as `services/pipeline/src/pipeline/normalizer/__main__.py`), start Prometheus HTTP server on `settings.metrics_port`, call `await EnricherService(settings).run()`
- [X] T016 [P] [US1] Write unit tests in `services/pipeline/tests/unit/test_catastro_enricher.py`: mock `httpx.AsyncClient.get` to return a fixture GML response; assert `cadastral_ref`, `official_built_area_m2`, `year_built`, `building_geometry_wkt` are correctly extracted; assert `area_discrepancy_flag=True` when portal area differs >10%; assert `area_discrepancy_flag=False` when difference ≤10%; assert `status="no_match"` when WFS returns empty `FeatureCollection`; assert `status="failed"` when `httpx` raises `ConnectError`

**Checkpoint**: US1 complete — enricher processes Spanish listings, applies Catastro data, persists to DB, publishes to `listings.enriched.es`.

---

## Phase 4: User Story 2 — POI Distance Calculation (Priority: P2)

**Goal**: Every listing with a valid geolocation gets distances (in metres) to the nearest metro station, train station, airport, park, and beach. Primary source is the PostGIS `pois` table; fallback is the Overpass API.

**Independent Test**: Seed a listing with known coordinates and pre-load two POIs per category into the `pois` table, run the enricher, and assert `dist_metro_m` matches the expected distance within ±200 m.

- [X] T017 [US2] Implement `POIDistanceCalculator` in `services/pipeline/src/pipeline/enricher/poi.py`: `async def calculate(listing, pool, overpass_url, overpass_cache)` method; for each category (`metro`, `train`, `airport`, `park`, `beach`) run PostGIS query `SELECT ST_Distance(ST_GeographyFromText($1), location::geography)::int FROM pois WHERE country=$2 AND category=$3 ORDER BY location <-> ST_GeographyFromText($1) LIMIT 1` via asyncpg; if no rows returned call `_overpass_fallback(lat, lon, category, overpass_url, overpass_cache)`; return `dict[str, int | None]` mapping `dist_{category}_m` keys
- [X] T018 [US2] Implement `_overpass_fallback` in `services/pipeline/src/pipeline/enricher/poi.py`: build Overpass QL query `[out:json]; node[{tag}](around:5000,{lat},{lon}); out 1;`, call via `httpx.AsyncClient` with 30s timeout, parse nearest node from `elements[0]`, compute Haversine distance; use `cachetools.TTLCache(maxsize=1024, ttl=300)` keyed by `(round(lat,3), round(lon,3), category)`; return `None` on any error without raising
- [X] T019 [US2] Integrate `POIDistanceCalculator` into `EnricherService.handle_message()` in `services/pipeline/src/pipeline/enricher/service.py`: instantiate calculator from settings; call after all registry enrichers; merge POI distance updates into the same `_apply_updates` call (single DB round-trip per listing)
- [X] T020 [US2] Implement `poi_loader.py` CLI in `services/pipeline/src/pipeline/enricher/poi_loader.py`: `python -m pipeline.enricher.poi_loader --pbf <path> --country <code> --database-url <dsn>`; use `pyosmium.SimpleHandler` to stream PBF nodes; filter by tags: `amenity=subway_entrance` OR `railway=subway_station` → `metro`; `railway=station` → `train`; `aeroway=aerodrome` → `airport`; `leisure=park` → `park`; `natural=beach` → `beach`; batch-insert to `pois` table using `asyncpg.executemany` in chunks of 500; print progress every 10,000 rows
- [X] T021 [P] [US2] Write unit tests in `services/pipeline/tests/unit/test_poi_calculator.py`: mock asyncpg fetch to return a row with a known distance; assert correct `dist_metro_m` value; mock asyncpg fetch returning no rows → assert Overpass fallback is called; mock Overpass HTTP response returning one node; assert `dist_park_m` computed correctly from Haversine; assert `dist_beach_m=None` when both PostGIS and Overpass return nothing

**Checkpoint**: US2 complete — all listings with geolocation get POI distances populated; fallback to Overpass when `pois` table has no data for the country.

---

## Phase 5: User Story 3 — Price Drop, Delisting & Re-listing Detection (Priority: P3)

**Goal**: After each scrape cycle, price drops are recorded in `price_history` and published to NATS; listings not seen in the cycle are marked delisted; previously delisted listings that reappear are restored to active.

**Independent Test**: Seed two listings: one at €300,000 (will drop to €290,000) and one that will be missing. Publish a `scraper.cycle.completed.es.idealista` event. Assert a `price_history` row exists for the price drop, the missing listing has `status='delisted'`, and a `PriceChangeEvent` was published to `listings.price-change.es`.

- [X] T022 [US3] Implement `ChangeDetectorConsumer` in `services/pipeline/src/pipeline/change_detector/consumer.py`: NATS JetStream consumer subscribed to `scraper.cycle.completed.{country}.{portal}` (durable `change-detector`, `AckPolicy.EXPLICIT`, `max_deliver=3`, `ack_wait=120s`, `max_ack_pending=10`); parse message as `ScrapeCycleEvent`; delegate to `Detector.run_cycle(event, pool, nats_js)`; ack on success, nak on error
- [X] T023 [US3] Implement `Detector.run_cycle()` in `services/pipeline/src/pipeline/change_detector/detector.py`: accepts `ScrapeCycleEvent`, asyncpg pool, NATS JetStream client; if `event.listing_ids` is empty → resolve cycle members via `SELECT id FROM listings WHERE source=$1 AND country=$2 AND last_seen_at >= $3 AND last_seen_at <= $4` using `completed_at - cycle_window` and `completed_at`; fetch all active listings for the portal/country as `{id: row}` dict; compute three sets: `to_delist` = active - cycle; `to_relist` = cycle ∩ delisted; `to_check_price` = active ∩ cycle
- [X] T024 [US3] Implement delisting logic in `services/pipeline/src/pipeline/change_detector/detector.py`: for each `listing_id` in `to_delist` execute `UPDATE listings SET status='delisted', delisted_at=NOW() WHERE id=$1 AND country=$2`; use `asyncpg.executemany` for batch efficiency
- [X] T025 [US3] Implement re-listing logic in `services/pipeline/src/pipeline/change_detector/detector.py`: for each `listing_id` in `to_relist` execute `UPDATE listings SET status='active', delisted_at=NULL WHERE id=$1 AND country=$2`; use `asyncpg.executemany`
- [X] T026 [US3] Implement price-change detection in `services/pipeline/src/pipeline/change_detector/detector.py`: for each listing in `to_check_price` compare `current.asking_price` (from DB) against `scraped.asking_price` (from `last_seen_at` row or cycle payload); if different: `INSERT INTO price_history(listing_id, country, old_price, new_price, currency, old_price_eur, new_price_eur, change_type, recorded_at) VALUES(...)` and `UPDATE listings SET asking_price=$1, asking_price_eur=$2 WHERE id=$3 AND country=$4`
- [X] T027 [US3] Implement `PriceChangeEvent` NATS publish in `services/pipeline/src/pipeline/change_detector/detector.py`: after each successful price-history insert where `new_price < old_price`, compute `drop_percentage = (old_price - new_price) / old_price * 100`; build `PriceChangeEvent` and publish JSON to `listings.price-change.{country_lower}` via NATS JetStream
- [X] T028 [US3] Implement description-change detection in `services/pipeline/src/pipeline/change_detector/detector.py`: for listings in `to_check_price` compare `description_orig` hash (use `hashlib.md5`); if changed execute `UPDATE listings SET description_orig=$1, updated_at=NOW() WHERE id=$2 AND country=$3`; no NATS event for description changes
- [X] T029 [US3] Implement fallback timer in `services/pipeline/src/pipeline/change_detector/consumer.py`: if no cycle event received within `settings.fallback_interval_h` hours (use `asyncio.wait_for` + periodic `asyncio.sleep`), query `SELECT DISTINCT source, country FROM listings WHERE last_seen_at < NOW() - interval '$N hours' AND status='active'` and trigger `Detector.run_cycle` with a synthetic event; log as `WARN` level
- [X] T030 [US3] Implement `__main__.py` entry point in `services/pipeline/src/pipeline/change_detector/__main__.py`: load `ChangeDetectorSettings`, configure `structlog` JSON renderer, start Prometheus HTTP server on `settings.metrics_port`, call `await ChangeDetectorConsumer(settings).run()`
- [X] T031 [P] [US3] Write unit tests in `services/pipeline/tests/unit/test_change_detector.py`: mock asyncpg fetch returning active listings; assert price-change path inserts `price_history` row when prices differ; assert no `price_history` insert when prices are equal; assert NATS publish is called only for price drops (new < old), not price increases; assert `to_delist` set computed correctly; assert `to_relist` set computed correctly

**Checkpoint**: US3 complete — price drops, delistings, and re-listings all detected and processed within one cycle of the scrape completing.

---

## Phase 6: Integration Tests

**Purpose**: End-to-end validation against real PostgreSQL + NATS containers.

- [X] T032 Write integration test `services/pipeline/tests/integration/test_enricher_integration.py`: use existing testcontainers fixtures from `services/pipeline/tests/integration/conftest.py`; run migration 015; seed one Spanish listing with location; seed three POI rows per category in `pois` table; mock Catastro HTTP response (fixture XML); publish listing to `listings.deduplicated.es` via NATS; run `EnricherService` for one message; assert `cadastral_ref`, `official_built_area_m2`, `area_discrepancy_flag`, `dist_metro_m` are all populated on the listing row; assert message published to `listings.enriched.es`
- [X] T033 Write integration test `services/pipeline/tests/integration/test_change_detector_integration.py`: seed two active listings for `source='idealista'`, `country='ES'`: one at `asking_price=300000`, one that will be missing; publish `ScrapeCycleEvent` to `scraper.cycle.completed.es.idealista` with `listing_ids=[first_only_id, updated_price_id]` and updated price `290000`; run `ChangeDetectorConsumer` for one cycle; assert `price_history` row inserted for price drop; assert `PriceChangeEvent` published to `listings.price-change.es`; assert second listing has `status='delisted'`; assert no extra `price_history` row for unchanged listing
- [X] T034 [P] Add `015_enrichment` migration to testcontainers fixture: update `TRUNCATE` statement in `services/pipeline/tests/integration/conftest.py` to include `pois` table reset

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Observability, Helm deployment, and acceptance test tooling.

- [X] T035 [P] Add Prometheus metrics to `services/pipeline/src/pipeline/enricher/service.py` and `services/pipeline/src/pipeline/enricher/catastro.py`: counters `enricher_listings_total{country, status}`, `enricher_catastro_requests_total{status}`, gauge `enricher_catastro_rate_limit_active`; histogram `enricher_duration_seconds`; follow existing pattern in `services/pipeline/src/pipeline/metrics.py`
- [X] T036 [P] Add Prometheus metrics to `services/pipeline/src/pipeline/change_detector/detector.py`: counters `change_detector_cycles_total{country,portal}`, `change_detector_price_changes_total{country}`, `change_detector_delistings_total{country}`, `change_detector_relistitings_total{country}`
- [X] T037 Add Helm values entries to `helm/estategap/values.yaml` for two new deployments under `estategap-pipeline` namespace: `pipeline-enricher` (image same as pipeline, `command: ["python", "-m", "pipeline.enricher"]`, resources `requests: {cpu: 100m, memory: 128Mi}`, `limits: {cpu: 500m, memory: 512Mi}`, env vars `DATABASE_URL`, `NATS_URL`, `ENRICHER_CATASTRO_RATE_LIMIT`) and `pipeline-change-detector` (same image, `command: ["python", "-m", "pipeline.change_detector"]`, resources `requests: {cpu: 50m, memory: 64Mi}`, `limits: {cpu: 200m, memory: 256Mi}`)
- [X] T038 [P] Add `scraper-cycle` NATS stream to `helm/estategap/values.yaml` JetStream streams config: `subjects: ["scraper.cycle.>"]`, `retention: WorkQueue`, `max_age: 3600` (1h), `replicas: 3`, `storage: file` (so `scraper.cycle.completed.{country}.{portal}` events are durable)
- [X] T039 [P] Write acceptance test script `services/pipeline/src/pipeline/enricher/test_acceptance.py`: CLI tool taking `--lat`, `--lon`, `--portal-area` args; calls live Catastro WFS (no mock); prints returned cadastral ref, official area, discrepancy flag, year built; used to manually validate 10 Madrid samples as per `quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS Phases 3, 4, 5
- **Phase 3 (US1 Cadastral)**: Depends on Phase 2 — no dependency on US2/US3
- **Phase 4 (US2 POI)**: Depends on Phase 2 — no dependency on US1/US3; can run in parallel with Phase 3
- **Phase 5 (US3 Change Detector)**: Depends on Phase 2 — no dependency on US1/US2; can run in parallel with Phases 3/4
- **Phase 6 (Integration Tests)**: Depends on Phases 3, 4, 5 all complete
- **Phase 7 (Polish)**: Depends on Phases 3, 4, 5 all complete; can overlap with Phase 6

### User Story Dependencies

- **US1 (P1, Cadastral)**: Requires Foundational complete. No US2/US3 dependency.
- **US2 (P2, POI)**: Requires Foundational complete. No US1/US3 dependency. Integrates into `EnricherService` (T019) which modifies US1's `service.py`, so coordinate with US1 author or do after T013.
- **US3 (P3, Change Detector)**: Requires Foundational complete (T004 migration, T006/T007 models). Fully independent from US1/US2.

### Within Each User Story

- T010 (BaseEnricher ABC) before T011 (SpainCatastroEnricher)
- T011 before T012 (rate limiter)
- T010, T011, T012 before T013 (EnricherService)
- T013 before T014 (DB writer — part of service)
- T017 (POIDistanceCalculator) before T018 (Overpass fallback — part of calculator) before T019 (integration into service)
- T022 (Consumer) + T023 (Detector setup) before T024/T025/T026/T027/T028 (detection logic)
- T026 before T027 (NATS publish follows DB insert)

### Parallel Opportunities

- T005, T006, T007, T008, T009 all operate on different files — run in parallel (within Phase 2)
- T010 and T016 can be written together (ABC + unit tests)
- T017 and T021 can be written together (calculator + unit tests)
- T022 and T031 can be written together (consumer + unit tests)
- T035 and T036 can run in parallel (different files)
- T037 and T038 can run in parallel (different sections of values.yaml)

---

## Parallel Example: Phase 3 (US1 Cadastral)

```bash
# These tasks can run concurrently:
Task T010: "Implement BaseEnricher ABC + registry in services/pipeline/src/pipeline/enricher/base.py"
Task T016: "Write unit tests in services/pipeline/tests/unit/test_catastro_enricher.py"

# Then sequentially:
Task T011: "Implement SpainCatastroEnricher (depends on T010)"
Task T012: "Add rate limiter to SpainCatastroEnricher (depends on T011)"
Task T013: "Implement EnricherService (depends on T010, T011, T012)"
Task T014: "Implement _apply_updates DB writer (depends on T013)"
Task T015: "Implement enricher __main__.py entry point (depends on T013)"
```

## Parallel Example: Phase 5 (US3 Change Detector)

```bash
# These can run in parallel:
Task T022: "Implement ChangeDetectorConsumer in consumer.py"
Task T023: "Implement Detector.run_cycle() skeleton in detector.py"
Task T031: "Write unit tests for detector.py"

# Then sequentially (in any order, different methods):
Task T024: "Delisting logic in detector.py"
Task T025: "Re-listing logic in detector.py"
Task T026: "Price-change detection in detector.py"
Task T027: "NATS publish for price drops in detector.py"
Task T028: "Description-change detection in detector.py"
Task T029: "Fallback timer in consumer.py"
Task T030: "change_detector __main__.py entry point"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T009)
3. Complete Phase 3: User Story 1 (T010–T016)
4. **STOP and VALIDATE**: Run `uv run pytest tests/unit/test_catastro_enricher.py -v`, then integration test with mocked WFS
5. Deploy enricher to staging, run `test_acceptance.py` against 10 real Madrid listings

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 (US1 Cadastral) → Validate → Deploy enricher (MVP)
3. Phase 4 (US2 POI) → Validate → Deploy enricher with POI support
4. Phase 5 (US3 Change Detector) → Validate → Deploy change detector
5. Phase 6 (Integration Tests) + Phase 7 (Polish) → Production-ready

### Parallel Team Strategy

With two developers after Phase 2 is complete:

- **Dev A**: Phase 3 (US1 Cadastral, T010–T016) → Phase 7 Helm (T037–T038)
- **Dev B**: Phase 4 (US2 POI, T017–T021) + Phase 5 (US3 Change Detector, T022–T031) → Phase 6 Integration Tests (T032–T034)

---

## Notes

- All new Python code must pass `ruff check` and `mypy --strict` before committing
- The Catastro WFS is always mocked in automated tests; use `test_acceptance.py` for live validation
- The `pois` table pre-load (poi_loader.py, T020) is an operational step documented in `quickstart.md`; it is not a runtime dependency for unit/integration tests
- The Alembic migration (T004) adds columns to the parent `listings` table; PostGIS partition inheritance propagates them to all country partitions automatically
- `PriceChangeEvent` (T006) and `ScrapeCycleEvent` (T007) are added to `estategap_common` so the alert-engine and scrape-orchestrator teams can consume/produce them with the same typed model
