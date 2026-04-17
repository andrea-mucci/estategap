# API Contract: Saved Searches

**Service**: Go API Gateway  
**Base Path**: `/api/v1/saved-searches`  
**Auth**: Bearer JWT (all endpoints require authentication)

---

## GET /api/v1/saved-searches

Return all saved searches for the authenticated user.

**Response 200**:
```json
{
  "data": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "Barcelona Tier 1 under 400k",
      "filters": {
        "country": "ES",
        "city": "Barcelona",
        "deal_tier": [1],
        "max_price_eur": 400000,
        "sort_by": "deal_score",
        "sort_dir": "desc"
      },
      "created_at": "2026-04-17T10:00:00Z",
      "updated_at": "2026-04-17T10:00:00Z"
    }
  ]
}
```

---

## POST /api/v1/saved-searches

Create a new saved search.

**Request body**:
```json
{
  "name": "Barcelona Tier 1 under 400k",
  "filters": {
    "country": "ES",
    "city": "Barcelona",
    "deal_tier": [1],
    "max_price_eur": 400000,
    "sort_by": "deal_score",
    "sort_dir": "desc"
  }
}
```

**Response 201**:
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Barcelona Tier 1 under 400k",
  "filters": { ... },
  "created_at": "2026-04-17T10:00:00Z",
  "updated_at": "2026-04-17T10:00:00Z"
}
```

**Validation**:
- `name`: required, max 100 chars
- `filters.country`: required, must be a supported country code
- Max 20 saved searches per user (return 422 if exceeded)

---

## DELETE /api/v1/saved-searches/{id}

Delete a saved search by ID.

**Path param**: `id` — UUID of the saved search

**Response 204**: No content

**Error 404**: `{ "error": "saved search not found" }` — if ID doesn't belong to the user

---

## Error Responses (all endpoints)

| Status | Meaning |
|--------|---------|
| 400 | Invalid request body |
| 401 | Missing or invalid JWT |
| 404 | Resource not found |
| 422 | Validation error (e.g., limit exceeded) |
| 500 | Internal server error |
