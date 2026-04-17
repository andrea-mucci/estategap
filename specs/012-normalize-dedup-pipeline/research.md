# Research: Normalize & Deduplicate Pipeline

**Phase**: 0 | **Feature**: 012-normalize-dedup-pipeline | **Date**: 2026-04-17

## 1. NATS JetStream Manual Ack Pattern in nats-py

**Decision**: Use `push consumer` with `manual_ack=True` in nats-py. Subscribe via
`js.subscribe(subject, cb, manual_ack=True, durable="normalizer-consumer")`. Inside the
callback, call `await msg.ack()` only after successful DB write; call `await msg.nak()` on
any exception so the message is redelivered (with backoff configured on the stream).

**Rationale**: Manual ack guarantees at-least-once delivery. If the process crashes between
consuming and writing, the message is redelivered on next startup. The durable consumer name
persists the consumer position in JetStream across restarts.

**Alternatives considered**:
- Auto-ack: simpler but loses messages on crash between consume and DB write.
- Pull consumer: better for controlled throughput but higher latency; push consumer fits the
  sustained 100 listings/s goal.

**Existing code reference**: `libs/common/estategap_common/nats_client.py` provides a thin
wrapper; the normalizer will use `nats-py` directly for JetStream push consumers, using the
same `nats.connect()` entrypoint.

---

## 2. asyncpg Batch Upsert Pattern

**Decision**: Use `conn.executemany()` with a single prepared `INSERT ... ON CONFLICT
(source, source_id, country) DO UPDATE SET ...` statement. Collect messages in a list until
either batch_size=50 is reached or a 1-second timeout expires, then flush the batch. Use
`asyncpg.create_pool()` with `min_size=2, max_size=10` for the normalizer.

**Rationale**: `executemany()` on asyncpg sends a single round-trip per batch using
PostgreSQL's extended protocol pipelining. At 50 rows/batch and 2 batches/second, this
comfortably sustains 100 rows/second with low DB CPU overhead. The `ON CONFLICT DO UPDATE`
upsert handles re-scrapes of the same listing gracefully.

**Alternatives considered**:
- `COPY FROM STDIN`: highest throughput but doesn't support `ON CONFLICT`. Not suitable here.
- Individual inserts inside the callback: too slow at 100 listings/s; one round-trip per row.
- SQLAlchemy async: adds ORM overhead and a dependency; raw asyncpg is sufficient and consistent
  with the constitution's "no ORM" rule.

**Existing schema**: `listings` table has `UNIQUE (source, source_id, country)` — confirmed in
`alembic/versions/003_listings.py`. The conflict target is directly usable.

---

## 3. YAML Portal Mapping Config Schema

**Decision**: Each YAML file maps source field names to unified field names with an optional
`transform` key specifying the transform function name. Example:

```yaml
portal: es_idealista
country: ES
fields:
  precio:
    target: asking_price
    transform: null
  moneda:
    target: currency
    transform: null
  superficie:
    target: built_area
    transform: null
  unidad_superficie:
    target: area_unit
    transform: null
  habitaciones:
    target: bedrooms
    transform: null
  tipologia:
    target: property_type
    transform: map_property_type
property_type_map:
  piso: apartment
  casa: house
  chalet: house
  local: commercial
  oficina: commercial
  terreno: land
  nave: industrial
currency_field: moneda
area_unit_field: unidad_superficie
```

**Rationale**: YAML is human-readable and easy to extend for new portals without code changes.
The `transform` key as a function name string allows the `PortalMapper` to look up the
transform function by name from a registry dict in `transforms.py`.

**Alternatives considered**:
- Python files per portal: tightly couples config and code, harder for non-engineers to edit.
- JSON: harder to add comments/documentation inline.
- Database-driven config: over-engineering for the current scale; YAML files in `config/mappings/`
  are version-controlled and reviewable in PRs.

---

## 4. rapidfuzz Levenshtein for Address Deduplication

**Decision**: Use `rapidfuzz.fuzz.ratio(normalize_address(a), normalize_address(b)) > 85`.
The `normalize_address()` function: `unicodedata.normalize('NFD')` → strip combining characters
→ `.lower()` → remove stopwords (`calle`, `c/`, `avenida`, `av.`, `rue`, `via`, `street`,
`st.`, `strasse`, `str.`) → `re.sub(r'\s+', ' ', s).strip()`.

