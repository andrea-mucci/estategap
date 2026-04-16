# SpecKit Constitution — EstateGap

## /constitution prompt

```
Create a constitution for a multi-country real estate deal tracking platform called EstateGap with the following immutable principles:

## Project Identity
- Name: EstateGap
- Purpose: Scrape property listings from 30+ real estate portals across Europe and the USA, detect undervalued properties using ML models, and alert users before anyone else. Monetized via premium subscriptions.
- Target users: Real estate investors, property hunters, and market analysts.

## Architecture Principles
- Polyglot backend: Go for high-throughput services (API Gateway, WebSocket server, Alert Engine, Scrape Orchestrator) and Python for data/ML/AI services (spiders, pipeline, ML scorer/trainer, AI conversational search).
- Frontend: Next.js 15 with TypeScript, App Router, shadcn/ui, Tailwind CSS 4, MapLibre GL JS for maps.
- Communication: NATS JetStream for async events between all services. gRPC with Protobuf for synchronous inter-service calls. No direct service-to-service HTTP.
- Database: PostgreSQL 16 with PostGIS 3.4. Table partitioning by country. Redis 7 for caching and sessions. MinIO for object storage.
- Deployment: Kubernetes-native. Helm charts. ArgoCD for GitOps. All services containerized.
- ML: LightGBM trained per country, exported to ONNX for inference. MLflow for experiment tracking. SHAP for explainability.
- AI: LLM-powered conversational search with provider-agnostic abstraction (Claude, GPT, open-source via LiteLLM). Streaming responses via WebSocket.

## Code Standards
- Go: stdlib net/http + chi router. pgx for PostgreSQL (no ORM). Structured logging via slog. Error handling: explicit, no panics. Lint: golangci-lint.
- Python: Pydantic v2 for all data models. asyncio + httpx for async HTTP. Scrapy + Playwright for scraping. structlog for logging. Lint: ruff + mypy (strict). Package manager: uv.
- Frontend: TypeScript strict mode. TanStack Query for server state. Zustand for client state. next-intl for i18n (10 languages). React Hook Form + Zod for forms.
- Protobuf: All inter-service contracts defined in proto/ directory. buf for linting and code generation.
- Testing: Go: table-driven tests. Python: pytest + pytest-asyncio. Frontend: Vitest + React Testing Library. Integration tests with testcontainers.

## Data Principles
- Country is a first-class entity. All data partitioned by country.
- Prices stored in original currency + EUR-normalized.
- Areas stored in source unit + m²-normalized.
- Listings follow a unified schema regardless of source portal.
- Property types: residential, commercial, industrial, land.
- All changes tracked (price history, audit trail).

## Security & Compliance
- JWT authentication (short-lived access + refresh tokens). Google OAuth2.
- GDPR compliant: data export, account deletion, consent management.
- No secrets in code. K8s Sealed Secrets.
- Rate limiting per subscription tier.
- Scraping: respect robots.txt, geo-targeted proxies, configurable throttling per portal.

## Monorepo Structure
- services/ — Go and Python microservices (one directory per service)
- frontend/ — Next.js application
- proto/ — Shared Protobuf definitions
- helm/ — Helm charts for K8s deployment
- libs/ — Shared libraries (Go pkg/, Python common/)
- docs/ — Architecture and requirements documentation
```
