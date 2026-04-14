# Feature: API Gateway Skeleton & Authentication

## /specify prompt

```
Build the Go API Gateway service with authentication, rate limiting, and core middleware.

## What
A Go HTTP service that serves as the single public entry point for all REST API calls:

1. HTTP server with chi router, graceful shutdown, health/readiness endpoints
2. PostgreSQL connection pool (pgx) with read/write splitting (primary for writes, replica for reads)
3. Redis client for sessions, rate limits, and caching
4. JWT authentication: register (email+password), login, refresh, logout. Access tokens (15min HS256), refresh tokens (7d, stored in Redis). Passwords hashed with bcrypt (12 rounds).
5. Google OAuth2 login flow (redirect + callback). Creates or links user account.
6. Rate limiting middleware: token-bucket per user via Redis. Limits by subscription tier: Free 30/min, Basic 120/min, Pro 300/min, Global 600/min, API 1200/min. Returns 429 with Retry-After header.
7. CORS middleware with configurable allowed origins.
8. Request logging middleware (structured JSON with request_id, user_id, method, path, status, duration).
9. Prometheus metrics: http_requests_total, http_request_duration_seconds, active_connections.

## Why
All external traffic enters through this gateway. It handles cross-cutting concerns (auth, rate limiting, logging, metrics) so internal services don't need to.

## Acceptance Criteria
- Service starts on port 8080, /healthz returns 200, /readyz checks DB + Redis + NATS
- Full auth flow: register → login → get tokens → access protected endpoint → refresh → logout
- Invalid/expired JWT returns 401. Missing JWT on protected route returns 401.
- Google OAuth2 flow completes end-to-end
- Rate limit triggers at threshold. 429 response includes correct Retry-After.
- All requests logged as structured JSON with correlation ID
- Prometheus metrics exposed at /metrics
- Dockerfile builds. Image < 20MB. Helm deployment works in K8s.
```
