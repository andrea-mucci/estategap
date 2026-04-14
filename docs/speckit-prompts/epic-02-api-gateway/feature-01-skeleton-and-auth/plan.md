# Feature: API Gateway Skeleton & Authentication

## /plan prompt

```
Implement the API Gateway with these technical decisions:

## Stack
- Go 1.23, net/http + github.com/go-chi/chi/v5
- github.com/jackc/pgx/v5/pgxpool for PostgreSQL
- github.com/redis/go-redis/v9 for Redis
- github.com/golang-jwt/jwt/v5 for JWT
- golang.org/x/oauth2 for Google OAuth2
- golang.org/x/crypto/bcrypt for password hashing
- github.com/prometheus/client_golang for metrics

## Project Structure
services/api-gateway/
├── cmd/main.go              (entry point, wire dependencies, start server)
├── internal/
│   ├── config/config.go     (viper, env vars: DB_URL, REDIS_URL, JWT_SECRET, GOOGLE_CLIENT_ID...)
│   ├── handler/
│   │   ├── auth.go          (register, login, refresh, logout, google_oauth)
│   │   ├── health.go        (healthz, readyz)
│   │   ├── listings.go      (CRUD + search)
│   │   ├── zones.go         (list, detail, analytics, compare)
│   │   ├── alerts.go        (rules CRUD, history)
│   │   └── subscriptions.go (Stripe checkout, webhooks)
│   ├── middleware/
│   │   ├── auth.go          (JWT extraction + validation)
│   │   ├── ratelimit.go     (Redis token bucket)
│   │   ├── cors.go          
│   │   ├── logging.go       (structured request logging)
│   │   └── metrics.go       (Prometheus HTTP metrics)
│   ├── repository/          (data access layer, raw pgx queries)
│   │   ├── listings.go
│   │   ├── users.go
│   │   ├── zones.go
│   │   └── alerts.go
│   └── grpc/                (gRPC clients to internal services)
│       ├── ml_client.go
│       └── chat_client.go
├── Dockerfile
└── go.mod

## Auth Design
- Access token payload: {user_id, email, tier, iat, exp}
- Refresh token: random UUID stored in Redis with TTL 7d, key = "refresh:{token}" → user_id
- Logout: delete refresh token from Redis + add access token to blacklist (Redis SET with TTL = remaining token life)
- Google OAuth: state parameter stored in Redis (TTL 10min) to prevent CSRF

## Rate Limiting
- Redis key: "ratelimit:{user_id}" with TTL = 60s
- INCR on each request. If > limit for tier → 429
- Sliding window counter pattern for accuracy
```
