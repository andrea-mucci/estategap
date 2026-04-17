# Data Model: EU Portals & Enrichment

**Feature**: 025-eu-portals-enrichment  
**Phase**: 1 — Design  
**Date**: 2026-04-17

---

## Existing Entities Extended

### NormalizedListing (extended)

Existing entity in the `listings` partitioned table. The following fields are added or newly populated for EU countries:

| Field | Type | Notes |
|-------|------|-------|
| `currency` | VARCHAR(3) | Source currency — `EUR` (default), `GBP` (UK). Already exists; now populated for UK. |
| `original_price` | NUMERIC(14,2) | Price in source currency. Already exists; now populated for GBP listings. |
| `council_tax_band` | VARCHAR(2) | UK only. A–H. New field. |
| `epc_rating` | VARCHAR(1) | UK only. A–G. Maps to energy_rating but kept separately for raw UK value. |
| `tenure` | VARCHAR(10) | UK only. `leasehold` or `freehold`. New field. |
| `leasehold_years_remaining` | SMALLINT | UK only, nullable. New field. |
| `seller_type` | VARCHAR(10) | FR LeBonCoin: `pro` or `private`. New field. |
| `omi_zone_code` | VARCHAR(20) | IT enrichment: OMI zone identifier. New field. |
| `omi_price_min_eur_m2` | NUMERIC(10,2) | IT enrichment: OMI min €/m² for zone+type. New field. |
| `omi_price_max_eur_m2` | NUMERIC(10,2) | IT enrichment: OMI max €/m² for zone+type. New field. |
| `omi_period` | VARCHAR(10) | IT enrichment: e.g., `2024-H1`. New field. |
| `price_vs_omi` | NUMERIC(6,4) | IT enrichment: listing €/m² ÷ OMI midpoint. New field. |
| `bag_id` | VARCHAR(16) | NL enrichment: BAG pand identifier. New field. |
| `official_area_m2` | NUMERIC(8,2) | NL enrichment: BAG official floor area. Already exists (also used by Catastro). |
| `dvf_nearby_count` | SMALLINT | FR enrichment: number of DVF transactions found within 200m. New field. |
| `dvf_median_price_m2` | NUMERIC(10,2) | FR enrichment: median €/m² of nearby DVF transactions. New field. |
| `uk_lr_match_count` | SMALLINT | UK enrichment: number of Land Registry matches. New field. |
| `uk_lr_last_price_gbp` | INTEGER | UK enrichment: most recent matched sale price in GBP. New field. |
| `uk_lr_last_date` | DATE | UK enrichment: date of most recent matched sale. New field. |

**Alembic migration**: `services/pipeline/alembic/versions/025_eu_listing_fields.py`

---

## New Entities

### dvf_transactions

French Demandes de Valeurs Foncières — historical property sale records.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL | Primary key |
| `date_mutation` | DATE | Sale date |
| `valeur_fonciere` | NUMERIC(14,2) | Sale price (EUR) |
| `type_local` | VARCHAR(50) | Property type (`Appartement`, `Maison`, etc.) |
| `surface_reelle_bati` | NUMERIC(8,2) | Built area m² |
| `adresse_numero` | VARCHAR(10) | Street number |
| `adresse_nom_voie` | TEXT | Street name |
| `code_postal` | VARCHAR(10) | Postal code |
| `commune` | VARCHAR(150) | Municipality name |
| `geom` | GEOMETRY(POINT, 4326) | Geocoded coordinates |
| `loaded_at` | TIMESTAMPTZ | Import timestamp |

**Indexes**:
- `GIST(geom)` — spatial index for radius queries
- `(code_postal, type_local)` — composite for pre-filter

**Alembic migration**: `services/pipeline/alembic/versions/025_dvf_transactions.py`

---

### uk_price_paid

UK Land Registry Price Paid Data — historical property sale records.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL | Primary key |
| `transaction_uid` | UUID | Land Registry transaction ID (unique) |
| `price_gbp` | INTEGER | Sale price in pence |
| `date_transfer` | DATE | Transfer date |
| `postcode` | VARCHAR(8) | UK postcode |
| `property_type` | CHAR(1) | D/S/T/F/O (detached/semi/terraced/flat/other) |
| `old_new` | CHAR(1) | Y=new build, N=established |
| `tenure` | CHAR(1) | F=freehold, L=leasehold |
| `paon` | TEXT | Primary addressable object name |
| `saon` | TEXT | Secondary addressable object name (nullable) |
| `street` | TEXT | Street name |
| `locality` | TEXT | Locality (nullable) |
| `town_city` | TEXT | Town/city |
| `district` | TEXT | District |
| `county` | TEXT | County |
| `address_normalized` | TEXT | Computed: concat of paon+saon+street+town_city+postcode, lowercased |
| `loaded_at` | TIMESTAMPTZ | Import timestamp |

