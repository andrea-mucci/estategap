# Quickstart: API Gateway

**Branch**: `006-api-gateway` | **Date**: 2026-04-17

## Prerequisites

- Go 1.23+
- Docker + Docker Compose (for local dependencies)
- PostgreSQL 16 + Redis 7 running locally (or via the stack below)

## 1. Start local dependencies

```bash
# From repo root — start Postgres, Redis, NATS
docker compose up -d postgres redis nats
```

Or if using the existing K8s dev cluster, port-forward:

```bash
kubectl port-forward svc/postgres-primary 5432:5432 -n estategap-system &
kubectl port-forward svc/redis-master 6379:6379 -n estategap-system &
kubectl port-forward svc/nats 4222:4222 -n estategap-system &
```

## 2. Configure environment

```bash
cat > .env <<'EOF'
DB_PRIMARY_URL=postgres://estategap:estategap@localhost:5432/estategap?sslmode=disable
DB_REPLICA_URL=postgres://estategap:estategap@localhost:5432/estategap?sslmode=disable
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=dev-secret-must-be-at-least-32-bytes-long
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URL=http://localhost:8080/v1/auth/google/callback
ALLOWED_ORIGINS=http://localhost:3000
PORT=8080
NATS_URL=nats://localhost:4222
EOF
```

## 3. Run the service

```bash
# Load env and run
set -a && source .env && set +a
go run ./cmd/main.go
```

Service is ready when you see:

```
{"level":"INFO","msg":"server started","addr":":8080"}
```

## 4. Smoke test

```bash
# Liveness
curl -s http://localhost:8080/healthz | jq .
# → {"status":"ok"}

# Readiness
curl -s http://localhost:8080/readyz | jq .
# → {"status":"ok","checks":{"postgres":"ok","redis":"ok","nats":"ok"}}

# Register
curl -s -X POST http://localhost:8080/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"securepassword123"}' | jq .
# → {"access_token":"...","refresh_token":"...","expires_in":900,"user":{...}}

# Use access token
ACCESS_TOKEN="<token from above>"
curl -s http://localhost:8080/v1/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .

# Metrics
curl -s http://localhost:8080/metrics | grep http_requests_total
```

## 5. Run tests

```bash
cd services/api-gateway

# Unit tests
go test ./...

# Integration tests (requires Docker for testcontainers)
go test -tags integration ./...

# Lint
golangci-lint run ./...
```

## 6. Build Docker image

```bash
# From repo root
docker build -f services/api-gateway/Dockerfile -t api-gateway:local .
docker images api-gateway:local  # Verify < 20 MB

# Run container
docker run --rm -p 8080:8080 \
  -e DB_PRIMARY_URL="..." \
  -e DB_REPLICA_URL="..." \
  -e REDIS_URL="..." \
  -e JWT_SECRET="..." \
  api-gateway:local
```

## 7. Deploy to Kubernetes (staging)

```bash
# From repo root
helm upgrade --install estategap helm/estategap \
  --namespace estategap-system \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  --set services.api-gateway.image.tag=local \
  --wait --timeout 5m

kubectl rollout status deployment/api-gateway -n estategap-gateway
```

## Key URLs (local)

| URL | Description |
|-----|-------------|
| `http://localhost:8080/healthz` | Liveness probe |
| `http://localhost:8080/readyz` | Readiness probe |
| `http://localhost:8080/metrics` | Prometheus metrics |
| `http://localhost:8080/v1/auth/register` | Register |
| `http://localhost:8080/v1/auth/login` | Login |
| `http://localhost:8080/v1/auth/google` | Google OAuth2 initiation |

## Troubleshooting

**`dial tcp: connection refused` on startup**: Dependencies not ready. Check `docker compose ps` or port-forward status.

**`failed to connect to Redis`**: Verify `REDIS_URL` format is `redis://host:port/db`.

**`JWT_SECRET too short`**: Secret must be at least 32 bytes. Use `openssl rand -hex 32` to generate one.

**Google OAuth returns `invalid state`**: Ensure `GOOGLE_REDIRECT_URL` matches the authorized redirect URI in the Google Cloud Console.

**Image larger than 20 MB**: Ensure the Dockerfile uses a multi-stage build with `FROM scratch` (or distroless) as the final stage and `CGO_ENABLED=0`.