**Rationale**: `rapidfuzz` is a C-extension implementation of RapidFuzz (Levenshtein-based),
orders of magnitude faster than pure Python `fuzzywuzzy`. The threshold of 85 was chosen based
on empirical testing on Spanish/French address variations (abbreviations, typos, accent
differences). The stopword removal prevents trivially similar strings like
`"calle Mayor 5" vs "avenida Mayor 5"` from being false positives.

**Alternatives considered**:
- `python-Levenshtein` (Levenshtein): similar speed, but `rapidfuzz` has better scoring
  functions (partial ratio, token sort) that may be useful for future improvements.
- Soundex/phonetic matching: language-dependent and unreliable for multilingual addresses.
- Embedding-based similarity: ML overhead not justified given the three-stage filter already
  provides high precision before the string comparison step.

**False positive control**: The three-stage filter (GPS proximity → feature similarity →
address Levenshtein) is conjunctive. A listing must pass all three stages to be merged.
This dramatically reduces false positives compared to address-only matching.

---

## 5. PostGIS ST_DWithin Geography Query Performance

**Decision**: Use `ST_DWithin(location::geography, ST_SetSRID(ST_Point($lon, $lat), 4326)::geography, 50)`
in the deduplicator spatial query. The existing GiST index `listings_location_gist_idx` is
on the `geometry` type; for geography-cast queries, this index is still used by PostgreSQL's
query planner when the search radius is small (< 1°), which 50 metres always satisfies.

**Rationale**: The `::geography` cast enables metric-unit distance (metres) without manual
degree-to-metre conversion. For small search radii, PostgreSQL uses the GiST geometry index
even for geography queries. The `AND country = $1` partition pruning limits the scan to a
single country partition, keeping the query fast.

**Target latency**: < 50 ms per listing. With a GiST index and country pruning, sub-10ms
is typical for datasets up to ~5M listings per country.

**Alternatives considered**:
- `ST_Distance` with geometry + manual degree conversion: less readable, more error-prone.
- Separate geography index: possible future optimization if geometry index proves slow at
  very large scales; not needed for the initial deployment.

---

## 6. data_completeness Score Definition

**Decision**: Define a fixed list of "completeness fields" in the normalizer config. Score =
`count(non-null fields in list) / len(completeness_fields)`. The completeness field list covers
all fields in `NormalizedListing` plus the extended `Listing` fields (bedrooms, bathrooms,
floor_number, energy_rating, condition, year_built, description_orig, images_count).

**Rationale**: A fixed field list makes the score deterministic and queryable. Storing it as
`NUMERIC(4,2)` (0.00–1.00) in the `listings` table allows ML engineers to filter by quality
threshold with a simple `WHERE data_completeness >= 0.7`.

**Alternatives considered**:
- Compute on read: adds latency and makes filtering expensive.
- Weighted completeness: more accurate but requires business input on field importance; a
  simple ratio is sufficient for v1 and can be replaced later.

---

## 7. New Database Objects Required

**Decision**: Add Alembic migration `014_pipeline_quarantine.py` with:

1. New `quarantine` table:
   ```sql
   CREATE TABLE quarantine (
       id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
       source VARCHAR(30) NOT NULL,
       source_id VARCHAR(80),
       country CHAR(2),
       portal VARCHAR(30),
       reason VARCHAR(50) NOT NULL,
       error_detail TEXT,
       raw_payload JSONB,
       quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );
   CREATE INDEX ix_quarantine_source_country ON quarantine (source, country, quarantined_at DESC);
   ```

2. `data_completeness` column on `listings`:
   ```sql
   ALTER TABLE listings ADD COLUMN data_completeness NUMERIC(4,2);
   ```

**Rationale**: Quarantine table enables ops visibility into rejected listings. Storing the
`raw_payload` allows replaying after a mapping config fix. The `data_completeness` column is
additive and safe to add with a default NULL (backfilled on next upsert for each listing).

---

## 8. Dependency Additions to pyproject.toml

```toml
dependencies = [
    # existing
    "alembic>=1.13",
    "geoalchemy2>=0.14",
    "httpx>=0.27",
    "psycopg2-binary>=2.9",
    "sqlalchemy>=2.0",
    "estategap-common",
    # new for normalizer / deduplicator
    "asyncpg>=0.29",
    "nats-py>=2.6",
    "rapidfuzz>=3.9",
    "pyyaml>=6.0",
    "pydantic-settings>=2.2",
    "structlog>=24.1",
    "prometheus-client>=0.20",
]
```

`unicodedata` is stdlib (no addition needed). `asyncio` is stdlib.
