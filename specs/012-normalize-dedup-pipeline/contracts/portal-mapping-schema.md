# Portal Mapping Config Schema

**Feature**: 012-normalize-dedup-pipeline | **Date**: 2026-04-17

## Purpose

Each YAML file in `services/pipeline/config/mappings/` declares how to translate a portal's
raw JSON field names into the unified `NormalizedListing` schema. Adding a new portal requires
only a new YAML file — no code changes.

## File Naming Convention

`<country_code>_<portal_slug>.yaml` — e.g., `es_idealista.yaml`, `fr_seloger.yaml`.

## YAML Schema

```yaml
# Required top-level keys
portal: string          # must match RawListing.portal value exactly
country: string         # ISO 3166-1 alpha-2 uppercase

# Field mappings: source_field_name → target
fields:
  <source_field_name>:
    target: <unified_field_name>      # NormalizedListing field name
    transform: <transform_fn> | null  # optional transform function name

# Property type lookup table (portal-specific → canonical)
property_type_map:
  <portal_type>: <canonical_type>    # canonical: residential|commercial|industrial|land

# Condition lookup table (portal-specific → canonical)
condition_map:                        # optional
  <portal_condition>: <canonical>     # canonical: new|good|needs_renovation

# Special field pointers (required if portal has these fields)
currency_field: <source_field_name>   # field containing the currency code
area_unit_field: <source_field_name>  # field containing the area unit (optional)
country_uses_pieces: bool             # true for France portals (pièces → bedrooms)
```

## Supported Transform Function Names

| Function name | Input | Output | Notes |
|---------------|-------|--------|-------|
| `currency_convert` | `(amount, currency)` | EUR decimal | Reads exchange_rates table |
| `area_to_m2` | `(value, unit)` | m² decimal | Supports m2, sqft, ft2 |
| `map_property_type` | `(portal_type, type_map)` | canonical str | Uses `property_type_map` |
| `map_condition` | `(portal_condition, condition_map)` | canonical str | Uses `condition_map` |
| `pieces_to_bedrooms` | `(pieces)` | int | FR only: pièces - 1 |

## Example: `es_idealista.yaml`

```yaml
portal: idealista
country: ES

fields:
  precio:
    target: asking_price
    transform: null
  tipologia:
    target: property_type
    transform: map_property_type
  superficie:
    target: built_area
    transform: null
  habitaciones:
    target: bedrooms
    transform: null
  banos:
    target: bathrooms
    transform: null
  planta:
    target: floor_number
    transform: null
  ascensor:
    target: has_lift
    transform: null
  garaje:
    target: parking_spaces
    transform: null
  terraza:
    target: has_terrace
    transform: null
  anoConstruccion:
    target: year_built
    transform: null
  estado:
    target: condition
    transform: map_condition
  certificadoEnergetico:
    target: energy_rating
    transform: null
  latitud:
    target: _lat
    transform: null
  longitud:
    target: _lon
    transform: null
  url:
    target: source_url
    transform: null
  descripcion:
    target: description_orig
    transform: null
  numFotos:
    target: images_count
    transform: null
  direccion:
    target: address
    transform: null
  municipio:
    target: city
    transform: null
  provincia:
    target: region
    transform: null
  codigoPostal:
    target: postal_code
    transform: null

property_type_map:
  piso: residential
  atico: residential
  casa: residential
  chalet: residential
  duplex: residential
  estudio: residential
  local: commercial
  oficina: commercial
  nave: industrial
  terreno: land
  solar: land
  garaje: commercial

condition_map:
  buenEstado: good
  paraBaja: needs_renovation
  obraEnCurso: needs_renovation
  obraGuarderia: new
  obraNueva: new

currency_field: null   # Idealista always returns EUR
area_unit_field: null  # Idealista always returns m²
country_uses_pieces: false
```

## Example: `es_fotocasa.yaml`

```yaml
portal: fotocasa
country: ES

fields:
  price:
    target: asking_price
    transform: null
  propertyTypeId:
    target: property_type
    transform: map_property_type
  surface:
    target: built_area
    transform: null
  rooms:
    target: bedrooms
    transform: null
  bathrooms:
    target: bathrooms
    transform: null
  floor:
    target: floor_number
    transform: null
  hasLift:
    target: has_lift
    transform: null
  parkingIncluded:
    target: parking_spaces
    transform: null
  constructionYear:
    target: year_built
    transform: null
  status:
    target: condition
    transform: map_condition
  energyCertification:
    target: energy_rating
    transform: null
  latitude:
    target: _lat
    transform: null
  longitude:
    target: _lon
    transform: null
  detailUrl:
    target: source_url
    transform: null
  description:
    target: description_orig
    transform: null
  multimedia.images.count:
    target: images_count
    transform: null
  address:
    target: address
    transform: null
  city:
    target: city
    transform: null
  province:
    target: region
    transform: null
  postalCode:
    target: postal_code
    transform: null

property_type_map:
  1: residential   # piso
  2: residential   # casa
  3: residential   # chalet
  4: commercial    # local
  5: industrial    # nave
  6: land          # terreno

condition_map:
  good: good
  new: new
  secondhand: good
  toReform: needs_renovation

currency_field: null   # Fotocasa always returns EUR
area_unit_field: null
country_uses_pieces: false
```

## Validation Rules

The `PortalMapper` validates the YAML at load time:

1. `portal` and `country` are required strings.
2. Every `target` in `fields` must be a known field on `NormalizedListing` or one of the
   private accumulator keys (`_lat`, `_lon`).
3. Every `transform` value must be `null` or a key in the transform function registry.
4. `property_type_map` must map to one of `residential`, `commercial`, `industrial`, `land`.
5. Unknown keys in the YAML cause a load-time `ValueError` (fail fast, not silently).
