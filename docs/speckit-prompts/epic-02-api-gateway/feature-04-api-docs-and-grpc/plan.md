# Feature: API Documentation & gRPC Clients

## /plan prompt

```
Implement with these technical decisions:

## OpenAPI
- Hand-written OpenAPI 3.1 YAML file at services/api-gateway/openapi.yaml
- Serve via swaggo/swag or embed Swagger UI static files and serve spec at /api/openapi.json
- Document: all endpoints, JWT Bearer auth scheme, request bodies (JSON), response schemas, error formats, pagination model
- Generate TypeScript types from OpenAPI spec for frontend (using openapi-typescript)

## gRPC Clients
- Create grpc/ package in api-gateway with client wrappers
- Use grpc.WithDefaultServiceConfig for retry policy: max 3 retries on UNAVAILABLE
- Circuit breaker: custom implementation using atomic counters. States: closed (normal), open (all calls fail fast with 503), half-open (allow 1 probe call). Threshold: 5 failures in 30s window.
- Connection: use K8s service DNS (e.g., ml-scorer.estategap-intelligence.svc.cluster.local:50051)
- Timeout: 5s per call, configurable via env var

## Alert Rules
- JSONB filter schema validated server-side against allowed fields per property_category
- Zone IDs validated against zones table (must exist and be active)
- Max rules check: COUNT(*) WHERE user_id = ? AND is_active = true
```
