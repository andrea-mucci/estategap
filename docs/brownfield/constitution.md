# SpecKit Constitution — EstateGap Brownfield Adaptation

## /constitution prompt

```
Create a constitution for a brownfield adaptation of the EstateGap multi-country real estate deal tracker platform. This project already has a working codebase built with the original architecture. We are now adapting it to run on an existing Kubernetes cluster with pre-installed infrastructure services.

## Project Identity
- Name: EstateGap (brownfield adaptation)
- Purpose: Adapt the existing EstateGap codebase to use shared cluster infrastructure instead of self-managed services. Zero functional changes — same features, different plumbing.
- Goal: Reduce operational overhead by leveraging existing Kafka, PostgreSQL, Prometheus, and Grafana already running in the target Kubernetes cluster, and replacing MinIO with Hetzner S3-compatible object storage.

## Key Constraints — EXISTING CLUSTER SERVICES (DO NOT DEPLOY)
The target Kubernetes cluster already has these services running. EstateGap MUST use them, NOT deploy its own:
- **Apache Kafka** — replaces NATS JetStream for all async event-driven communication
- **PostgreSQL** (with PostGIS extension available) — replaces CloudNativePG operator deployment
- **Prometheus** — replaces kube-prometheus-stack for metrics collection
- **Grafana** — replaces bundled Grafana for dashboards and alerting
These services are managed by the platform team and accessed via ClusterIP services in their own namespaces.

## Key Constraints — EXTERNAL SERVICES
- **Hetzner Object Storage (S3-compatible)** — replaces self-hosted MinIO for: ML model artifacts, listing photos, training data, exports, backups. Accessed via standard AWS S3 SDK with custom endpoint.

## Architecture Principles (UNCHANGED from original)
- Polyglot backend: Go for high-throughput services, Python for data/ML/AI
- Frontend: Next.js 15, TypeScript, App Router, shadcn/ui, Tailwind CSS 4, MapLibre GL JS
- gRPC with Protobuf for synchronous inter-service calls
- Kubernetes-native deployment via Helm charts and ArgoCD GitOps
- ML: LightGBM per country, ONNX Runtime inference, MLflow tracking, SHAP explainability
- AI: LLM-powered conversational search, provider-agnostic (Claude/GPT/LiteLLM)

## What Changes
| Component | Before (greenfield) | After (brownfield) |
|---|---|---|
| Message broker | NATS JetStream (self-deployed) | Kafka (existing in cluster) |
| Database | CloudNativePG (self-deployed) | PostgreSQL (existing in cluster) |
| Object storage | MinIO (self-deployed) | Hetzner S3 (external, S3-compatible) |
| Metrics | kube-prometheus-stack (self-deployed) | Prometheus (existing in cluster) |
| Dashboards | Grafana (self-deployed) | Grafana (existing in cluster) |
| Logging | Loki + Promtail (self-deployed) | Cluster logging solution (existing) |
| Redis | Self-deployed | Self-deployed (UNCHANGED — still needed) |
| MLflow | Self-deployed | Self-deployed (UNCHANGED) |

## What Does NOT Change
- All business logic, API contracts, gRPC services, frontend — IDENTICAL
- Database schema (same PostgreSQL + PostGIS, just different connection)
- ML pipeline (same LightGBM → ONNX flow, artifacts on S3 instead of MinIO)
- Alert system, AI chat, scraping — all unchanged functionally

## Code Standards (UNCHANGED)
- Go: stdlib net/http + chi router, pgx for PostgreSQL, slog logging
- Python: Pydantic v2, asyncio + httpx, Scrapy + Playwright, structlog
- Frontend: TypeScript strict, TanStack Query, Zustand, next-intl
- Protobuf: all inter-service contracts in proto/ directory
- Testing: same pyramid (unit → integration → contract → E2E → user journeys)

## Migration Strategy
- Feature-branch per migration (kafka, s3, helm-refactor, helm-docs)
- Each migration is backward-compatible during transition
- All Kafka topics mirror the old NATS stream names for consistency
- S3 bucket names match old MinIO bucket names
- Zero downtime: existing services keep running during migration

## Helm Chart Principles (CRITICAL)
- The Helm chart MUST NOT deploy: Kafka, PostgreSQL, Prometheus, Grafana, Loki
- External services configured via values.yaml with clear documentation
- Every Helm value MUST be documented in values.yaml comments AND in a dedicated HELM_VALUES.md
- Sensitive values (DB passwords, S3 keys, Kafka credentials) via Kubernetes Secrets referenced in values
- Feature flags to conditionally enable/disable optional components (MLflow, Redis, Loki)
```
