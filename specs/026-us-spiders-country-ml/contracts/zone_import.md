# Zone Import Contract: US TIGER/Line

**Feature**: 026-us-spiders-country-ml  
**Date**: 2026-04-17

---

## Source Data

All shapefiles are downloaded from `https://www2.census.gov/geo/tiger/TIGER2024/`.

| Level | URL Path | File |
|-------|---------|------|
| State | `STATE/` | `tl_2024_us_state.zip` |
| County | `COUNTY/` | `tl_2024_us_county.zip` |
| City (Place) | `PLACE/` | `tl_2024_{state_fips}_place.zip` (one per state) |
| ZIP Code | `ZCTA520/` | `tl_2024_us_zcta520.zip` |
| Neighbourhood (Block Group) | `BG/` | `tl_2024_{state_fips}_bg.zip` (one per state) |

---

## Import Script Interface

```bash
# Full import (all 50 states, all levels)
python -m estategap_pipeline.zone_import.us_tiger \
    --level state county city zipcode neighbourhood \
    --state-fips all \
    --output-country US

# Single state (for testing)
python -m estategap_pipeline.zone_import.us_tiger \
    --level state county city zipcode neighbourhood \
    --state-fips 36 \     # 36 = New York
    --output-country US
```

---

## Zone Record Schema

Each imported zone is inserted into the existing `zones` table:

```python
{
    "country": "US",
    "level": "state" | "county" | "city" | "zipcode" | "neighbourhood",
    "name": str,          # TIGER NAME field
    "code": str,          # FIPS code or ZCTA
    "geometry": WKT,      # ST_Multi(ST_GeomFromGeoJSON(…)) in SRID 4326
    "parent_id": int | None,  # Resolved by ST_Within lookup
    "metadata": {
        "fips": str,
        "state_fips": str,
        "tiger_geoid": str,
    }
}
```

---

## Hierarchy Resolution

Parents are resolved bottom-up after all geometries are inserted:

```sql
-- Example: set county parent = state (where county centroid is within state)
UPDATE zones child
SET parent_id = parent.id
FROM zones parent
WHERE child.country = 'US'
  AND child.level = 'county'
  AND parent.level = 'state'
  AND parent.country = 'US'
  AND ST_Within(ST_Centroid(child.geometry), parent.geometry);
```

Run order: state → county → city → zipcode → neighbourhood.

---

## Listing Zone Assignment

After zone import, existing and future US listings are zone-assigned via the existing enrichment pipeline's `assign_zones` step (no code change required — the step performs `ST_Within(listing.location, zone.geometry)` for each level).
