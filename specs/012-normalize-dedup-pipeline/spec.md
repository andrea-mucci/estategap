# Feature Specification: Normalize & Deduplicate Pipeline

**Feature Branch**: `012-normalize-dedup-pipeline`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Build the data pipeline services that transform raw scraped data into normalized, deduplicated listings."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Raw Listings Converted to Unified Schema (Priority: P1)

A data analyst queries the listings database and finds that all listings — regardless of which portal
they were scraped from — share the same field names, units, and value formats. A Madrid apartment
from Idealista and a Paris flat from SeLoger both have `built_area_m2`, `asking_price_eur`, and a
canonical `property_category`, even though each portal uses completely different field names and
conventions in its raw output.

**Why this priority**: Without a unified schema the entire downstream stack (ML scoring, alert
matching, API responses) collapses — every consumer would have to deal with per-portal
heterogeneity. This is the foundational pipeline step.

**Independent Test**: Feed a synthetic Idealista raw listing into the pipeline consumer. Query the
`listings` table and verify all mapped fields are present with correct values and types.

**Acceptance Scenarios**:

1. **Given** a raw Idealista listing with portal-specific field names, **When** the normalizer
   processes it, **Then** the resulting DB row contains unified field names and the `source` column
   records `idealista`.
2. **Given** a raw Fotocasa listing with a `precioTotal` field, **When** the normalizer processes
   it, **Then** `asking_price` is populated with the correct numeric value.
3. **Given** a portal for which no mapping config exists, **When** the normalizer receives a
   message, **Then** the listing is quarantined with reason `no_mapping_config` and no row is
   written to the listings table.

---

### User Story 2 - Prices and Areas Expressed in Standard Units (Priority: P1)

A data analyst compares listings from Spain (EUR), the UK (GBP/sqft) and the USA (USD/sqft) side
by side. Every listing has `asking_price_eur` and `built_area_m2` populated using the correct
conversion, making cross-market comparison possible without any manual unit handling.

**Why this priority**: Without standard units, cross-country analytics and ML models cannot be
built. This is a data-quality invariant that must hold for every listing.

**Independent Test**: Submit raw listings with prices in GBP and USD and areas in sqft. Verify
`asking_price_eur` and `built_area_m2` are correct against today's ECB exchange rate and the
standard 1 sqft = 0.0929 m² conversion.

**Acceptance Scenarios**:

1. **Given** a UK listing with price in GBP, **When** the normalizer processes it, **Then**
   `asking_price_eur` equals `asking_price * GBP/EUR rate` from the `exchange_rates` table, within
   1 cent.
2. **Given** a US listing with area in sqft, **When** the normalizer processes it, **Then**
   `built_area_m2` equals `sqft * 0.092903`, rounded to 2 decimal places.
3. **Given** a French listing where the portal reports `pièces` (total rooms including living room),
   **When** the normalizer processes it, **Then** `bedrooms` equals `pièces - 1`.
4. **Given** no exchange rate exists for today's date, **When** the normalizer processes a
   non-EUR listing, **Then** it falls back to the most recent available rate for that currency and
   logs a warning.

---

### User Story 3 - Invalid Listings Rejected Before Reaching the Database (Priority: P1)

An operator reviews the quarantine log and finds all listings that could not be normalized — each
with a clear reason (missing price, missing coordinates, zero area). None of these defective
listings appear in the main listings table, ensuring the database contains only trustworthy data.

**Why this priority**: A single invalid listing (e.g., price = 0) reaching the database can
corrupt ML training data or trigger false alerts. Quarantine is the data quality firewall.

**Independent Test**: Send ten synthetic raw listings: five valid, two with price = 0, two with no
GPS, one with no property type. Verify five rows in `listings`, five rows in `quarantine` with
appropriate reasons, and zero exceptions in the consumer logs.

**Acceptance Scenarios**:

1. **Given** a raw listing where the portal-reported price resolves to 0 or is absent, **When**
   the normalizer validates it, **Then** the listing is written to the quarantine table with reason
   `invalid_price` and no row is written to `listings`.
2. **Given** a raw listing with no GPS coordinates and no geocodeable address, **When** the
   normalizer validates it, **Then** the listing is quarantined with reason `missing_location`.
