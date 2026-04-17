# Feature Specification: Enrichment & Change Detection Services

**Feature Branch**: `013-enrichment-change-detection`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Build the enrichment service (cadastral data + POI distances) and the change detection service."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cadastral Data Enrichment for Spain (Priority: P1)

A property buyer searching in Madrid wants to verify the advertised area against official cadastral records. The enrichment service automatically fetches Catastro data for each active Spanish listing, attaches the official built area, year of construction, and cadastral reference, and flags any listing where the portal-advertised area diverges from the official record by more than 10%.

**Why this priority**: Cadastral verification is the single highest-trust signal for buyers in Spain. It directly reduces fraud-prone listings and increases platform credibility in the largest target market.

**Independent Test**: Can be tested by inserting a Spanish listing with a known address into the pipeline and verifying that the listing record is updated with a cadastral reference, official area, and the area-discrepancy flag is correctly set or unset.

**Acceptance Scenarios**:

1. **Given** a normalized Spanish listing with a geocoded location, **When** the enrichment service processes it, **Then** the listing is updated with a `cadastral_ref`, `official_built_area_m2`, `year_built`, and `building_geometry_wkt` sourced from the Catastro WFS API.
2. **Given** a listing whose portal-reported area is more than 10% different from the Catastro official area, **When** enrichment completes, **Then** the `area_discrepancy_flag` is set to `true`.
3. **Given** the Catastro API returns no result for a listing, **When** enrichment completes, **Then** the listing is marked as enrichment-attempted with a `no_match` status and no fields are overwritten.
4. **Given** the enrichment service is processing many listings, **When** calling the Catastro API, **Then** requests are throttled to at most 1 per second to respect the official rate limit.

---

### User Story 2 - POI Distance Calculation (Priority: P2)

A buyer wants to know how far a listing is from the nearest metro station, city center, beach, or park. The enrichment service computes Haversine distances to the nearest point of interest in each category and stores them on the listing record.

**Why this priority**: POI distances are a top filter used by buyers (commute proximity, lifestyle). They are also key input features for ML deal-scoring and directly improve search relevance.

**Independent Test**: Can be tested by inserting a listing with known coordinates near a known POI, running enrichment, and verifying the computed distance is within ±200 m of the expected value.

**Acceptance Scenarios**:

1. **Given** a listing with a valid geolocation, **When** POI enrichment runs, **Then** distances to the nearest metro station, train station, airport, park, and beach are stored on the listing (null for categories with no data in the country).
2. **Given** a pre-loaded PostGIS POI table for the listing's country, **When** computing distances, **Then** the nearest POI per category is found using a spatial query and the result is within ±200 m of verified reference values.
3. **Given** no pre-loaded POI data for a country, **When** POI enrichment runs, **Then** the Overpass API is queried as a fallback within a bounding box around the listing.
4. **Given** a listing without a geolocation, **When** POI enrichment runs, **Then** POI distances are skipped and all distance fields remain null.

---

### User Story 3 - Price Drop Detection (Priority: P3)

A buyer with a saved alert wants to be notified when a listing they are tracking drops in price. After each scraping cycle, the change detector compares the new price against the stored value, records the change in `price_history`, and publishes an event on the `price.changes` NATS stream so the alert engine can deliver notifications.

**Why this priority**: Price-drop alerts are the core monetizable value proposition. Without this, premium subscribers have no reason to upgrade.

**Independent Test**: Can be tested by seeding a listing at price X, running the change detector with a scrape snapshot containing the same listing at price X − €10,000, and asserting a `price_history` row is inserted and a `price.changes` event is published.

**Acceptance Scenarios**:

1. **Given** an active listing at price €300,000, **When** the scrape cycle produces the same listing at €290,000, **Then** a `price_history` row is inserted recording the old and new prices, the listing's `asking_price` is updated, and a `price.changes` event is published.
2. **Given** an active listing whose price has not changed, **When** the change detector runs, **Then** no `price_history` row is inserted and no event is published.
3. **Given** an active listing that does not appear in the latest scrape snapshot, **When** the change detector runs, **Then** the listing's `status` is set to `delisted` and `delisted_at` is set to the current timestamp.
4. **Given** a previously delisted listing that reappears in the latest scrape snapshot, **When** the change detector runs, **Then** the listing's `status` is reset to `active` and `delisted_at` is cleared.

---

### Edge Cases

- What happens when the Catastro API is unreachable or returns HTTP 5xx? The enrichment is retried with exponential backoff up to 3 times; after that the listing is marked `enrichment_failed` and processing continues.
- What happens when two enrichers both update the same listing field simultaneously? Each enricher upserts only its own columns; there is no overlap by design.
- What happens when a scrape cycle event arrives before the previous cycle has been fully processed by the change detector? The change detector uses `last_seen_at` timestamp from the DB as the ground truth — late-arriving events from a prior cycle are treated as the prior snapshot.
- What happens when a listing's price changes and the listing is also delisted in the same cycle? Both events are recorded: a `price_history` row is inserted and the listing is marked delisted.
- What happens if the POI table is empty for a new country? Distances default to null; the system does not fail. Operators are notified via a Prometheus metric (`poi_data_missing_total` per country).

## Requirements *(mandatory)*

### Functional Requirements

**Enricher Service:**

