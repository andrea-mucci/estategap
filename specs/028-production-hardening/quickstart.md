# Quickstart: Production Hardening (028)

**Branch**: `028-production-hardening` | **Date**: 2026-04-17

## Prerequisites

- Go 1.23, Node 22, Python 3.12, uv installed
- Docker + kubectl + helm available
- Local Redis running on `localhost:6379`
- Local PostgreSQL 16 running with `estategap` database
- `pg_stat_statements` extension enabled on local PG

## 1. API Gateway — local dev

```bash
cd services/api-gateway

# Required env vars for new features
export ALLOWED_ORIGINS="http://localhost:3000"
export CSP_REPORT_ONLY="true"
export CSP_REPORT_URI="http://localhost:9090/csp-report"
export REDIS_URL="redis://localhost:6379"
export DATABASE_URL="postgres://estategap:estategap@localhost:5432/estategap"

go run ./cmd/...
```

### Verify CORS allowlist

```bash
# Should return Access-Control-Allow-Origin header
curl -s -I -H "Origin: http://localhost:3000" http://localhost:8080/api/v1/listings \
  | grep Access-Control

# Should return 403 for unlisted origin
curl -s -o /dev/null -w "%{http_code}" \
  -H "Origin: http://evil.example.com" http://localhost:8080/api/v1/listings
# Expected: 403
```

### Verify auth rate limiting

```bash
# Run 6 rapid POST requests to auth — 6th should return 429
for i in {1..6}; do
  echo -n "Attempt $i: "
  curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8080/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"x@x.com","password":"wrong"}'
  echo
done
# Expected: 200 or 401 for attempts 1-5, 429 for attempt 6
```

### Verify caching

```bash
# First request — cache miss
time curl -s http://localhost:8080/api/v1/zones/1/stats > /dev/null

# Second request — cache hit (should be faster)
time curl -s http://localhost:8080/api/v1/zones/1/stats > /dev/null

# Inspect Redis
redis-cli keys "cache:zone-stats:*"
```

### Verify GDPR export

```bash
# Get a valid JWT first
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -d '{"email":"test@test.com","password":"test123"}' | jq -r .access_token)

# Export
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/me/export | jq .
# Expected: JSON object with profile, alert_rules, portfolio_properties, alert_history, conversations
```

### Verify account deletion

```bash
# Delete account
curl -s -X DELETE http://localhost:8080/api/v1/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"confirm": "delete my account"}'
# Expected: 202 Accepted

# Verify soft delete in DB
psql $DATABASE_URL -c "SELECT id, email, deleted_at, anonymized_at FROM users LIMIT 1"
# Expected: deleted_at and anonymized_at are set; email is 'deleted-{uuid}@deleted.invalid'
```

## 2. Database Migration

```bash
cd services/pipeline

# Apply the new indexes and anonymized_at column
uv run alembic upgrade head

# Verify
psql $DATABASE_URL -c "\d users" | grep anonymized
psql $DATABASE_URL -c "\di" | grep ix_listings
```

## 3. Frontend — local dev

```bash
cd frontend
npm install
npm run dev
```

### Verify cookie consent

1. Open `http://localhost:3000` in a private/incognito browser window
2. The consent Dialog should appear before any analytics scripts load
3. Open DevTools → Network: verify no analytics requests before consent
4. Accept → verify `eg_consent=granted` cookie is set
5. Reload → verify Dialog does not reappear

### Verify bundle size

```bash
cd frontend
npm run build

# Check bundle sizes
npx bundlesize
# Main JS chunk should be < 200 KB gzipped

# Or use built-in Next.js analyser
ANALYZE=true npm run build
# Open .next/analyze/client.html in browser
```

### Verify dynamic imports

After `npm run build`, inspect `.next/static/chunks/`:
- `maplibre*.js` should be a separate chunk (not in `main-*.js`)
- `recharts*.js` should be a separate chunk

### Verify preconnect hints

```bash
curl -s http://localhost:3000 | grep preconnect
# Expected: <link rel="preconnect" href="https://api.estategap.com" ...>
# Expected: <link rel="preconnect" href="https://api.maptiler.com" ...>
```

## 4. CI Scanning — local verification

```bash
# Go
cd services/api-gateway
go install golang.org/x/vuln/cmd/govulncheck@latest
govulncheck ./...

# Python
cd services/pipeline
uv run pip-audit
# Expected: No known vulnerabilities found

# Node
cd frontend
npm audit --audit-level=high
# Expected: found 0 vulnerabilities
```

## 5. Helm — staging deploy

```bash
# Verify sealed-secrets controller is running
kubectl get pods -n kube-system | grep sealed-secrets

# Diff the chart changes
helm diff upgrade estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml

# Apply
helm upgrade estategap helm/estategap \
  --namespace estategap-system \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml

# Verify CronJob created
kubectl get cronjob -n estategap-system | grep gdpr
```

## 6. Load Tests — in-cluster

```bash
# Create the K6 ConfigMap with test scripts
kubectl create configmap k6-scripts \
  --from-file=tests/load/ \
  -n estategap-system

# Run the load test Job (triggers all 4 scripts sequentially)
kubectl create job load-test-$(date +%s) \
  --from=cronjob/load-test-job \
  -n estategap-system

# Watch logs
kubectl logs -f -l job-name=load-test-... -n estategap-system

# Results land in Grafana → k6 dashboard
# URL: http://grafana.estategap-system.svc/d/k6-results
```

## 7. OWASP ZAP Scan

```bash
# Run ZAP baseline scan against staging
docker run --rm -v $(pwd):/zap/wrk \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py \
  -t https://staging.estategap.com \
  -r zap-report.html \
  -I  # ignore warn, fail only on high/critical

open zap-report.html
# Expected: 0 HIGH, 0 CRITICAL findings
```
