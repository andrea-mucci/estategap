# estategap Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-17

## Active Technologies
- Go 1.23, Python 3.12, TypeScript 5.x / Node 22 + go.work (multi-module workspace), uv (Python pkg manager), buf (proto codegen), golangci-lint, ruff, mypy, Next.js 15 (002-monorepo-foundation)
- N/A (foundation only — no runtime data layer) (002-monorepo-foundation)
- Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend) + Go — chi, pgx, slog, viper, nats.go, grpc; Python — Pydantic v2, asyncpg, structlog, nats-py, LightGBM, Scrapy, Playwright, LiteLLM, FastAPI; Frontend — Next.js 15, Tailwind CSS 4, shadcn/ui, TanStack Query, Zustand (002-monorepo-foundation)
- YAML (Helm/Kubernetes manifests), Go 1.23 (application services), Python 3.12 (application services), TypeScript 5.x / Node 22 (frontend) + Helm 3.14+, NATS nats-io/nats chart, CloudNativePG 0.x, Bitnami Redis 19.x, kube-prometheus-stack 58.x, grafana/loki-stack 2.x, grafana/tempo 1.x, KEDA 2.x (for NATS-based HPA) (003-k8s-infrastructure)
- PostgreSQL 16 + PostGIS 3.4 (200Gi), Redis 7 (8Gi), MinIO (50Gi), NATS (10Gi × 3 replicas), Prometheus (50Gi), Loki (20Gi), Grafana (10Gi), Tempo (10Gi) (003-k8s-infrastructure)
- Python 3.12 + Alembic 1.13+, SQLAlchemy 2.0, asyncpg 0.29, psycopg2-binary (Alembic sync driver), GeoAlchemy2 0.14 (PostGIS type support) (004-database-schema)
- PostgreSQL 16 + PostGIS 3.4, Redis 7 (out of scope for this feature) (004-database-schema)
- Python 3.12 (Pydantic v2), Go 1.23 (005-shared-data-models)
- PostgreSQL 16 + PostGIS 3.4 (models mirror existing schema; no migrations in this feature) (005-shared-data-models)
- Go 1.23 + chi v5 (router), pgx/v5/pgxpool (PostgreSQL), redis/go-redis v9 (Redis), golang-jwt/jwt v5 (JWT), golang.org/x/oauth2 (Google OAuth2), golang.org/x/crypto/bcrypt (password hashing), prometheus/client_golang (metrics), spf13/viper (config), nats.go (NATS health check) (006-api-gateway)
- PostgreSQL 16 (pgx, read/write split) + Redis 7 (sessions, rate limits, blacklist, OAuth state) (006-api-gateway)
- Go 1.23 + chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, shopspring/decimal v1.4.0 (007-listing-zone-endpoints)
- PostgreSQL 16 + PostGIS 3.4 (read replica pool); Redis 7 (caching) (007-listing-zone-endpoints)
- Go 1.23 + chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, stripe-go/v81 (new), viper v1.19.0, slog (stdlib) (008-stripe-subscriptions)
- PostgreSQL 16 (new `subscriptions` table; `users` table updated); Redis 7 (idempotency keys, downgrade sorted set) (008-stripe-subscriptions)
- Go 1.23 + chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, google.golang.org/grpc (existing), gopkg.in/yaml.v3 (for YAML→JSON conversion), embed (stdlib) (009-openapi-grpc-alerts)
- PostgreSQL 16 + PostGIS 3.4 (new tables: alert_rules, alert_history); Redis 7 (existing; not used by this feature directly) (009-openapi-grpc-alerts)
- Python 3.12 + nats-py, httpx, parsel, playwright, playwright-stealth, grpcio, redis, prometheus_client, pydantic-settings, structlog, uv (011-spider-worker-framework)
- Redis 7 (seen listing IDs, quarantine records) — no PostgreSQL writes in this service (011-spider-worker-framework)
- Python 3.12 + nats-py (JetStream consumer), asyncpg (batch upsert), pydantic v2 (012-normalize-dedup-pipeline)
- PostgreSQL 16 + PostGIS 3.4 (`listings` partitioned table + new `quarantine` table + (012-normalize-dedup-pipeline)
- Python 3.12 + nats-py 2.6+, asyncpg 0.29+, httpx 0.27+, lxml 5.x (GML parsing), shapely 2.x (WKT conversion), pyosmium 3.7+ (OSM PBF loading), cachetools 5.x (Overpass TTL cache), pydantic-settings 2.2+, pydantic v2, structlog 24.x, prometheus-client 0.20+, estategap-common (shared models) (013-enrichment-change-detection)
- PostgreSQL 16 + PostGIS 3.4 (`listings` partitioned table + new `pois` table); NATS JetStream (existing streams) (013-enrichment-change-detection)
- Python 3.12 + LightGBM 4.3+, scikit-learn 1.5+, Optuna 3.x, skl2onnx 1.17+, onnxmltools 1.12+, onnxruntime 1.18+ (already present), MLflow 2.x, asyncpg 0.29+, nats-py 2.6+, structlog 24.x, pydantic-settings 2.2+, prometheus-client 0.20+, pandas 2.x, joblib, estategap-common (014-ml-training-pipeline)
- PostgreSQL 16 + PostGIS 3.4 (`listings`, `model_versions`, `zones`); MinIO (ONNX artefacts + joblib dumps) (014-ml-training-pipeline)
- Python 3.12 + onnxruntime 1.18+, shap 0.45+, scikit-learn 1.5+, lightgbm 4.3+, grpcio 1.63+, grpcio-tools 1.63+, nats-py 2.6+, asyncpg 0.29+, boto3 1.34+, pydantic-settings 2.2+, structlog 24.x, prometheus-client 0.20+, estategap-common (015-ml-inference-scoring)
- PostgreSQL 16 + PostGIS 3.4 (`listings` table — write scoring columns); MinIO (ONNX + joblib + LGB artefacts read-only) (015-ml-inference-scoring)
- Go 1.23 + chi v5, pgx/v5, go-redis v9, nats.go v1.37, shopspring/decimal, prometheus/client_golang, viper, golang.org/x/sync (016-alert-engine)
- PostgreSQL 16 + PostGIS 3.4 (read: alert_rules, zones, listings; write: alert_history); Redis 7 (dedup SETs + digest ZSETs) (016-alert-engine)
- Go 1.23 + nats.go v1.37, go-chi/chi v5, pgx/v5, go-redis/v9, aws-sdk-go-v2/ses, go-telegram-bot-api v5, twilio-go, firebase-admin-go v4, prometheus/client_golang (017-notification-dispatcher)
- PostgreSQL 16 (`users`, `alert_history`, `alert_rules`); Redis 7 (webhook retry counters) (017-notification-dispatcher)

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
- 017-notification-dispatcher: Added Go 1.23 + nats.go v1.37, go-chi/chi v5, pgx/v5, go-redis/v9, aws-sdk-go-v2/ses, go-telegram-bot-api v5, twilio-go, firebase-admin-go v4, prometheus/client_golang
- 016-alert-engine: Added Go 1.23 + chi v5 (health HTTP), pgx/v5, go-redis v9, nats.go v1.37 (JetStream pull consumers), google/uuid, shopspring/decimal, prometheus/client_golang, spf13/viper, golang.org/x/sync (errgroup); in-memory rule cache, Redis dedup SETs, Redis digest ZSETs, PostGIS zone intersection
- 015-ml-inference-scoring: Added Python 3.12 + onnxruntime 1.18+, shap 0.45+, scikit-learn 1.5+, lightgbm 4.3+, grpcio 1.63+, grpcio-tools 1.63+, nats-py 2.6+, asyncpg 0.29+, boto3 1.34+, pydantic-settings 2.2+, structlog 24.x, prometheus-client 0.20+, estategap-common


<!-- MANUAL ADDITIONS START -->
## Kubernetes / Helm

Add the chart repositories before resolving dependencies:
`helm repo add nats https://nats-io.github.io/k8s/helm/charts`
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