- **FR-001**: The system MUST expose a `BaseEnricher` interface with an `enrich(listing)` method that returns an `EnrichmentResult` containing updated fields and a status.
- **FR-002**: The system MUST provide a plugin registry mapping country codes to a list of enricher classes, allowing per-country enrichers to be added without modifying core logic.
- **FR-003**: The `SpainCatastroEnricher` MUST call the Catastro INSPIRE WFS endpoint using the listing's geolocation, extract `cadastral_ref`, `official_built_area_m2`, `year_built`, and `building_geometry_wkt`, and persist them on the listing record.
- **FR-004**: The `SpainCatastroEnricher` MUST set `area_discrepancy_flag = true` when the absolute difference between the portal area and the official area exceeds 10%.
- **FR-005**: The `SpainCatastroEnricher` MUST limit concurrent Catastro API requests to 1 per second.
- **FR-006**: The POI distance calculator MUST compute and store the Haversine distance (in metres) from each listing to the nearest feature in each of the following categories: metro station, train station, airport, park, and beach.
- **FR-007**: The POI calculator MUST prefer pre-loaded PostGIS POI data for spatial queries and fall back to the Overpass API if no pre-loaded data exists for that country.
- **FR-008**: After enrichment, the service MUST update the listing record in the database with all enriched fields and set an `enrichment_status` field to `completed`, `partial`, or `failed`.
- **FR-009**: The enricher MUST publish the enriched listing to the `listings.enriched.{country}` NATS subject.
- **FR-010**: The enricher MUST consume from the `listings.deduplicated.{country}` NATS subject (output of the deduplicator).

**Change Detector Service:**

- **FR-011**: The change detector MUST subscribe to NATS subject `scraper.cycle.completed.{country}.{portal}` and trigger a change-detection cycle for the specified source.
- **FR-012**: The change detector MUST compare all currently active listings for the given source against the set of listing IDs seen in the latest scrape cycle (determined by `last_seen_at` matching the cycle timestamp).
- **FR-013**: When an active listing's `asking_price` differs from the value in the latest scrape, the system MUST insert a row into `price_history` and update the listing's `asking_price`.
- **FR-014**: When an active listing is not present in the latest scrape cycle, the system MUST set `status = 'delisted'` and `delisted_at = NOW()`.
- **FR-015**: When a previously delisted listing reappears in the latest scrape cycle, the system MUST set `status = 'active'` and clear `delisted_at`.
- **FR-016**: The change detector MUST publish a `PriceChangeEvent` to the `listings.price-change.{country}` NATS subject for every price drop, including `listing_id`, `old_price`, `new_price`, `currency`, and `drop_percentage`.
- **FR-017**: The change detector MUST NOT produce any price-change or delisting event for a listing whose data has not changed.
- **FR-018**: Description changes MUST be detected and recorded but do not require a NATS event — only a DB update.

### Key Entities

- **EnrichmentResult**: Outcome of a single enricher run — contains partial listing field updates and a status (`completed`, `partial`, `no_match`, `failed`) with an optional error message.
- **CadastralRecord**: Official cadastral data returned by the Catastro WFS — cadastral reference, built area, year built, building geometry.
- **POIRecord**: A single point of interest stored in PostGIS — category, name, country, location geometry.
- **ScrapeCycleEvent**: NATS message published by the scrape orchestrator when a portal's scrape cycle completes — contains `portal`, `country`, `cycle_id`, `completed_at`.
- **PriceChangeEvent**: NATS message published by the change detector for price drops — contains `listing_id`, `country`, `old_price`, `new_price`, `currency`, `drop_percentage`, `recorded_at`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 80% of active Madrid listings are enriched with a valid Catastro cadastral reference within 24 hours of being deduplicated.
- **SC-002**: The area discrepancy flag is correctly set (true or false) on 100% of Spanish listings where Catastro data was successfully retrieved.
- **SC-003**: POI distances for any listing with a valid geolocation are accurate to within ±200 m of independently verified reference coordinates for a sample of 10 listings.
- **SC-004**: A price drop of €10,000 or more is recorded in `price_history` and a `price.changes` event is published within one processing cycle of the scrape completing.
- **SC-005**: A delisted listing is detected within one full scraping cycle and its `delisted_at` timestamp is set accordingly.
- **SC-006**: No `price_history` rows or `price.changes` events are generated for listings whose price has not changed (zero false positives).
- **SC-007**: The Catastro enricher processes no more than 1 API request per second under sustained load, verified by timing logs.

## Assumptions

- Listings are already geocoded (have a valid `location` geometry) before reaching the enricher; enrichment requiring a geocode is out of scope.
- The Catastro INSPIRE WFS endpoint is publicly accessible without authentication.
- OpenStreetMap PBF files for active countries are pre-downloaded and loaded into the PostGIS `poi` table by an out-of-band data-loading job (not part of this feature).
- The scrape orchestrator already publishes `scraper.cycle.completed.{country}.{portal}` events on cycle completion; if not, the change detector falls back to querying the DB for listings with `last_seen_at` in the last cycle window.
- Currency and EUR-normalised prices are already stored on each listing by the normalizer; the change detector compares `asking_price` (original currency) and also updates `asking_price_eur` on price changes.
- The pipeline service Alembic migrations are the authoritative schema source; new enrichment columns are added via a new migration in `services/pipeline/alembic/versions/`.
- GDPR compliance for enriched data (cadastral refs are public data) is out of scope for this feature.
