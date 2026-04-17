<!--
Sync Impact Report
==================
Version change: 1.0.0 → 2.0.0 (brownfield adaptation)
Modified principles:
  - II. Event-Driven Communication → II. Event-Driven Communication
    (NATS JetStream replaced by Apache Kafka; rationale updated)
  - III. Country-First Data Sovereignty → III. Country-First Data
    Sovereignty (MinIO replaced by Hetzner S3; PostgreSQL/Redis
    deployment model changed to external/shared cluster)
  - VII. Kubernetes-Native Deployment → VII. Brownfield
    Kubernetes-Native Deployment (shared cluster infra model;
    Helm chart MUST NOT deploy Kafka, PostgreSQL, Prometheus,
    Grafana, Loki)
Added sections:
  - Migration Strategy (brownfield transition rules)
Removed sections: none
Templates requiring updates:
  - .specify/templates/plan-template.md — ✅ no updates needed
    (Constitution Check section is dynamic; plan structure already
    supports polyglot/web layouts)
  - .specify/templates/spec-template.md — ✅ no updates needed
    (generic feature spec structure; no constitution-specific refs)
  - .specify/templates/tasks-template.md — ✅ no updates needed
    (phase-based task structure accommodates constitution principles)
  - .specify/templates/commands/*.md — no command templates found
Follow-up TODOs: none
-->

# EstateGap Constitution

## Core Principles

### I. Polyglot Service Architecture

EstateGap MUST use a polyglot backend split by workload profile:

- **Go** for high-throughput, latency-sensitive services: API Gateway,
  WebSocket server, Alert Engine, Scrape Orchestrator.
- **Python** for data-intensive and ML/AI services: scraping spiders,
  data pipeline, ML scorer/trainer, AI conversational search.
- **Next.js 15** (TypeScript, App Router) for the frontend with
  shadcn/ui, Tailwind CSS 4, and MapLibre GL JS for maps.

Each service MUST be a standalone, independently deployable unit inside
`services/`. No service may import another service's internal packages
directly. Shared code lives in `libs/` (Go `pkg/`, Python `common/`).

**Rationale**: Go delivers the concurrency and low-latency guarantees
required for real-time alerting and high-throughput API serving. Python
provides the richest ecosystem for ML, scraping, and data processing.
Separating by workload profile avoids language misuse.

### II. Event-Driven Communication

All inter-service communication MUST follow these rules:

- **Asynchronous events**: Apache Kafka for all event-driven messaging
  between services (listing ingested, price changed, alert triggered,
  model retrained). Kafka is provided by the platform team as a shared
  cluster service — EstateGap MUST NOT deploy its own Kafka instance.
- **Topic naming**: All Kafka topic names MUST mirror the legacy NATS
  stream names for traceability and consistency during migration.
- **Synchronous calls**: gRPC with Protobuf for request/response
  patterns between services.
- **No direct HTTP**: Services MUST NOT call each other via REST/HTTP.
  The API Gateway is the sole HTTP entry point for external clients.

All inter-service contracts MUST be defined as Protobuf schemas in
`proto/` and linted/generated via `buf`.

**Rationale**: Apache Kafka provides durable, replay-capable event
streams essential for audit trails and pipeline reliability. The target
cluster already runs Kafka as a shared service — reusing it eliminates
operational overhead of managing a separate message broker. gRPC
enforces typed contracts and avoids the drift that untyped HTTP causes.
A single protocol definition source (proto/) eliminates contract
ambiguity.

### III. Country-First Data Sovereignty

Country is a first-class entity. All data MUST be partitioned and
queryable by country:

- PostgreSQL 16 with PostGIS 3.4. Tables MUST be partitioned by
  country code. The PostgreSQL instance is provided by the platform
  team as a shared cluster service — EstateGap MUST NOT deploy its
  own database. Connection details are supplied via Kubernetes Secrets.
- Prices MUST be stored in original currency AND EUR-normalized.
- Areas MUST be stored in source unit AND m²-normalized.
- All property listings MUST conform to a unified schema regardless
  of source portal.
- Supported property types: residential, commercial, industrial, land.
- All mutations MUST be tracked: price history, status changes,
  and full audit trail.
- Redis 7 for caching and session storage. Redis remains self-deployed
  by EstateGap as it is not available as a shared cluster service.
- **Hetzner Object Storage** (S3-compatible) for images, documents,
  and model artifacts. Accessed via standard AWS S3 SDK with custom
  endpoint. EstateGap MUST NOT deploy MinIO or any other self-hosted
  object storage. S3 bucket names MUST match the legacy MinIO bucket
  names for consistency.

**Rationale**: EstateGap covers 30+ portals across Europe and the USA.
Country-based partitioning enables per-market query isolation,
regulatory compliance per jurisdiction, and efficient scaling as new
countries are added. Using the platform-managed PostgreSQL and external
Hetzner S3 reduces operational burden while preserving identical schema
and data access patterns.

### IV. ML-Powered Intelligence

The ML and AI layer MUST follow these rules:

- **ML scoring**: LightGBM models trained per country, exported to
  ONNX format for inference. Models MUST be versioned and reproducible.
- **Experiment tracking**: MLflow for all training runs, hyperparameter
  searches, and model registry. MLflow remains self-deployed.
- **Model artifacts**: Stored on Hetzner S3 (replacing MinIO). The S3
  bucket structure and artifact paths MUST remain identical to the
  legacy MinIO layout.
- **Explainability**: SHAP values MUST accompany every deal score to
  provide transparent reasoning to users.
- **AI search**: LLM-powered conversational search with a
  provider-agnostic abstraction layer (Claude, GPT, open-source models
  via LiteLLM). Streaming responses delivered via WebSocket.
- No single LLM vendor lock-in. The abstraction layer MUST allow
  swapping providers without code changes to consuming services.

**Rationale**: Per-country models capture local market dynamics that a
single global model would miss. ONNX export decouples training
(Python) from inference (can run in Go or Python). SHAP
explainability builds user trust and satisfies potential regulatory
requirements for automated financial advice.

### V. Code Quality Discipline

Every language in the stack MUST enforce strict quality gates:

- **Go**: stdlib `net/http` + chi router. `pgx` for PostgreSQL (no
  ORM). Structured logging via `slog`. Explicit error handling — no
  panics. Lint: `golangci-lint`.
- **Python**: Pydantic v2 for all data models. `asyncio` + `httpx`
  for async HTTP. Scrapy + Playwright for scraping. `structlog` for
  logging. Lint: `ruff` + `mypy` (strict mode). Package manager: `uv`.
- **Frontend**: TypeScript strict mode. TanStack Query for server
  state. Zustand for client state. `next-intl` for i18n (10
  languages). React Hook Form + Zod for form validation.
- **Testing**: Go: table-driven tests. Python: `pytest` +
  `pytest-asyncio`. Frontend: Vitest + React Testing Library.
  Integration tests with testcontainers across all languages.
- **Protobuf**: `buf` for linting and code generation. Breaking
  changes to proto files MUST go through a review process.

**Rationale**: Consistent tooling per language reduces cognitive
overhead. Strict linting and type checking catch defects before review.
Table-driven and testcontainers-based testing ensures coverage is
meaningful, not ceremonial.

### VI. Security & Ethical Scraping

Security and compliance are non-negotiable:

- **Authentication**: JWT with short-lived access tokens + refresh
  tokens. Google OAuth2 as an identity provider.
- **GDPR compliance**: Data export, account deletion, and consent
  management MUST be implemented from day one.
- **Secrets management**: No secrets in code, ever. Kubernetes Sealed
  Secrets for all sensitive configuration. External service credentials
  (Kafka, PostgreSQL, Hetzner S3) MUST be injected via Kubernetes
  Secrets referenced in Helm values — never hardcoded.
- **Rate limiting**: Per subscription tier, enforced at the API
  Gateway.
- **Scraping ethics**: All spiders MUST respect `robots.txt`.
  Geo-targeted proxies MUST be used. Throttling MUST be configurable
  per portal. No aggressive scraping patterns that could harm source
  portals.

**Rationale**: EstateGap processes personal property data across
multiple EU jurisdictions — GDPR compliance is a legal requirement,
not a feature. Ethical scraping protects business continuity by
avoiding IP bans and legal action from portal operators.

### VII. Brownfield Kubernetes-Native Deployment

All deployment MUST be Kubernetes-native and MUST leverage existing
shared cluster infrastructure:

- Every service MUST be containerized with a Dockerfile.
- Helm charts in `helm/` for all deployment manifests.
- ArgoCD for GitOps-based continuous deployment.
- Infrastructure changes MUST be version-controlled and reviewed
  like application code.
- No manual cluster modifications. All state expressed declaratively.

**Shared cluster services — DO NOT DEPLOY**:

The Helm chart MUST NOT deploy any of the following. These are managed
by the platform team and accessed via ClusterIP services in their own
namespaces:

| Service | Access Method | Replaces |
|---------|--------------|----------|
| Apache Kafka | ClusterIP in platform namespace | NATS JetStream |
| PostgreSQL (PostGIS) | ClusterIP in platform namespace | CloudNativePG |
| Prometheus | ClusterIP in platform namespace | kube-prometheus-stack |
| Grafana | ClusterIP in platform namespace | Bundled Grafana |
| Cluster logging | Platform-managed | Loki + Promtail |

**External services**:

| Service | Access Method | Replaces |
|---------|--------------|----------|
| Hetzner Object Storage | S3 API with custom endpoint | MinIO |

**Self-deployed by EstateGap** (still required):

| Service | Reason |
|---------|--------|
| Redis 7 | Not available as shared cluster service |
| MLflow | Specialized ML experiment tracking |

**Helm chart rules**:

- External services MUST be configured via `values.yaml` with clear
  documentation of every value.
- Every Helm value MUST be documented in `values.yaml` comments AND
  in a dedicated `HELM_VALUES.md`.
- Sensitive values (DB passwords, S3 keys, Kafka credentials) MUST
  be supplied via Kubernetes Secrets referenced in Helm values.
- Feature flags MUST exist to conditionally enable/disable optional
  components (MLflow, Redis).

**Rationale**: The target Kubernetes cluster already provides
production-grade Kafka, PostgreSQL, Prometheus, and Grafana managed
by the platform team. Deploying duplicate instances would waste
resources, create operational confusion, and conflict with cluster
policies. Hetzner S3 provides cost-effective, S3-compatible object
storage without the operational burden of self-hosted MinIO.

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| API Gateway | Go + chi | High-throughput HTTP entry point |
| WebSocket Server | Go | Real-time alerts and AI streaming |
| Alert Engine | Go + Kafka | Event-driven deal notifications |
| Scrape Orchestrator | Go + Kafka | Schedules and coordinates spiders |
| Scraping Spiders | Python + Scrapy + Playwright | Per-portal spider implementations |
| Data Pipeline | Python + Pydantic v2 | Normalization, dedup, enrichment |
| ML Scorer | Python + LightGBM + ONNX | Per-country deal scoring |
| ML Trainer | Python + LightGBM + MLflow | Model training and registry |
| AI Search | Python + LiteLLM | Conversational property search |
| Frontend | Next.js 15 + TypeScript | App Router, shadcn/ui, Tailwind 4 |
| Maps | MapLibre GL JS | Open-source map rendering |
| Messaging | Apache Kafka (shared cluster) | Async event bus |
| RPC | gRPC + Protobuf | Synchronous inter-service calls |
| Database | PostgreSQL 16 + PostGIS 3.4 (shared cluster) | Country-partitioned tables |
| Cache | Redis 7 (self-deployed) | Sessions and query caching |
| Object Storage | Hetzner S3 (external) | Images, documents, model artifacts |
| Metrics | Prometheus (shared cluster) | Application metrics collection |
| Dashboards | Grafana (shared cluster) | Observability dashboards |
| Container Orchestration | Kubernetes + Helm | All services containerized |
| GitOps | ArgoCD | Declarative deployments |
| Protobuf Tooling | buf | Linting and code generation |

## Monorepo Structure & Development Workflow

The repository MUST follow this layout:

```text
estategap/
├── services/          # Go and Python microservices (one dir per service)
│   ├── api-gateway/         # Go
│   ├── websocket-server/    # Go
│   ├── alert-engine/        # Go
│   ├── scrape-orchestrator/ # Go
│   ├── spiders/             # Python
│   ├── pipeline/            # Python
│   ├── ml-scorer/           # Python
│   ├── ml-trainer/          # Python
│   └── ai-search/           # Python
├── frontend/          # Next.js 15 application
├── proto/             # Shared Protobuf definitions
├── helm/              # Helm charts for K8s deployment
├── libs/              # Shared libraries
│   ├── pkg/                 # Go shared packages
│   └── common/              # Python shared packages
└── docs/              # Architecture and requirements documentation
```

Development workflow rules:

- Each service MUST have its own `Dockerfile`, dependency manifest,
  and README.
- Proto changes MUST be committed and generated before dependent
  service changes.
- CI MUST run linting, type checking, and tests for all affected
  services on every PR.
- Feature branches MUST target `main`. No long-lived release branches.

## Migration Strategy

The brownfield adaptation follows these migration rules:

- **Feature-branch per migration**: separate branches for kafka, s3,
  helm-refactor, and helm-docs changes.
- **Backward compatibility**: each migration MUST be backward-compatible
  during the transition period. Existing services keep running while
  new infrastructure is wired up.
- **Topic/bucket naming consistency**: all Kafka topic names MUST
  mirror the legacy NATS stream names. All S3 bucket names MUST match
  the legacy MinIO bucket names.
- **Zero downtime**: existing services MUST continue operating during
  migration. No big-bang cutover.
- **No functional changes**: the adaptation changes infrastructure
  plumbing only. All business logic, API contracts, gRPC services,
  database schema, ML pipeline, alert system, AI chat, scraping, and
  frontend MUST remain identical.

**Rationale**: Incremental, backward-compatible migration reduces risk
and allows validation at each step. Name consistency between old and
new systems preserves audit trails and simplifies rollback if needed.

## Governance

This constitution is the highest-authority document for EstateGap
technical decisions. All implementation work, code reviews, and
architectural proposals MUST comply with the principles defined here.

### Amendment Procedure

1. Propose an amendment as a PR modifying this constitution file.
2. The amendment MUST include rationale for the change.
3. Breaking changes to principles require MAJOR version bump and
   migration plan for affected services.
4. Non-breaking additions require MINOR version bump.
5. Clarifications and typo fixes require PATCH version bump.

### Compliance Review

- Every PR MUST be checked against applicable constitution principles.
- Architecture Decision Records (ADRs) in `docs/` MUST reference
  the constitution principles they relate to.
- Quarterly review of constitution relevance and accuracy.

### Versioning Policy

This constitution follows semantic versioning:

- **MAJOR**: Principle removal, redefinition, or backward-incompatible
  governance change.
- **MINOR**: New principle or section added, material expansion of
  existing guidance.
- **PATCH**: Clarifications, wording improvements, typo fixes.

**Version**: 2.0.0 | **Ratified**: 2026-04-16 | **Last Amended**: 2026-04-17