**Indexes**:
- `(postcode)` — for postcode pre-filter
- `(transaction_uid)` — for deduplication on re-import

**Alembic migration**: `services/pipeline/alembic/versions/026_uk_price_paid.py`

---

### omi_zones

Italian Agenzia delle Entrate OMI zone reference price bands.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key (gen_random_uuid()) |
| `zona_omi` | VARCHAR(20) | OMI zone code (e.g., `A1`, `B3`) |
| `comune_istat` | VARCHAR(10) | ISTAT municipality code |
| `comune_name` | VARCHAR(150) | Municipality name |
| `period` | VARCHAR(10) | Semester (e.g., `2024-H1`) |
| `tipologia` | VARCHAR(80) | Property type (e.g., `Abitazioni civili`, `Ville e villini`) |
| `fascia` | VARCHAR(20) | Zone classification (centrale/semicentrale/periferica) |
| `price_min` | NUMERIC(10,2) | Minimum €/m² |
| `price_max` | NUMERIC(10,2) | Maximum €/m² |
| `geometry` | GEOMETRY(MULTIPOLYGON, 4326) | Zone boundary (nullable — some OMI zones lack geometries) |
| `loaded_at` | TIMESTAMPTZ | Import timestamp |

**Indexes**:
- `(zona_omi, period, tipologia)` — for lookup
- `GIST(geometry)` — for spatial assignment

**Alembic migration**: `services/pipeline/alembic/versions/027_omi_zones.py`

---

## Existing Entity: zones (extended via import)

The existing `zones` table gains zone records for IT, FR, GB, NL. No schema changes needed — the table already supports all 4 countries via `country_code CHAR(2)`.

**Zone level mapping per country**:

| Country | Platform level 1 | Platform level 2 | Platform level 3 |
|---------|-----------------|-----------------|-----------------|
| Italy (IT) | regione (20) | provincia (107) | comune (7,904) |
| France (FR) | région (13 metro + 5 overseas) | département (101) | commune (34,935) |
| UK (GB) | country (4: ENG/SCT/WLS/NIR) | county (~100) | district (~400) |
| Netherlands (NL) | provincie (12) | gemeente (342) | — (only 3 levels) |

---

## Field Mapping YAML Files

Seven new YAML files in `services/pipeline/config/mappings/`:

| File | Portal | Country |
|------|--------|---------|
| `it_immobiliare.yaml` | Immobiliare.it | IT |
| `it_idealista.yaml` | Idealista IT | IT |
| `fr_seloger.yaml` | SeLoger | FR |
| `fr_leboncoin.yaml` | LeBonCoin | FR |
| `fr_bienici.yaml` | Bien'ici | FR |
| `gb_rightmove.yaml` | Rightmove | GB |
| `nl_funda.yaml` | Funda | NL |

Each YAML declares:
- `portal`, `country`, `currency_field` (null=EUR, or source field name)
- `country_uses_pieces: true` for FR portals (pièces → bedrooms)
- `fields`: source_field → {target, transform}
- `property_type_map`: portal values → platform type
- `condition_map`: portal values → platform condition
- `expected_fields`: list of fields required for completeness scoring

---

## Enricher Output Summary

| Enricher | Country | Match Method | Output Fields |
|----------|---------|-------------|--------------|
| FranceDVFEnricher | FR | ST_DWithin 200m + property_type | dvf_nearby_count, dvf_median_price_m2 |
| UKLandRegistryEnricher | GB | postcode + rapidfuzz ≥90 | uk_lr_match_count, uk_lr_last_price_gbp, uk_lr_last_date |
| ItalyOMIEnricher | IT | ST_Within(listing, omi_zone) | omi_zone_code, omi_price_min/max_eur_m2, omi_period, price_vs_omi |
| NetherlandsBAGEnricher | NL | BAG ID (direct) or address/postcode WFS | year_built, official_area_m2, bag_id, building_geometry_wkt |
