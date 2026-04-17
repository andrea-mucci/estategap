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
- 005-shared-data-models: Added Python 3.12 (Pydantic v2), Go 1.23
- 004-database-schema: Added Python 3.12 + Alembic 1.13+, SQLAlchemy 2.0, asyncpg 0.29, psycopg2-binary (Alembic sync driver), GeoAlchemy2 0.14 (PostGIS type support)
- 003-k8s-infrastructure: Added YAML (Helm/Kubernetes manifests), Go 1.23 (application services), Python 3.12 (application services), TypeScript 5.x / Node 22 (frontend) + Helm 3.14+, NATS nats-io/nats chart, CloudNativePG 0.x, Bitnami Redis 19.x, kube-prometheus-stack 58.x, grafana/loki-stack 2.x, grafana/tempo 1.x, KEDA 2.x (for NATS-based HPA)


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
