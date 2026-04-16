# Feature: Shared Data Models

## /plan prompt

```
Implement shared models with these technical decisions:

## Python (libs/common/)
- Use Pydantic v2 with ConfigDict(strict=True) for type safety
- Enums for: PropertyCategory (residential, commercial, industrial, land), DealTier (1-4), SubscriptionTier (free, basic, pro, global, api), ListingStatus (active, delisted, sold)
- Custom validators: price must be positive, area must be > 0, country must be valid ISO 3166-1 alpha-2, currency must be valid ISO 4217
- Use datetime with timezone (aware datetimes only)
- Export JSON Schema from Pydantic for documentation

## Go (pkg/models/)
- Plain structs with json, db tags
- Use pgtype.UUID, pgtype.Timestamptz for PostgreSQL compatibility
- Use decimal type (shopspring/decimal) for prices to avoid floating point issues
- Implement Scan/Value interfaces for custom types
- Unit tests with table-driven test pattern

## Cross-Language Compatibility
- Python JSON output must be parseable by Go json.Unmarshal and vice versa
- Date format: RFC 3339 (ISO 8601 with timezone)
- UUID format: standard 8-4-4-4-12
- Null handling: Python None → JSON null → Go pointer types
```