3. **Given** a raw listing that fails Pydantic validation on any field, **When** the normalizer
   processes it, **Then** the validation error detail is persisted in the quarantine record and the
   NATS message is acknowledged so it is not redelivered.

---

### User Story 4 - Identical Property From Two Portals Appears Once (Priority: P1)

A subscriber searching for a Madrid flat sees one listing per property, not two — even though the
same apartment is listed on both Idealista and Fotocasa. Both source records exist in the database
(full audit trail preserved), but they share a `canonical_id` that downstream systems use for
deduplication.

**Why this priority**: Without deduplication, users see duplicate listings, ML models double-count
data, and alert engines fire redundant notifications. Deduplication is what turns raw portal data
into a reliable property graph.

**Independent Test**: Seed the database with a known Idealista listing. Publish the same property
via Fotocasa. After the deduplicator processes the Fotocasa listing, verify both records share the
same `canonical_id` equal to the Idealista listing's own ID.

**Acceptance Scenarios**:

1. **Given** two listings within 50 metres of each other with matching area (±10%), same room
   count, same property type, and normalized address similarity > 85%, **When** the deduplicator
   processes the second listing, **Then** both records have the same `canonical_id`.
2. **Given** two listings that are geographically close but have different room counts, **When**
   the deduplicator evaluates them, **Then** they are treated as distinct properties and each
   retains its own `canonical_id`.
3. **Given** the first listing in a canonical group, **When** it is first inserted, **Then** its
   `canonical_id` equals its own `id`.
4. **Given** three listings of the same property from three different portals, **When** the
   deduplicator processes each in turn, **Then** all three share the `canonical_id` of the
   earliest-inserted record.

---

### User Story 5 - Data Completeness Visible per Listing (Priority: P2)

An ML engineer queries the listings table and filters by `data_completeness >= 0.7` to build a
training set with sufficient feature coverage. Each listing carries a completeness score
(0.0–1.0) indicating what fraction of the defined schema fields are populated.

**Why this priority**: Completeness scoring enables downstream consumers to make informed
quality-based decisions without re-inspecting every field themselves.

**Independent Test**: Verify that a listing with all optional fields populated scores 1.0 and a
listing with only mandatory fields scores < 0.5.

**Acceptance Scenarios**:

1. **Given** a listing with only mandatory fields (price, area, location), **When** it is written
   to the database, **Then** `data_completeness` reflects the fraction of all schema fields that
   are non-null.
2. **Given** a fully populated listing, **When** it is written to the database, **Then**
   `data_completeness` is 1.0.

---

### Edge Cases

- What happens when the `exchange_rates` table has no entry for a given currency?
- How does the normalizer behave when a portal mapping YAML file is malformed?
- What happens when the PostGIS proximity query returns hundreds of candidates for a dense urban block?
- How does the deduplicator handle a listing that is a duplicate of a quarantined listing?
- What happens when the NATS consumer receives a message that is not valid JSON?
- How does the pipeline recover if the database is temporarily unreachable during a batch write?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The normalizer MUST subscribe to `raw.listings.*` and process each message as a
  `RawListing` payload.
- **FR-002**: The normalizer MUST load a per-portal YAML mapping config that maps source field
  names to unified schema fields and specifies optional transform functions for each field.
- **FR-003**: The normalizer MUST apply transform functions: currency conversion to EUR, area
  conversion to m², property type mapping to canonical taxonomy, condition mapping, and France
  `pièces`-to-bedrooms conversion.
- **FR-004**: The normalizer MUST validate the mapped listing against the `NormalizedListing`
  Pydantic model; any validation failure MUST result in a quarantine record and no database write.
- **FR-005**: The normalizer MUST reject listings where `asking_price` resolves to zero or is
  absent, writing them to the quarantine table.
- **FR-006**: The normalizer MUST reject listings with no resolvable location (no GPS and no
  address), writing them to the quarantine table.
- **FR-007**: The normalizer MUST compute a `data_completeness` score (0.0–1.0) as the fraction
  of defined schema fields that are non-null, and store it on the listing row.
- **FR-008**: The normalizer MUST write valid listings to the `listings` table using upsert
  semantics (insert or update on `(source, source_id, country)` conflict).
- **FR-009**: The normalizer MUST publish each successfully normalized listing to
  `normalized.listings.<country>` on NATS JetStream.
