# API Contract: CRM (Pipeline Actions & Notes)

**Service**: Go API Gateway  
**Base Path**: `/api/v1/listings/{id}/crm`  
**Auth**: Bearer JWT (all endpoints require authentication)

---

## GET /api/v1/listings/{id}/crm

Fetch the CRM entry for a specific listing for the authenticated user.

**Path param**: `id` — listing UUID

**Response 200**:
```json
{
  "listing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "favorite",
  "notes": "Good location, close to metro. Follow up next week.",
  "updated_at": "2026-04-17T12:30:00Z"
}
```

**Response 200 (no CRM entry exists)**:
```json
{
  "listing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": null,
  "notes": "",
  "updated_at": null
}
```

---

## GET /api/v1/crm/bulk

Fetch CRM entries for multiple listings in a single request. Used by the search page to populate CRM badges on search result cards.

**Request body**:
```json
{
  "listing_ids": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "7cb12e89-1234-5678-abcd-ef0123456789"
  ]
}
```

**Response 200**:
```json
{
  "data": {
    "3fa85f64-5717-4562-b3fc-2c963f66afa6": {
      "status": "favorite",
      "notes": "...",
      "updated_at": "2026-04-17T12:30:00Z"
    },
    "7cb12e89-1234-5678-abcd-ef0123456789": {
      "status": null,
      "notes": "",
      "updated_at": null
    }
  }
}
```

**Validation**: `listing_ids` max 100 items per request.

---

## PATCH /api/v1/listings/{id}/crm/status

Update (or clear) the CRM pipeline status for a listing.

**Path param**: `id` — listing UUID

**Request body**:
```json
{
  "status": "favorite"
}
```

**Valid status values**: `"favorite"`, `"contacted"`, `"visited"`, `"offer"`, `"discard"`, `null`  
Setting `null` clears the status.

**Response 200**:
```json
{
  "listing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "favorite",
  "notes": "...",
  "updated_at": "2026-04-17T12:35:00Z"
}
```

---

## PATCH /api/v1/listings/{id}/crm/notes

Update (or clear) the private notes for a listing.

**Path param**: `id` — listing UUID

**Request body**:
```json
{
  "notes": "Good location, close to metro. Follow up next week."
}
```

**Validation**: `notes` max 5000 characters. Empty string `""` clears the notes.

**Response 200**:
```json
{
  "listing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "favorite",
  "notes": "Good location, close to metro. Follow up next week.",
  "updated_at": "2026-04-17T12:36:00Z"
}
```

---

## Error Responses (all endpoints)

| Status | Meaning |
|--------|---------|
| 400 | Invalid request body or invalid status value |
| 401 | Missing or invalid JWT |
| 404 | Listing not found |
| 422 | Validation error (e.g., notes too long) |
| 500 | Internal server error |

---

## Database Schema (Go API Gateway)

New table: `user_crm_entries`

```sql
CREATE TABLE user_crm_entries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id  UUID NOT NULL,
    status      TEXT CHECK (status IN ('favorite', 'contacted', 'visited', 'offer', 'discard')),
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, listing_id)
);
CREATE INDEX user_crm_entries_user_id_idx ON user_crm_entries(user_id);
CREATE INDEX user_crm_entries_listing_id_idx ON user_crm_entries(listing_id);
```
