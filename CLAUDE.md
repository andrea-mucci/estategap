# estategap Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-18

## Active Technologies
- Go 1.23, Python 3.12, TypeScript 5.x / Node 22 + go.work (multi-module workspace), uv (Python pkg manager), buf (proto codegen), golangci-lint, ruff, mypy, Next.js 15 (002-monorepo-foundation)
- N/A (foundation only — no runtime data layer) (002-monorepo-foundation)
- Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend) + Go — chi, pgx, slog, viper, github.com/segmentio/kafka-go, grpc; Python — Pydantic v2, asyncpg, structlog, aiokafka, LightGBM, Scrapy, Playwright, LiteLLM, FastAPI; Frontend — Next.js 15, Tailwind CSS 4, shadcn/ui, TanStack Query, Zustand (002-monorepo-foundation)
- YAML (Helm/Kubernetes manifests), Go 1.23 (application services), Python 3.12 (application services), TypeScript 5.x / Node 22 (frontend) + Helm 3.14+, CloudNativePG 0.x, Bitnami Redis 19.x, kube-prometheus-stack 58.x, grafana/loki-stack 2.x, grafana/tempo 1.x, KEDA 2.x (003-k8s-infrastructure)
- PostgreSQL 16 + PostGIS 3.4 (200Gi), Redis 7 (8Gi), MinIO (50Gi), Kafka (existing cluster), Prometheus (50Gi), Loki (20Gi), Grafana (10Gi), Tempo (10Gi) (003-k8s-infrastructure)
- Python 3.12 + Alembic 1.13+, SQLAlchemy 2.0, asyncpg 0.29, psycopg2-binary (Alembic sync driver), GeoAlchemy2 0.14 (PostGIS type support) (004-database-schema)
- PostgreSQL 16 + PostGIS 3.4, Redis 7 (out of scope for this feature) (004-database-schema)
- Python 3.12 (Pydantic v2), Go 1.23 (005-shared-data-models)
- PostgreSQL 16 + PostGIS 3.4 (models mirror existing schema; no migrations in this feature) (005-shared-data-models)
- Go 1.23 + chi v5 (router), pgx/v5/pgxpool (PostgreSQL), redis/go-redis v9 (Redis), golang-jwt/jwt v5 (JWT), golang.org/x/oauth2 (Google OAuth2), golang.org/x/crypto/bcrypt (password hashing), prometheus/client_golang (metrics), spf13/viper (config) (006-api-gateway)
- PostgreSQL 16 (pgx, read/write split) + Redis 7 (sessions, rate limits, blacklist, OAuth state) (006-api-gateway)
- Go 1.23 + chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, shopspring/decimal v1.4.0 (007-listing-zone-endpoints)
- PostgreSQL 16 + PostGIS 3.4 (read replica pool); Redis 7 (caching) (007-listing-zone-endpoints)
- Go 1.23 + chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, stripe-go/v81 (new), viper v1.19.0, slog (stdlib) (008-stripe-subscriptions)
- PostgreSQL 16 (new `subscriptions` table; `users` table updated); Redis 7 (idempotency keys, downgrade sorted set) (008-stripe-subscriptions)
- Go 1.23 + chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, google.golang.org/grpc (existing), gopkg.in/yaml.v3 (for YAML→JSON conversion), embed (stdlib) (009-openapi-grpc-alerts)
- PostgreSQL 16 + PostGIS 3.4 (new tables: alert_rules, alert_history); Redis 7 (existing; not used by this feature directly) (009-openapi-grpc-alerts)
- Python 3.12 + aiokafka, httpx, parsel, playwright, playwright-stealth, grpcio, redis, prometheus_client, pydantic-settings, structlog, uv (011-spider-worker-framework)
- Redis 7 (seen listing IDs, quarantine records) — no PostgreSQL writes in this service (011-spider-worker-framework)
- Python 3.12 + aiokafka, asyncpg (batch upsert), pydantic v2 (012-normalize-dedup-pipeline)
- PostgreSQL 16 + PostGIS 3.4 (`listings` partitioned table + new `quarantine` table + (012-normalize-dedup-pipeline)
- Python 3.12 + aiokafka, asyncpg 0.29+, httpx 0.27+, lxml 5.x (GML parsing), shapely 2.x (WKT conversion), pyosmium 3.7+ (OSM PBF loading), cachetools 5.x (Overpass TTL cache), pydantic-settings 2.2+, pydantic v2, structlog 24.x, prometheus-client 0.20+, estategap-common (shared models) (013-enrichment-change-detection)
- PostgreSQL 16 + PostGIS 3.4 (`listings` partitioned table + new `pois` table); Kafka (existing cluster) (013-enrichment-change-detection)
- Python 3.12 + LightGBM 4.3+, scikit-learn 1.5+, Optuna 3.x, skl2onnx 1.17+, onnxmltools 1.12+, onnxruntime 1.18+ (already present), MLflow 2.x, asyncpg 0.29+, aiokafka, structlog 24.x, pydantic-settings 2.2+, prometheus-client 0.20+, pandas 2.x, joblib, estategap-common (014-ml-training-pipeline)
- PostgreSQL 16 + PostGIS 3.4 (`listings`, `model_versions`, `zones`); MinIO (ONNX artefacts + joblib dumps) (014-ml-training-pipeline)
- Python 3.12 + onnxruntime 1.18+, shap 0.45+, scikit-learn 1.5+, lightgbm 4.3+, grpcio 1.63+, grpcio-tools 1.63+, aiokafka, asyncpg 0.29+, boto3 1.34+, pydantic-settings 2.2+, structlog 24.x, prometheus-client 0.20+, estategap-common (015-ml-inference-scoring)
- PostgreSQL 16 + PostGIS 3.4 (`listings` table — write scoring columns); MinIO (ONNX + joblib + LGB artefacts read-only) (015-ml-inference-scoring)
- Go 1.23 + chi v5, pgx/v5, go-redis v9, github.com/segmentio/kafka-go, shopspring/decimal, prometheus/client_golang, viper, golang.org/x/sync (016-alert-engine)
- PostgreSQL 16 + PostGIS 3.4 (read: alert_rules, zones, listings; write: alert_history); Redis 7 (dedup SETs + digest ZSETs) (016-alert-engine)
- Go 1.23 + github.com/segmentio/kafka-go, go-chi/chi v5, pgx/v5, go-redis/v9, aws-sdk-go-v2/ses, go-telegram-bot-api v5, twilio-go, firebase-admin-go v4, prometheus/client_golang (017-notification-dispatcher)
- PostgreSQL 16 (`users`, `alert_history`, `alert_rules`); Redis 7 (webhook retry counters) (017-notification-dispatcher)
- Python 3.12 + grpcio 1.63+, grpcio-tools 1.63+, anthropic (AsyncAnthropic), openai (AsyncOpenAI), litellm 1.35+, redis[asyncio] 5.x, asyncpg 0.29+, pydantic-settings 2.2+, pydantic v2, jinja2 3.x, structlog 24.x, prometheus-client 0.20+, estategap-common (path dep) (018-ai-chat-service)
- Redis 7 (conversation state + message history — primary); PostgreSQL 16 + PostGIS 3.4 (visual_references table — read-only at runtime) (018-ai-chat-service)
- Go 1.23 + gorilla/websocket v1.5, golang-jwt/jwt v5, github.com/segmentio/kafka-go, google.golang.org/grpc v1.64+, go-chi/chi v5, prometheus/client_golang v1.19, spf13/viper v1.19, redis/go-redis v9, slog (stdlib), `libs/pkg` (go.work path dep) (019-ws-chat-realtime)
- Redis 7 (JWT blacklist check — read-only); no PostgreSQL access (019-ws-chat-realtime)
- TypeScript 5.5 (strict mode), Node.js 22 + Next.js 15 (App Router, RSC), Tailwind CSS 4, shadcn/ui, next-intl, NextAuth v5, @tanstack/react-query v5, Zustand 5, openapi-typescript (already in devDeps) (020-nextjs-frontend-foundation)
- No direct DB access — state via TanStack Query cache + Zustand; JWT stored in NextAuth session (020-nextjs-frontend-foundation)
- TypeScript 5.5 (strict mode) / Node.js 22 + Next.js 15 (App Router), Tailwind CSS 4, shadcn/ui, Zustand 5, TanStack Query v5, next-intl, react-markdown + remark-gfm, @tailwindcss/typography, MapLibre GL JS (021-ai-chat-search-ui)
- sessionStorage (Zustand persist middleware) — no direct DB access (021-ai-chat-search-ui)
- TypeScript 5.5 (strict) / Node.js 22 (frontend); Go 1.23 (API gateway) (022-dashboard-analytics-map)
- PostgreSQL 16 + PostGIS 3.4 (listings.location POINT, zones.geometry MULTIPOLYGON); Redis 7 (dashboard summary cache 60s, zone geometry cache 5min) (022-dashboard-analytics-map)
- TypeScript 5.5 (strict mode) / Node.js 22 + Next.js 15 (App Router, RSC), TanStack Query v5, nuqs (new — URL state), shadcn/ui, Recharts 2.x, MapLibre GL JS 4.x, yet-another-react-lightbox (new), Zustand 5, react-hook-form + Zod, next-intl (023-listing-search-detail)
- No direct DB access — TanStack Query cache (server state), Zustand (UI state), localStorage (saved searches fallback) (023-listing-search-detail)
- TypeScript 5.5 strict / Node.js 22 (frontend); Go 1.23 (API Gateway) (024-zones-portfolio-admin)
- PostgreSQL 16 + PostGIS 3.4 (new `portfolio_properties` table; zone analytics query extended); Redis 7 (zone analytics cache extended; exchange rate cache 24h) (024-zones-portfolio-admin)
- Python 3.12 (spiders + pipeline enrichers) + aiokafka, asyncpg 0.29+, httpx 0.27+, playwright 1.43+ (SeLoger, LeBonCoin), beautifulsoup4 4.12+ (Rightmove), parsel 1.9+ (existing), rapidfuzz 3.6+ (UK address matching), geopandas 0.14+ (zone import), shapely 2.x (existing), pydantic-settings 2.2+, structlog 24.x, pytest-httpx 0.30+ (spider tests) (025-eu-portals-enrichment)
- PostgreSQL 16 + PostGIS 3.4 (3 new tables + listings column extensions); Redis 7 (existing seen-IDs dedup) (025-eu-portals-enrichment)
- Python 3.12 (spiders + ML trainer), Go 1.23 (no changes) + Playwright 1.43+ with playwright-stealth (Zillow), httpx 0.27+ (Redfin/Realtor.com), LightGBM 4.3+, scikit-learn 1.5+, onnxruntime 1.18+, MLflow 2.x, geopandas 0.14+ (TIGER/Line import), aiokafka, asyncpg 0.29+ (026-us-spiders-country-ml)
- PostgreSQL 16 + PostGIS 3.4 (listings + model_versions extensions); MinIO (ONNX + LGB .txt artefacts); Kafka (existing cluster) (026-us-spiders-country-ml)
- TypeScript 5.5 / Node.js 22 (frontend); Go 1.23 (API Gateway); Python 3.12 (Alembic migration) (027-landing-onboarding)
- PostgreSQL 16 (users table extension); no Redis usage for this feature (027-landing-onboarding)
- Go 1.23 (API Gateway), TypeScript 5.5 / Next.js 15 (frontend), Python 3.12 (Alembic migration for anonymization columns if needed) + chi v5.2.1, go-redis v9, shadcn/ui Dialog, next-intl, K6 v0.51+, Bitnami sealed-secrets controller, golangci-lint, govulncheck, pip-audit, ruff, mypy (028-production-hardening)
- PostgreSQL 16 + PostGIS 3.4 (users table — soft delete already present); Redis 7 (auth:attempts:{ip} rate limit counters, zone-stats / top-deals / alert-rules cache keys) (028-production-hardening)
- Bash (scripts), Python 3.12 (seed loader + conformance), YAML (kind config + helm tests), HCL (docker-bake.hcl), GNU Make + kind 0.24+, Helm 3.14+, helm-unittest plugin, kubectl 1.30+, docker buildx, pyyaml, asyncpg, boto3, redis-py (029-kind-helm-validation)
- PostgreSQL 16 + PostGIS 3.4 (seeded via asyncpg), MinIO (seeded via boto3), Redis 7 (seeded via redis-py) (029-kind-helm-validation)
- Go 1.23, Python 3.12, TypeScript 5.6 / Node 22 (030-test-coverage-infrastructure)
- PostgreSQL 16 + PostGIS 3.4, Redis 7, Kafka, MinIO (all via testcontainers) (030-test-coverage-infrastructure)
- Python 3.12 (API + WebSocket + concurrency tests), TypeScript 5.5 / Node.js 22 (Playwright browser tests) (031-e2e-test-suite)
- No direct DB writes from tests. PostgreSQL seeded via existing `tests/fixtures/load.py`; Redis flushed per-run via helper script (031-e2e-test-suite)
- Python 3.12 + pytest 8.2+, pytest-asyncio 0.23+, playwright 1.43+ (Python), asyncpg 0.29+, aiokafka, redis 5.x, websockets 12+, httpx 0.27+, kubernetes 29.0+ (032-e2e-user-journeys)
- PostgreSQL 16 (read-only verification via asyncpg), Redis 7 (notification spy reads + Redis reset), no schema changes (032-e2e-user-journeys)
- PostgreSQL 16 + PostGIS 3.4, Redis 7 (unchanged) (033-nats-to-kafka-migration)
- Go 1.23 (`libs/pkg/s3client/`), Python 3.12 (`libs/common/s3client/`), YAML (Helm) (034-s3-migration)
- Hetzner Object Storage (S3-compatible, endpoint: `https://fsn1.your-objectstorage.com`) (034-s3-migration)
- YAML (Helm 3.14+), Go templates (Helm templating) + Helm 3.14+, Bitnami Redis 19.x (kept), KEDA 2.x (kept), Prometheus operator ≥ 0.63 (external, for ServiceMonitor CRD) (035-helm-external-infra)
- Redis 7 (self-deployed, Bitnami sub-chart unchanged); external PostgreSQL 16, Hetzner S3 (035-helm-external-infra)
- YAML (Helm 3.14+), JSON Schema 2020-12, Markdown + Helm 3.14+; no new packages (036-helm-values-documentation)

- Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend) (001-monorepo-foundation)