- **FR-010**: The normalizer MUST acknowledge the NATS message only after a successful database
  write; on failure it MUST NAK so the message is redelivered.
- **FR-011**: The normalizer MUST process messages in async batches (batch size 50) to sustain
  100 listings/second throughput.
- **FR-012**: The deduplicator MUST subscribe to `normalized.listings.*` and, for each listing,
  query the database for spatial candidates within 50 metres using PostGIS.
- **FR-013**: The deduplicator MUST filter spatial candidates by feature similarity: area within
  ±10%, matching bedroom count, and matching property type.
- **FR-014**: The deduplicator MUST apply Levenshtein-based address similarity on
  accent-stripped, stopword-removed, lowercased addresses; threshold > 85% constitutes a match.
- **FR-015**: On a confirmed match, the deduplicator MUST update both the new listing and all
  existing records in the canonical group to share the `canonical_id` of the
  earliest-inserted matched record.
- **FR-016**: A listing with no match MUST have its `canonical_id` set to its own `id`.
- **FR-017**: The deduplicator MUST publish each processed listing (with `canonical_id` resolved)
  to `deduplicated.listings.<country>` on NATS JetStream.
- **FR-018**: Both services MUST expose Prometheus-compatible metrics:
  `pipeline_messages_processed_total`, `pipeline_messages_quarantined_total`,
  `pipeline_batch_duration_seconds`, labelled by `service` and `portal`.
- **FR-019**: Both services MUST use structured logging (JSON) with correlation fields: `portal`,
  `country`, `source_id`, `trace_id`.

### Key Entities

- **RawListing**: Upstream contract from spider-workers; contains `external_id`, `portal`,
  `country_code`, `raw_json`, `scraped_at`. Already defined in `libs/common`.
- **NormalizedListing**: Output of the normalizer; unified schema ready for DB insertion.
  Already defined in `libs/common`.
- **PortalMapping**: YAML configuration per portal that declares field mappings and transform
  functions. Loaded at startup, one file per portal.
- **QuarantineRecord**: Persisted record of a rejected listing, including source, reason,
  error detail, and raw payload.
- **CanonicalGroup**: Logical grouping of listings sharing the same `canonical_id`; not a
  separate table — expressed as a shared UUID value on the `listings` rows.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A raw Idealista listing published to NATS results in a correctly populated row in
  the `listings` table with all mapped fields present, verified end-to-end.
- **SC-002**: Currency conversion accuracy is within 1 cent of the ECB reference rate for
  supported currencies (GBP, USD, CHF, PLN).
- **SC-003**: sqft-to-m² conversion is accurate to 2 decimal places against the standard
  factor (1 sqft = 0.092903 m²).
- **SC-004**: France `pièces` correctly maps to `bedrooms = pièces - 1` for 100% of test cases.
- **SC-005**: Listings with `asking_price = 0` or no location are never present in the `listings`
  table; 100% are in the quarantine table.
- **SC-006**: Two listings of the same property from Idealista and Fotocasa are assigned the
  same `canonical_id` within one processing cycle.
- **SC-007**: False-positive deduplication rate is below 5% on a 1,000-listing test set with
  known ground truth.
- **SC-008**: The pipeline sustains 100 listings per second throughput under steady-state load,
  measured at the database write layer.

## Assumptions

- The `exchange_rates` table is populated by an external ECB rate fetcher (out of scope for this
  feature); the normalizer treats the table as read-only and falls back to the most recent rate
  when today's rate is absent.
- The `listings` table and all indexes defined in migration `003_listings.py` are in place;
  this feature adds only the `quarantine` table and a `data_completeness` column migration.
- `NormalizedListing` and `RawListing` Pydantic models in `libs/common` are the authoritative
  schema contracts; this feature consumes them without redefining them.
- The NATS JetStream streams `raw.listings`, `normalized.listings`, and `deduplicated.listings`
  are created by the scrape-orchestrator infrastructure; this feature only publishes and subscribes.
- Initial portal mapping configs cover Idealista ES and Fotocasa ES; other portals are additive
  and do not require code changes.
- Geocoding (converting address string to GPS) is out of scope; listings without GPS in their
  raw payload are quarantined.
- The normalizer and deduplicator run as separate long-lived processes within the existing
  `services/pipeline/` Python service.
