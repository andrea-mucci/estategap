# Contract: REST API

**Feature**: `021-ai-chat-search-ui`  
**Counterparty**: `006-api-gateway` (Go API Gateway)  
**Date**: 2026-04-17

All endpoints require `Authorization: Bearer <jwt>` except where noted.

---

## Chat Sessions

### `GET /api/chat/sessions`

List recent chat sessions for the sidebar.

**Query params**:
- `limit` (optional, default 20): max sessions to return
- `cursor` (optional): pagination cursor

**Response 200**:
```json
{
  "sessions": [
    {
      "sessionId": "uuid",
      "snippetText": "I'm looking for a 3-bedroom...",
      "updatedAt": "2026-04-17T10:23:00Z",
      "status": "confirmed"
    }
  ],
  "nextCursor": "string | null"
}
```

---

## Listings Search

### `GET /api/listings/search`

Paginated property listings matching confirmed criteria.

**Query params** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `city` | string | City name |
| `country` | string | ISO 3166-1 alpha-2 |
| `minPrice` | number | Minimum price EUR |
| `maxPrice` | number | Maximum price EUR |
| `bedrooms` | number | Minimum bedrooms |
| `propertyType` | string | residential / commercial / land |
| `sortBy` | string | `price_asc`, `price_desc`, `deal_score_desc`, `date_desc` |
| `cursor` | string | Pagination cursor |
| `limit` | number | Items per page (default 20, max 50) |

**Response 200**:
```json
{
  "items": [
    {
      "listingId": "uuid",
      "title": "Spacious apartment in Eixample",
      "price": 480000,
      "currency": "EUR",
      "dealScore": 82,
      "photos": ["https://cdn.estategap.com/..."],
      "bedrooms": 3,
      "areaSqm": 95,
      "location": "Eixample, Barcelona",
      "latitude": 41.3917,
      "longitude": 2.1650
    }
  ],
  "nextCursor": "string | null",
  "total": 347
}
```

**Response 400**: Invalid query params  
**Response 401**: Unauthenticated (redirect to login for anonymous users)
