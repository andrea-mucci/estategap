# Quickstart: OpenAPI, gRPC Clients & Alert Rules

**Branch**: `009-openapi-grpc-alerts` | **Date**: 2026-04-17

---

## What This Feature Adds

| Component | What changes |
|-----------|-------------|
| Swagger UI | New route at `/api/docs`; spec at `/api/openapi.json` |
| gRPC clients | Enhanced `ml_client.go` + `chat_client.go` with circuit breaker, retry, timeout |
| Alert rules | New `alert_rules` + `alert_history` tables; new CRUD endpoints |
| ML estimate | New `GET /api/v1/model/estimate` proxying to ml-scorer gRPC |
| Frontend types | `openapi-typescript` generates `frontend/src/types/api.ts` from the spec |

---

## Local Development Setup

### 1. Database migration

```bash
# From project root
cd services/pipeline  # or wherever Alembic migrations live
uv run alembic upgrade head
```

The migration creates `alert_rules` and `alert_history` tables. See `research.md` for DDL.

### 2. Environment variables (add to `.env`)

```env
# gRPC targets (K8s DNS in production; localhost in dev with port-forward)
GRPC_ML_SCORER_ADDR=localhost:50051
GRPC_AI_CHAT_ADDR=localhost:50052
GRPC_TIMEOUT_SECONDS=5

# Circuit breaker (optional — these are the defaults)
GRPC_CB_THRESHOLD=5
GRPC_CB_WINDOW_SECONDS=30
GRPC_CB_COOLDOWN_SECONDS=30
```

### 3. Port-forward gRPC services (for local testing)

```bash
# Terminal 1 — ml-scorer
kubectl port-forward -n estategap-intelligence svc/ml-scorer 50051:50051

# Terminal 2 — ai-chat-service
kubectl port-forward -n estategap-intelligence svc/ai-chat-service 50052:50051
```

### 4. Run the API Gateway

```bash
cd services/api-gateway
go run ./cmd/api-gateway/main.go
```

### 5. Verify Swagger UI

Open `http://localhost:8080/api/docs` in a browser. Click "Authorize" and paste a JWT from `POST /api/v1/auth/login`.

### 6. Generate TypeScript types

```bash
cd frontend
npx openapi-typescript ../services/api-gateway/openapi.yaml -o src/types/api.ts
```

---

## Testing Alert Rules

```bash
# Login to get a JWT
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  | jq -r '.access_token')

# Create an alert rule (Pro tier required)
curl -X POST http://localhost:8080/api/v1/alerts/rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Berlin Apartments Under 500k",
    "zone_ids": ["<valid-zone-uuid>"],
    "category": "residential",
    "filter": {"price_eur": {"lte": 500000}, "bedrooms": {"gte": 3}},
    "channels": [{"type": "email"}]
  }'

# List rules
curl http://localhost:8080/api/v1/alerts/rules \
  -H "Authorization: Bearer $TOKEN"

# View delivery history
curl "http://localhost:8080/api/v1/alerts/history?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Testing the ML Estimate Endpoint

```bash
curl "http://localhost:8080/api/v1/model/estimate?listing_id=<uuid>" \
  -H "Authorization: Bearer $TOKEN"
```

### Testing circuit breaker

```bash
# Bring down the ml-scorer port-forward (Ctrl+C on terminal 1)
# Then call the estimate endpoint 5 times to open the breaker
for i in {1..6}; do
  curl -s "http://localhost:8080/api/v1/model/estimate?listing_id=<uuid>" \
    -H "Authorization: Bearer $TOKEN" | jq .
done
# 6th call should return 503 immediately (circuit open)
```

---

## File Layout (after implementation)

```text
services/api-gateway/
├── openapi.yaml                          # Hand-written OpenAPI 3.1 spec (NEW)
├── internal/
│   ├── docs/
│   │   └── swagger-ui/                   # Embedded Swagger UI static assets (NEW)
│   │       ├── swagger-ui.css
│   │       ├── swagger-ui-bundle.js
│   │       └── index.html
│   ├── grpc/
│   │   ├── circuit_breaker.go            # Custom atomic circuit breaker (NEW)
│   │   ├── ml_client.go                  # Enhanced with CB + retry + timeout (UPDATED)
│   │   └── chat_client.go                # Enhanced with retry + timeout (UPDATED)
│   ├── handler/
│   │   ├── docs.go                       # Swagger UI + spec serving (NEW)
│   │   ├── ml.go                         # GET /api/v1/model/estimate (NEW)
│   │   └── alert_rules.go                # Alert rules CRUD (NEW)
│   └── repository/
│       └── alert_rules.go                # DB queries for alert_rules + alert_history (NEW)

frontend/
└── src/types/api.ts                      # Generated TypeScript types (NEW, generated)

specs/009-openapi-grpc-alerts/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── openapi-new-endpoints.yaml
```
