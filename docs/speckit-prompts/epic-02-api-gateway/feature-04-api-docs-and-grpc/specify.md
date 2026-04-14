# Feature: API Documentation & gRPC Clients

## /specify prompt

```
Add OpenAPI documentation and gRPC client connections to the API Gateway.

## What
1. OpenAPI 3.1 specification covering all REST endpoints with request/response schemas, auth requirements, and example values. Served as interactive Swagger UI at GET /api/docs.
2. gRPC client connections from api-gateway to internal services: ml-scorer (for on-demand valuation endpoint GET /api/v1/model/estimate) and ai-chat-service (for conversation management). Connection pooling, 5s timeout, circuit breaker (open after 5 consecutive failures, half-open after 30s).
3. Alert rules CRUD endpoints: GET/POST/PUT/DELETE /api/v1/alerts/rules, GET /api/v1/alerts/history with pagination and delivery status tracking. Enforce max rules per subscription tier (free=0, basic=3, pro/global/api=unlimited).

## Acceptance Criteria
- Swagger UI at /api/docs is accessible and interactive ("Try it out" works with JWT)
- All endpoints documented with schemas, auth, and examples
- gRPC calls to ml-scorer and ai-chat succeed in K8s
- Circuit breaker opens on ml-scorer failure, returns 503 to client, auto-recovers
- Alert rules CRUD with tier enforcement passes all tests
```