## Project Structure

```text
src/
tests/
```

## Commands

cd src && pytest && ruff check .

## Code Style

Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend): Follow standard conventions

## Recent Changes
- 036-helm-values-documentation: Added YAML (Helm 3.14+), JSON Schema 2020-12, Markdown + Helm 3.14+; no new packages
- 035-helm-external-infra: Added YAML (Helm 3.14+), Go templates (Helm templating) + Helm 3.14+, Bitnami Redis 19.x (kept), KEDA 2.x (kept), Prometheus operator ≥ 0.63 (external, for ServiceMonitor CRD)
- 034-s3-migration: Added Go 1.23 (`libs/pkg/s3client/`), Python 3.12 (`libs/common/s3client/`), YAML (Helm)


<!-- MANUAL ADDITIONS START -->
## Kubernetes / Helm

Add the chart repositories before resolving dependencies:
`helm repo add cnpg https://cloudnative-pg.github.io/charts`
`helm repo add bitnami https://charts.bitnami.com/bitnami`
`helm repo add prometheus-community https://prometheus-community.github.io/helm-charts`
`helm repo add grafana https://grafana.github.io/helm-charts`
`helm repo add kedacore https://kedacore.github.io/charts`
`helm repo update`

Core Helm commands:
`helm dependency update helm/estategap`
`helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml`
`helm template estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml`
`helm install estategap helm/estategap --namespace estategap-system --create-namespace -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml --wait --timeout 10m`

ArgoCD bootstrap:
`helm template estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml --show-only templates/argocd-application.yaml | kubectl apply -f -`
`argocd app get estategap-staging`
<!-- MANUAL ADDITIONS END -->
