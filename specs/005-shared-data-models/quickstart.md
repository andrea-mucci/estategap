# Quickstart: Shared Data Models

**Feature**: 005-shared-data-models | **Date**: 2026-04-17

---

## Python — `libs/common`

### Install

```bash
cd libs/common
uv sync
```

### Use a model

```python
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
from estategap_common.models import NormalizedListing, ListingStatus, PropertyCategory

listing = NormalizedListing(
    id=uuid4(),
    country="ES",
    source="idealista",
    source_id="abc-123",
    source_url="https://www.idealista.com/inmueble/abc-123/",
    asking_price=Decimal("450000"),
    currency="EUR",
    asking_price_eur=Decimal("450000"),
    built_area_m2=Decimal("80"),
    property_category=PropertyCategory.RESIDENTIAL,
    status=ListingStatus.ACTIVE,
    first_seen_at=datetime.now(timezone.utc),
    last_seen_at=datetime.now(timezone.utc),
)

# Serialise to JSON (RFC 3339 datetimes, Decimal as number)
json_str = listing.model_dump_json()

# Export JSON Schema for documentation
schema = NormalizedListing.model_json_schema()
```

### Validation errors

```python
from pydantic import ValidationError
from estategap_common.models import NormalizedListing

try:
    NormalizedListing(
        ...,
        asking_price=Decimal("-100"),  # ❌ must be > 0
        country="XX",                  # ❌ invalid ISO 3166-1
        currency="ZZZ",                # ❌ invalid ISO 4217
    )
except ValidationError as e:
    print(e)  # lists all failing fields
```

### Run tests

```bash
cd libs/common
uv run pytest tests/ -v
uv run mypy estategap_common --strict
uv run ruff check estategap_common
```

---

## Go — `libs/pkg/models`

### Add dependency

```bash
cd libs/pkg
go get github.com/jackc/pgx/v5
go get github.com/shopspring/decimal
go get github.com/google/uuid
```

### Use a struct

```go
import (
    "encoding/json"
    "github.com/estategap/libs/models"
    "github.com/jackc/pgx/v5/pgtype"
    "github.com/shopspring/decimal"
)

// Scan from pgx row
var listing models.Listing
row := pool.QueryRow(ctx, `SELECT id, country, status, ... FROM listings WHERE id = $1`, id)
err := row.Scan(&listing.ID, &listing.Country, &listing.Status, ...)

// Marshal to JSON for API response
b, err := json.Marshal(listing)
```

### Deserialise from Python-produced JSON

```go
var listing models.Listing
err := json.Unmarshal(pythonBytes, &listing)
// listing.AskingPrice is a *decimal.Decimal — no float precision loss
// listing.ID is a pgtype.UUID — scan-ready for next DB write
```

### Run tests

```bash
cd libs/pkg
go test ./models/... -v
go vet ./models/...
golangci-lint run ./models/...
```

---

## Cross-Language Round-Trip Tests

```bash
# From repo root
cd tests/cross_language
uv run pytest test_roundtrip.py -v

cd ../../libs/pkg
go test ./models/... -run TestRoundTrip -v
```

---

## Export JSON Schemas (Python)

```python
import json
from estategap_common.models import (
    Listing, NormalizedListing, RawListing, AlertRule,
    ScoringResult, User, Zone, Country,
)

for model in [Listing, NormalizedListing, RawListing, AlertRule,
              ScoringResult, User, Zone, Country]:
    schema = model.model_json_schema()
    path = f"docs/schemas/{model.__name__}.json"
    with open(path, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"Wrote {path}")
```

---

## Common Pitfalls

| Mistake | Correct approach |
|---------|-----------------|
| Passing a naive `datetime` to any model field | Always use `datetime.now(timezone.utc)` or parse with `datetime.fromisoformat("...Z").replace(tzinfo=timezone.utc)` |
| Using `float` for prices in Python | Use `Decimal("450000.00")` |
| Using `float64` for prices in Go | Use `decimal.NewFromString("450000.00")` |
| Using `"XX"` as country code | Must be a valid ISO 3166-1 alpha-2 code from the allowlist |
| Forgetting `model_dump(mode="json")` vs `model_dump()` | Use `mode="json"` when producing JSON — it converts `Decimal` and `UUID` to serialisable types |
| Go: scanning a `pgtype.UUID` into a `string` | Use `pgtype.UUID` directly; it implements `pgx.Scanner` |
