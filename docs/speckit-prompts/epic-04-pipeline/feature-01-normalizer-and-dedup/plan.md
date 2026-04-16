# Feature: Normalizer & Deduplicator

## /plan prompt

```
Implement with these technical decisions:

## Normalizer (services/pipeline/normalizer/)
- Async NATS consumer using nats-py with manual ack
- Per-portal mapping config: YAML files in config/mappings/ (es_idealista.yaml, es_fotocasa.yaml, etc.). Maps source field names → unified field names with optional transform functions.
- Transform functions: currency_convert(amount, from_currency), area_to_m2(value, unit), map_property_type(portal_type, country), map_condition(portal_condition, country), pieces_to_bedrooms(pieces) for France
- Pydantic validation: NormalizedListing model. On validation error → log to quarantine table with error details.
- DB write: asyncpg with batch inserts (INSERT ... ON CONFLICT (source, source_id) DO UPDATE for upserts)
- Throughput target: async processing, batch size 50, target 100/s

## Deduplicator (services/pipeline/deduplicator/)
- Async NATS consumer
- Stage 1: query PostGIS `SELECT id, address, built_area_m2, bedrooms, property_type FROM listings WHERE ST_DWithin(location, ST_SetSRID(ST_Point(lon, lat), 4326)::geography, 50) AND country = $1 AND id != $2`
- Stage 2: for each candidate, check abs(area_a - area_b) / area_a < 0.10 AND rooms match AND type match
- Stage 3: rapidfuzz.fuzz.ratio(normalize_address(a), normalize_address(b)) > 85
- normalize_address(): lowercase, remove accents, remove common words (calle, avenida, rue, via, street), collapse whitespace
- On match: UPDATE both listings SET canonical_id = (SELECT canonical_id FROM listings WHERE id = oldest_match_id)
- First listing in a canonical group: canonical_id = own id
```
