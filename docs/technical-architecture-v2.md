# Technical Architecture v2 — EstateGap

**Project:** Undervalued Property Detection & Alert System — Multi-Country Platform  
**Version:** 2.0  
**Date:** April 2026  
**Target:** Kubernetes-native deployment  
**Companion docs:** `functional-requirements v2.0`, `addendum v2.1`

---

## 1. Architecture Philosophy

### Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Architecture style** | Event-driven microservices | Clear bounded contexts (scraping, ML, alerts, AI chat). Independent scaling per concern. |
| **Backend languages** | **Go** (API + orchestration) + **Python** (data + ML + AI) | Go for high-concurrency HTTP/WebSocket, fast startup, tiny containers (~15MB). Python for ML/scraping/LLM ecosystems. Each language where it excels. |
| **Frontend** | **Next.js 15** (TypeScript, App Router) | SSR for SEO, React Server Components, API routes for BFF pattern, excellent i18n support. |
| **Inter-service comms** | **NATS JetStream** (async events) + **gRPC** (sync calls) | NATS: K8s-native, <10MB binary, exactly-once delivery, Go & Python clients. gRPC: typed contracts, bidirectional streaming for AI chat. |
| **Database** | **PostgreSQL 16 + PostGIS** (primary) + **Redis 7** (cache/sessions) | Spatial queries, JSONB, table partitioning, mature K8s operators. Redis for hot data, rate limiting, real-time leaderboards. |
| **ML lifecycle** | **MLflow** (tracking) + **ONNX Runtime** (inference) | Language-agnostic model format. Train in Python, serve anywhere. |
| **Deployment** | **Kubernetes** (Helm charts, GitOps via ArgoCD) | User already has a K8s cluster. Helm for packaging, ArgoCD for declarative deployments. |

---

## 2. High-Level Architecture

```
                              ┌──────────────────────┐
                              │      INTERNET         │
                              │   (Users + Portals)   │
                              └──────────┬───────────┘
                                         │
                              ┌──────────▼───────────┐
                              │  Ingress Controller   │
                              │  (Traefik / Nginx)    │
                              │  TLS termination      │
                              │  Rate limiting (L7)   │
                              └──────────┬───────────┘
                                         │
                    ┌────────────────────┬┴────────────────────┐
                    │                    │                      │
           ┌────────▼──────┐   ┌────────▼──────┐    ┌─────────▼─────┐
           │  Frontend     │   │  API Gateway  │    │  WebSocket    │
           │  (Next.js)    │   │  (Go)         │    │  Server (Go)  │
           │               │   │               │    │               │
           │  SSR + Static │   │  REST + Auth  │    │  AI Chat      │
           │  i18n (10 lng)│   │  Rate Limits  │    │  Streaming    │
           │  BFF pattern  │   │  Stripe hooks │    │  Notifications│
           └───────────────┘   └───────┬───────┘    └───────┬───────┘
                                       │                    │
                    ┌──────────────────┬┴────────────────────┘
                    │                  │
         ┌──────────▼──────────────────▼──────────────────────┐
         │              NATS JetStream                        │
         │              (Event Bus)                           │
         │                                                    │
         │  Streams:                                          │
         │    raw.listings.{country}                           │
         │    normalized.listings                              │
         │    enriched.listings                                │
         │    scored.listings                                  │
         │    alerts.triggers                                  │
         │    alerts.notifications                             │
         │    scraper.commands                                 │
         │    ai.conversations                                │
         │    price.changes                                    │
         └───────┬──────────────┬──────────────┬──────────────┘
                 │              │              │
    ┌────────────▼───┐  ┌──────▼──────┐  ┌────▼──────────────┐
    │  SCRAPING       │  │  PIPELINE    │  │  INTELLIGENCE     │
    │  DOMAIN         │  │  DOMAIN      │  │  DOMAIN           │
    │                 │  │              │  │                   │
    │ ┌─────────────┐ │  │ ┌──────────┐│  │ ┌───────────────┐ │
    │ │ Scrape      │ │  │ │Normalizer││  │ │ ML Scorer     │ │
    │ │ Orchestrator│ │  │ │(Python)  ││  │ │ (Python+ONNX) │ │
    │ │ (Go)        │ │  │ └──────────┘│  │ └───────────────┘ │
    │ └─────────────┘ │  │ ┌──────────┐│  │ ┌───────────────┐ │
    │ ┌─────────────┐ │  │ │Dedup     ││  │ │ ML Trainer    │ │
    │ │ Spider      │ │  │ │(Python)  ││  │ │ (Python)      │ │
    │ │ Workers     │ │  │ └──────────┘│  │ │ CronJob       │ │
    │ │ (Python)    │ │  │ ┌──────────┐│  │ └───────────────┘ │
    │ │ per-portal  │ │  │ │Enricher  ││  │ ┌───────────────┐ │
    │ └─────────────┘ │  │ │(Python)  ││  │ │ AI Chat Svc   │ │
    │ ┌─────────────┐ │  │ └──────────┘│  │ │ (Python)      │ │
    │ │ Proxy       │ │  │ ┌──────────┐│  │ │ LLM Provider  │ │
    │ │ Manager     │ │  │ │Change    ││  │ └───────────────┘ │
    │ │ (Go sidecar)│ │  │ │Detector  ││  └───────────────────┘
    │ └─────────────┘ │  │ │(Python)  ││
    └─────────────────┘  │ └──────────┘│  ┌───────────────────┐
                         └─────────────┘  │  NOTIFICATION      │
                                          │  DOMAIN            │
    ┌─────────────────┐                   │                   │
    │  DATA STORES     │                   │ ┌───────────────┐ │
    │                  │                   │ │ Alert Engine  │ │
    │ ┌──────────────┐ │                   │ │ (Go)          │ │
    │ │ PostgreSQL   │ │                   │ │ Rule matching │ │
    │ │ + PostGIS    │ │                   │ └───────────────┘ │
    │ │ (primary +   │ │                   │ ┌───────────────┐ │
    │ │  read replica)│ │                   │ │ Dispatcher    │ │
    │ └──────────────┘ │                   │ │ (Go)          │ │
    │ ┌──────────────┐ │                   │ │ Email/TG/WA/  │ │
    │ │ Redis 7      │ │                   │ │ Push/Webhook  │ │
    │ │ (cache +     │ │                   │ └───────────────┘ │
    │ │  sessions)   │ │                   └───────────────────┘
    │ └──────────────┘ │
    │ ┌──────────────┐ │   ┌───────────────────┐
    │ │ S3 / MinIO   │ │   │  OBSERVABILITY     │
    │ │ (models,     │ │   │                   │
    │ │  exports,    │ │   │  Prometheus        │
    │ │  images)     │ │   │  Grafana           │
    │ └──────────────┘ │   │  Loki              │
    └──────────────────┘   │  Tempo (traces)    │
                           └───────────────────┘
```

---

## 3. Service Catalog

### 3.1 Go Services

| Service | Role | Why Go | Replicas | HPA |
|---|---|---|---|---|
| **api-gateway** | REST API, auth (JWT/OAuth2), rate limiting, Stripe webhooks, request routing via gRPC to internal services | High-concurrency HTTP, sub-ms routing, tiny memory footprint (~30MB) | 2–6 | CPU 60% |
| **ws-server** | WebSocket server for AI chat streaming, real-time deal notifications, live scraping status | Goroutines handle 10k+ concurrent WS connections per pod | 2–4 | Connections per pod |
| **alert-engine** | Evaluates alert rules against scored listings, dispatches to notification channels | Fan-out pattern: one scored listing → evaluate N user rules concurrently | 2–3 | Queue depth |
| **scrape-orchestrator** | Manages scraping schedules per portal/country, distributes jobs to Python spider workers via NATS, monitors health | Scheduling + coordination logic, no heavy libs needed | 1–2 | Fixed |
| **proxy-manager** | Manages rotating proxy pool, assigns proxies to spider workers, tracks health/blocks per IP | High-frequency health checks, IP rotation logic | 1 | Fixed |

### 3.2 Python Services

| Service | Role | Why Python | Replicas | HPA |
|---|---|---|---|---|
| **spider-worker** | Executes scraping jobs (one pod type per portal or a generic worker with portal plugins) | Scrapy, Playwright, BeautifulSoup, httpx — all Python-native | 3–10 | Queue depth |
| **pipeline-normalizer** | Transforms raw portal data → unified schema (Pydantic validation) | pandas, Pydantic — best in Python | 2–4 | Queue depth |
| **pipeline-dedup** | Cross-portal deduplication via GPS + fuzzy address matching | rapidfuzz, scipy spatial — Python libs | 1–2 | Queue depth |
| **pipeline-enricher** | Cadastral enrichment, POI distance calculation, public data joins | geopandas, requests to public APIs | 1–2 | Queue depth |
| **pipeline-change-detector** | Detects price drops, delistings, new listings vs. previous state | pandas diff logic | 1–2 | Queue depth |
| **ml-scorer** | Scores listings: loads ONNX model, computes deal score + confidence + SHAP | ONNX Runtime, SHAP, scikit-learn, numpy | 2–4 | CPU 70% |
| **ml-trainer** | Weekly model retraining pipeline (K8s CronJob) | LightGBM, Optuna, MLflow, pandas | 0 (CronJob) | N/A |
| **ai-chat-service** | AI conversation manager: builds LLM prompts, manages state, parses structured output, fetches market context | LLM SDKs (anthropic, openai), prompt engineering, heavy string/JSON work | 2–4 | CPU 60% |

### 3.3 Frontend

| Service | Role | Stack | Replicas |
|---|---|---|---|
| **frontend** | SSR web app, dashboard, map, search, AI chat UI, admin panel | Next.js 15, TypeScript, React 19, MapLibre GL, Recharts, next-intl | 2–3 |

---

## 4. Technology Stack (Complete)

### 4.1 Go Services Stack

```
Language:       Go 1.23
HTTP framework: net/http (stdlib) + chi router (lightweight)
WebSocket:      gorilla/websocket or nhooyr/websocket
gRPC:           google.golang.org/grpc + protobuf
NATS client:    nats-io/nats.go
PostgreSQL:     jackc/pgx v5 (native driver, no ORM)
Redis:          redis/go-redis v9
Auth:           golang-jwt/jwt + OAuth2 stdlib
Stripe:         stripe/stripe-go
Metrics:        prometheus/client_golang
Logging:        log/slog (stdlib, structured JSON)
Config:         spf13/viper + K8s ConfigMaps
Container:      FROM scratch (or distroless) — ~15MB images
```

### 4.2 Python Services Stack

```
Language:       Python 3.12
Async HTTP:     httpx + asyncio
Scraping:       Scrapy 2.11 + Playwright (JS rendering)
HTML parsing:   parsel (CSS/XPath) + BeautifulSoup
Validation:     Pydantic v2
NATS client:    nats-io/nats.py
PostgreSQL:     asyncpg (async) + SQLAlchemy 2.0 (models)
Redis:          redis-py[async]
ML training:    LightGBM, XGBoost, Optuna, scikit-learn, pandas
ML inference:   ONNX Runtime
Explainability: SHAP
ML tracking:    MLflow (client)
LLM SDKs:      anthropic, openai, litellm (unified interface)
STT fallback:   openai (Whisper API)
Translation:    deepl (API client)
Spatial:        geopandas, shapely, scipy
Fuzzy match:    rapidfuzz
gRPC:           grpcio + protobuf
Metrics:        prometheus_client
Logging:        structlog (JSON)
Container:      python:3.12-slim — ~150MB images
```

### 4.3 Frontend Stack

```
Framework:      Next.js 15 (App Router, React Server Components)
Language:       TypeScript 5.5
UI library:     shadcn/ui + Tailwind CSS 4
Maps:           MapLibre GL JS + PMTiles (vector tiles)
Charts:         Recharts (dashboard) + Apache ECharts (analytics)
i18n:           next-intl (10 languages)
State:          Zustand (client) + React Query / TanStack Query (server)
WebSocket:      native WebSocket API (for AI chat streaming)
Voice input:    Web Speech API (browser STT) + Whisper API fallback
Auth:           NextAuth.js v5 (JWT + Google OAuth)
Forms:          React Hook Form + Zod validation
Container:      node:22-alpine + standalone output — ~80MB images
```

### 4.4 Infrastructure & Platform

```
Orchestration:  Kubernetes (user's existing cluster)
Package mgmt:   Helm 3 charts
GitOps:         ArgoCD
Ingress:        Traefik (or Nginx Ingress Controller)
TLS:            cert-manager + Let's Encrypt
Service mesh:   (optional) Linkerd (lighter than Istio)
Message broker: NATS JetStream (deployed as K8s StatefulSet)
Database:       PostgreSQL 16 + PostGIS 3.4 (CloudNativePG operator or managed)
Cache:          Redis 7 (Bitnami Helm chart or managed)
Object storage: MinIO (self-hosted) or S3-compatible
ML tracking:    MLflow (deployed in-cluster)
CI/CD:          GitHub Actions → build images → push to GHCR → ArgoCD syncs
Monitoring:     Prometheus + Grafana (kube-prometheus-stack Helm chart)
Logging:        Loki + Promtail
Tracing:        Tempo + OpenTelemetry
Secrets:        K8s Secrets + Sealed Secrets (Bitnami)
```

---

## 5. Kubernetes Cluster Layout

### 5.1 Namespace Structure

```
k8s cluster
├── estategap-system        # Core infrastructure
│   ├── nats (StatefulSet, 3 replicas)
│   ├── postgresql (StatefulSet via CloudNativePG, primary + 1 read replica)
│   ├── redis (StatefulSet, 1 replica + sentinel)
│   └── minio (StatefulSet, 1 replica)
│
├── estategap-gateway       # Edge / public-facing
│   ├── frontend (Deployment, 2-3 replicas, HPA)
│   ├── api-gateway (Deployment, 2-6 replicas, HPA)
│   └── ws-server (Deployment, 2-4 replicas, HPA)
│
├── estategap-scraping      # Data acquisition
│   ├── scrape-orchestrator (Deployment, 1-2 replicas)
│   ├── proxy-manager (Deployment, 1 replica)
│   ├── spider-worker-es (Deployment, 2-4 replicas, HPA)  # Spain portals
│   ├── spider-worker-it (Deployment, 1-3 replicas, HPA)  # Italy portals
│   ├── spider-worker-fr (Deployment, 1-3 replicas, HPA)  # France portals
│   ├── spider-worker-eu (Deployment, 1-3 replicas, HPA)  # Other EU
│   └── spider-worker-us (Deployment, 1-3 replicas, HPA)  # US portals
│
├── estategap-pipeline      # Data processing
│   ├── pipeline-normalizer (Deployment, 2-4 replicas, HPA)
│   ├── pipeline-dedup (Deployment, 1-2 replicas)
│   ├── pipeline-enricher (Deployment, 1-2 replicas)
│   └── pipeline-change-detector (Deployment, 1-2 replicas)
│
├── estategap-intelligence  # ML + AI
│   ├── ml-scorer (Deployment, 2-4 replicas, HPA)
│   ├── ml-trainer (CronJob, weekly)
│   ├── ai-chat-service (Deployment, 2-4 replicas, HPA)
│   └── mlflow (Deployment, 1 replica)
│
├── estategap-notifications # Alerting
│   ├── alert-engine (Deployment, 2-3 replicas, HPA)
│   └── alert-dispatcher (Deployment, 2-3 replicas, HPA)
│
└── observability              # Monitoring (shared or per-app)
    ├── prometheus (StatefulSet)
    ├── grafana (Deployment)
    ├── loki (StatefulSet)
    └── tempo (StatefulSet)
```

### 5.2 Ingress Routes

```yaml
# Traefik IngressRoute (simplified)
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: estategap-routes
  namespace: estategap-gateway
spec:
  entryPoints: [websecure]
  routes:
    # Frontend (SSR)
    - match: Host(`app.estategap.com`)
      kind: Rule
      services:
        - name: frontend
          port: 3000

    # REST API
    - match: Host(`api.estategap.com`)
      kind: Rule
      services:
        - name: api-gateway
          port: 8080
      middlewares:
        - name: rate-limit
        - name: cors

    # WebSocket (AI Chat + real-time)
    - match: Host(`ws.estategap.com`)
      kind: Rule
      services:
        - name: ws-server
          port: 8081

    # Admin / Monitoring
    - match: Host(`admin.estategap.com`)
      kind: Rule
      services:
        - name: grafana
          port: 3000
      middlewares:
        - name: admin-auth
```

### 5.3 Resource Profiles

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Notes |
|---|---|---|---|---|---|
| api-gateway | 100m | 500m | 64Mi | 256Mi | Go: tiny footprint |
| ws-server | 100m | 500m | 64Mi | 256Mi | 10k conns ≈ 200Mi |
| frontend | 200m | 1000m | 256Mi | 512Mi | Next.js SSR |
| spider-worker-* | 500m | 2000m | 512Mi | 2Gi | Playwright needs memory |
| pipeline-normalizer | 200m | 1000m | 256Mi | 1Gi | pandas in-memory |
| pipeline-dedup | 200m | 1000m | 512Mi | 2Gi | Spatial index in memory |
| pipeline-enricher | 100m | 500m | 256Mi | 1Gi | I/O-bound (API calls) |
| ml-scorer | 500m | 2000m | 512Mi | 2Gi | ONNX inference |
| ml-trainer | 2000m | 4000m | 4Gi | 8Gi | CronJob, bursty |
| ai-chat-service | 200m | 1000m | 256Mi | 1Gi | I/O-bound (LLM API) |
| alert-engine | 100m | 500m | 64Mi | 256Mi | Go |
| postgresql | 2000m | 4000m | 4Gi | 8Gi | Database |
| redis | 200m | 500m | 256Mi | 1Gi | Cache |
| nats | 100m | 500m | 64Mi | 256Mi | Broker |

---

## 6. Data Flow Architecture

### 6.1 Scraping → Scoring Pipeline

```
scrape-orchestrator (Go)
  │
  │  Publishes job to NATS: scraper.commands.{country}.{portal}
  │  Example: scraper.commands.es.idealista
  ▼
spider-worker-es (Python)
  │
  │  1. Receives job from NATS
  │  2. Requests proxy from proxy-manager (gRPC)
  │  3. Scrapes portal (Scrapy/Playwright)
  │  4. Publishes raw listing to NATS: raw.listings.es
  ▼
pipeline-normalizer (Python)
  │
  │  1. Consumes raw.listings.{country}
  │  2. Validates with Pydantic
  │  3. Maps portal fields → unified schema
  │  4. Writes to PostgreSQL (listings table)
  │  5. Publishes to NATS: normalized.listings
  ▼
pipeline-dedup (Python)
  │
  │  1. Consumes normalized.listings
  │  2. Queries PostGIS for nearby listings (50m radius)
  │  3. Fuzzy match on address + features
  │  4. Merges duplicates → canonical_id
  │  5. Publishes to NATS: enriched.listings (or to enricher)
  ▼
pipeline-enricher (Python)
  │
  │  1. Consumes from dedup output
  │  2. Calls country-specific enrichment APIs (Catastro, DVF, Land Registry...)
  │  3. Calculates POI distances (metro, coast, center)
  │  4. Updates listing in PostgreSQL
  │  5. Publishes to NATS: enriched.listings
  ▼
ml-scorer (Python)
  │
  │  1. Consumes enriched.listings
  │  2. Loads feature engineering pipeline
  │  3. Runs ONNX model inference
  │  4. Computes deal_score, confidence, tier
  │  5. Generates SHAP explanations (cached for Tier 1-2)
  │  6. Finds K-nearest comparables (KNN on feature space)
  │  7. Updates listing in PostgreSQL
  │  8. Publishes to NATS: scored.listings
  ▼
alert-engine (Go)
  │
  │  1. Consumes scored.listings
  │  2. Loads all active alert rules from cache (Redis)
  │  3. For each rule: evaluates zone match (PostGIS), filter match, tier match
  │  4. Dedup check: has this listing already been sent to this user?
  │  5. For instant rules: publishes to NATS alerts.notifications
  │  6. For digest rules: buffers in Redis, flushes on schedule
  ▼
alert-dispatcher (Go)
  │
  │  1. Consumes alerts.notifications
  │  2. Routes to channel: email (SES), Telegram, WhatsApp, Push (FCM), Webhook
  │  3. Records delivery status in PostgreSQL
```

### 6.2 AI Conversational Search Flow

```
User (browser)
  │
  │  Types or speaks: "Busco un loft industrial en Barcelona"
  │  (voice → Web Speech API → text transcription shown in input)
  ▼
Frontend (Next.js)
  │
  │  Opens WebSocket to ws-server
  │  Sends: { type: "chat", session_id: "abc", message: "Busco un loft..." }
  ▼
ws-server (Go)
  │
  │  1. Authenticates user (JWT from cookie)
  │  2. Checks subscription limits (conversations/day)
  │  3. Forwards to ai-chat-service via gRPC streaming
  ▼
ai-chat-service (Python)
  │
  │  1. Loads/creates conversation state (from Redis)
  │  2. Fetches market context:
  │     - gRPC call to api-gateway → zone stats for "Barcelona"
  │     - Available property types for country "ES"
  │     - Current deal counts for relevant zones
  │  3. Builds LLM prompt:
  │     ┌─────────────────────────────────────────┐
  │     │ System prompt (role, flow, taxonomy)    │
  │     │ + Market context (injected zone stats)  │
  │     │ + Conversation history                  │
  │     │ + User message                          │
  │     │ + Output format instructions (JSON)     │
  │     └─────────────────────────────────────────┘
  │  4. Calls LLM provider (Claude/GPT/self-hosted via LiteLLM)
  │  5. Parses response → chat_message + criteria_json + visual_trigger
  │  6. If visual_trigger: queries image reference library
  │  7. Saves updated state to Redis
  │  8. Streams response back via gRPC
  ▼
ws-server (Go)
  │
  │  Streams tokens to browser via WebSocket (for typewriter effect)
  │  Sends visual references as separate WS message (image carousel)
  ▼
Frontend (Next.js)
  │
  │  Renders chat bubbles, chips, image carousel
  │  When criteria complete → shows summary card
  │
  │  User taps [🚀 Search + Alert]:
  │  POST /api/search → api-gateway → PostgreSQL query
  │  POST /api/alerts/rules → api-gateway → creates alert rule
  │
  │  Results displayed inline below the conversation
```

---

## 7. gRPC Service Contracts

```protobuf
// proto/services.proto

syntax = "proto3";

// ─── AI Chat ───────────────────────────────────────
service AIChatService {
  // Bidirectional streaming: user messages in, AI responses out
  rpc Chat(stream ChatRequest) returns (stream ChatResponse);
  rpc GetConversation(ConversationID) returns (Conversation);
  rpc ListConversations(UserID) returns (ConversationList);
}

message ChatRequest {
  string session_id = 1;
  string user_id = 2;
  string message = 3;
  string language = 4;
  optional string image_feedback = 5;  // "liked" / "disliked" + image_id
}

message ChatResponse {
  string session_id = 1;
  oneof payload {
    TextChunk text_chunk = 2;         // Streamed token-by-token
    SuggestedChips chips = 3;         // Quick-reply buttons
    ImageCarousel images = 4;         // Visual references
    CriteriaSummary summary = 5;      // Final criteria card
    SearchResults results = 6;        // Inline results after confirmation
  }
}

message CriteriaSummary {
  string status = 1;                  // "refining" | "ready"
  float confidence = 2;
  map<string, string> criteria = 3;
  repeated string pending_dimensions = 4;
}

// ─── ML Scoring ────────────────────────────────────
service MLScoringService {
  rpc ScoreListing(ListingFeatures) returns (ScoringResult);
  rpc ScoreBatch(ListingBatch) returns (ScoringBatchResult);
  rpc GetComparables(ComparablesRequest) returns (ComparablesList);
}

message ScoringResult {
  int32 estimated_price = 1;
  float deal_score = 2;
  int32 deal_tier = 3;
  int32 confidence_low = 4;
  int32 confidence_high = 5;
  repeated ShapFeature shap_top = 6;
  string model_version = 7;
}

// ─── Proxy Management ──────────────────────────────
service ProxyService {
  rpc GetProxy(ProxyRequest) returns (ProxyAssignment);
  rpc ReportResult(ProxyReport) returns (Empty);
}

message ProxyRequest {
  string country = 1;          // geo-target
  string portal = 2;           // portal-specific pool
  bool sticky_session = 3;     // for paginated crawls
}
```

---

## 8. Database Schema Highlights (Multi-Country)

```sql
-- Listings partitioned by country (first level)
CREATE TABLE listings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id    UUID,
    country         CHAR(2) NOT NULL,          -- ISO 3166-1: ES, FR, IT, US...
    source          VARCHAR(30) NOT NULL,       -- idealista, seloger, zillow...
    source_id       VARCHAR(60) NOT NULL,
    source_url      TEXT NOT NULL,

    -- Location
    address         TEXT,
    neighborhood    VARCHAR(100),
    district        VARCHAR(100),
    city            VARCHAR(100),
    region          VARCHAR(100),
    postal_code     VARCHAR(15),
    location        GEOMETRY(Point, 4326),

    -- Pricing (dual currency)
    asking_price        NUMERIC(14,2),
    currency            CHAR(3) NOT NULL,       -- EUR, GBP, USD, SEK...
    asking_price_eur    NUMERIC(14,2),          -- normalized
    price_per_m2_eur    NUMERIC(10,2),

    -- Physical
    property_category   VARCHAR(20),            -- residential, commercial, industrial, land
    property_type       VARCHAR(30),
    built_area          NUMERIC(10,2),
    area_unit           VARCHAR(5) DEFAULT 'm2', -- m2 or sqft
    built_area_m2       NUMERIC(10,2),          -- normalized
    usable_area_m2      NUMERIC(10,2),
    plot_area_m2        NUMERIC(12,2),          -- for land/houses
    bedrooms            SMALLINT,
    bathrooms           SMALLINT,
    floor_number        SMALLINT,
    /* ... (rest of fields as in v1 schema) ... */

    -- Commercial/Industrial specific (nullable)
    frontage_m          NUMERIC(6,2),
    ceiling_height_m    NUMERIC(4,2),
    loading_docks       SMALLINT,
    power_kw            NUMERIC(8,2),

    -- Land specific (nullable)
    buildability_index  NUMERIC(4,2),
    urban_classification VARCHAR(30),

    -- Scores
    estimated_price     NUMERIC(14,2),
    deal_score          NUMERIC(5,2),
    deal_tier           SMALLINT,
    confidence_low      NUMERIC(14,2),
    confidence_high     NUMERIC(14,2),
    model_version       VARCHAR(20),
    scored_at           TIMESTAMPTZ,

    -- Metadata
    status              VARCHAR(20) DEFAULT 'active',
    description_orig    TEXT,                   -- original language
    description_lang    CHAR(2),                -- detected language
    first_seen_at       TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ DEFAULT NOW(),
    published_at        TIMESTAMPTZ,
    delisted_at         TIMESTAMPTZ,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, source_id)
) PARTITION BY LIST (country);

CREATE TABLE listings_es PARTITION OF listings FOR VALUES IN ('ES');
CREATE TABLE listings_fr PARTITION OF listings FOR VALUES IN ('FR');
CREATE TABLE listings_it PARTITION OF listings FOR VALUES IN ('IT');
CREATE TABLE listings_pt PARTITION OF listings FOR VALUES IN ('PT');
CREATE TABLE listings_de PARTITION OF listings FOR VALUES IN ('DE');
CREATE TABLE listings_gb PARTITION OF listings FOR VALUES IN ('GB');
CREATE TABLE listings_nl PARTITION OF listings FOR VALUES IN ('NL');
CREATE TABLE listings_us PARTITION OF listings FOR VALUES IN ('US');
CREATE TABLE listings_other PARTITION OF listings DEFAULT;

-- AI Conversations
CREATE TABLE ai_conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    language        CHAR(2),
    criteria_state  JSONB,              -- latest criteria snapshot
    alert_rule_id   UUID,               -- created alert (if any)
    turn_count      SMALLINT DEFAULT 0,
    status          VARCHAR(20),        -- active, completed, abandoned
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES ai_conversations(id),
    role            VARCHAR(10),        -- user, assistant
    content         TEXT,
    criteria_snapshot JSONB,            -- criteria state after this turn
    visual_refs     JSONB,              -- images shown (if any)
    tokens_used     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 9. CI/CD & GitOps

```
┌──────────┐    ┌───────────────────────┐    ┌──────────────┐    ┌──────────┐
│  GitHub   │───▶│  GitHub Actions       │───▶│  Container   │───▶│  ArgoCD  │
│  Push     │    │                       │    │  Registry    │    │          │
│           │    │  Per-service pipeline: │    │  (GHCR)      │    │  Syncs   │
│           │    │  1. Lint (golangci /   │    │              │    │  Helm    │
│           │    │     ruff+mypy)         │    │  Tags:       │    │  charts  │
│           │    │  2. Unit tests         │    │  sha-abc123  │    │  to K8s  │
│           │    │  3. Build Docker image │    │  v1.2.3      │    │          │
│           │    │  4. Push to GHCR       │    │  latest      │    │          │
│           │    │  5. Update Helm values │    │              │    │          │
│           │    └───────────────────────┘    └──────────────┘    └──────────┘
```

### Monorepo Structure

```
estategap/
├── .github/workflows/
│   ├── ci-go.yml              # Lint + test + build all Go services
│   ├── ci-python.yml          # Lint + test + build all Python services
│   ├── ci-frontend.yml        # Lint + test + build Next.js
│   └── release.yml            # Tag → build → push → update Helm
│
├── proto/                     # Shared protobuf definitions
│   ├── services.proto
│   └── buf.gen.yaml
│
├── services/
│   ├── api-gateway/           # Go
│   │   ├── cmd/main.go
│   │   ├── internal/
│   │   │   ├── handler/       # HTTP handlers
│   │   │   ├── middleware/    # Auth, rate limit, CORS
│   │   │   ├── grpc/         # gRPC clients to internal services
│   │   │   └── config/
│   │   ├── Dockerfile
│   │   └── go.mod
│   │
│   ├── ws-server/             # Go
│   │   ├── cmd/main.go
│   │   ├── internal/
│   │   │   ├── hub/          # WebSocket connection manager
│   │   │   ├── chat/         # AI chat WS protocol
│   │   │   └── realtime/     # Deal notifications
│   │   ├── Dockerfile
│   │   └── go.mod
│   │
│   ├── scrape-orchestrator/   # Go
│   ├── proxy-manager/         # Go
│   ├── alert-engine/          # Go
│   ├── alert-dispatcher/      # Go
│   │
│   ├── spider-workers/        # Python
│   │   ├── spiders/
│   │   │   ├── base.py
│   │   │   ├── es_idealista.py
│   │   │   ├── es_fotocasa.py
│   │   │   ├── it_immobiliare.py
│   │   │   ├── fr_seloger.py
│   │   │   ├── fr_leboncoin.py
│   │   │   ├── us_zillow.py
│   │   │   └── ...
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   ├── pipeline/              # Python
│   │   ├── normalizer/
│   │   ├── deduplicator/
│   │   ├── enricher/
│   │   │   ├── base.py
│   │   │   ├── es_catastro.py
│   │   │   ├── fr_dvf.py
│   │   │   ├── gb_land_registry.py
│   │   │   └── ...
│   │   ├── change_detector/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   ├── ml/                    # Python
│   │   ├── scorer/
│   │   ├── trainer/
│   │   ├── features/
│   │   ├── explainer/
│   │   ├── Dockerfile.scorer
│   │   ├── Dockerfile.trainer
│   │   └── pyproject.toml
│   │
│   └── ai-chat/               # Python
│       ├── service.py
│       ├── conversation.py
│       ├── prompts/
│       │   ├── system_prompt.jinja2
│       │   └── market_context.jinja2
│       ├── providers/
│       │   ├── base.py
│       │   ├── claude.py
│       │   ├── openai.py
│       │   └── litellm.py
│       ├── visual_refs/
│       ├── Dockerfile
│       └── pyproject.toml
│
├── frontend/                  # Next.js
│   ├── src/
│   │   ├── app/
│   │   │   ├── [locale]/     # i18n routing
│   │   │   │   ├── page.tsx  # Home: AI chat input
│   │   │   │   ├── search/
│   │   │   │   ├── listing/[id]/
│   │   │   │   ├── zones/
│   │   │   │   ├── alerts/
│   │   │   │   ├── portfolio/
│   │   │   │   └── admin/
│   │   │   └── api/          # BFF routes
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatWindow.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── ChipSelector.tsx
│   │   │   │   ├── ImageCarousel.tsx
│   │   │   │   ├── CriteriaSummaryCard.tsx
│   │   │   │   └── VoiceInput.tsx
│   │   │   ├── map/
│   │   │   ├── listings/
│   │   │   └── dashboard/
│   │   ├── lib/
│   │   │   ├── ws.ts         # WebSocket client
│   │   │   ├── api.ts        # REST API client
│   │   │   └── i18n.ts
│   │   └── messages/         # i18n JSON files
│   │       ├── en.json
│   │       ├── es.json
│   │       ├── fr.json
│   │       ├── it.json
│   │       ├── de.json
│   │       └── pt.json
│   ├── Dockerfile
│   └── package.json
│
├── helm/
│   └── estategap/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-staging.yaml
│       ├── values-production.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── namespace.yaml
│           ├── configmap.yaml
│           ├── secrets.yaml (SealedSecret)
│           ├── ingress.yaml
│           ├── api-gateway.yaml
│           ├── ws-server.yaml
│           ├── frontend.yaml
│           ├── spider-workers.yaml
│           ├── pipeline.yaml
│           ├── ml-scorer.yaml
│           ├── ml-trainer-cronjob.yaml
│           ├── ai-chat.yaml
│           ├── alert-engine.yaml
│           ├── nats.yaml
│           ├── postgresql.yaml (or CloudNativePG CR)
│           ├── redis.yaml
│           ├── hpa.yaml
│           └── monitoring.yaml
│
├── docs/
│   ├── functional-requirements-v2.md
│   ├── addendum-v2.1-ai-search.md
│   ├── technical-architecture-v2.md
│   └── runbook.md
│
└── Makefile                   # dev shortcuts: make proto, make test, make build-all
```

---

## 10. Observability Stack

```
┌─────────────────────────────────────────────────────────────┐
│  Grafana Dashboards                                         │
│                                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐│
│  │ Scraping      │ │ ML Model     │ │ AI Conversations    ││
│  │ • Success %   │ │ • MAPE/MAE   │ │ • Conversations/hr  ││
│  │ • Listings/hr │ │ • Inference  │ │ • Avg turns         ││
│  │ • Blocks/hr   │ │   latency    │ │ • LLM tokens/day   ││
│  │ • By portal   │ │ • Deal dist. │ │ • Conversion rate   ││
│  │ • By country  │ │ • By country │ │   (chat → alert)    ││
│  └──────────────┘ └──────────────┘ └──────────────────────┘│
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐│
│  │ API Gateway   │ │ Alerts       │ │ Business            ││
│  │ • Req/sec     │ │ • Sent/day   │ │ • Active users      ││
│  │ • Latency p95 │ │ • Delivery % │ │ • MRR               ││
│  │ • Error rate  │ │ • Click rate │ │ • Churn rate         ││
│  │ • By endpoint │ │ • By channel │ │ • Listings/country   ││
│  └──────────────┘ └──────────────┘ └──────────────────────┘│
└─────────────────────────────────────────────────────────────┘

Data sources:
  Prometheus  ← metrics from all Go/Python services (OpenTelemetry)
  Loki        ← structured JSON logs (Promtail DaemonSet)
  Tempo       ← distributed traces (OpenTelemetry SDK)
```

---

## 11. Cost Estimate (K8s Cluster)

| Component | Sizing | Monthly Cost |
|---|---|---|
| K8s nodes (3× 8 vCPU, 16GB) | Worker pool | ~€100–150 |
| PostgreSQL (managed or operator) | 4 vCPU, 8GB, 200GB SSD | ~€40–80 |
| NATS JetStream | 3-replica StatefulSet | Included in nodes |
| Redis | 1 replica, 1GB | Included in nodes |
| MinIO / S3 | 50GB | ~€5 |
| Residential proxies (~100GB/mo) | 5 countries active | ~€200–300 |
| LLM API costs (Claude/GPT) | ~50k conversations/mo | ~€150–300 |
| AWS SES (email) | ~10k emails/mo | ~€5 |
| Twilio (WhatsApp) | ~5k messages/mo | ~€25 |
| DeepL API (translations) | ~100k chars/mo | ~€5 |
| Domain + DNS | estategap.com | ~€15/year |
| **Total** | | **~€550–900/month** |

Revenue at 100 subscribers (mix Basic/Pro/Global): **~€4,000–5,000/month** → profitable from ~25 subscribers.

---

## 12. Development Phases (Updated)

| Phase | Scope | Duration | Key Deliverable |
|---|---|---|---|
| **1 — Foundation** | K8s setup, Helm charts, PostgreSQL schema, NATS, Go API skeleton, Proto definitions | 2–3 weeks | Infrastructure running, health endpoints |
| **2 — Scraping Core** | Go orchestrator, Python spider (Idealista ES), proxy manager, normalizer | 3–4 weeks | 10k+ Spanish listings scraped and stored |
| **3 — Pipeline** | Dedup, enricher (Catastro), change detector, full pipeline flow | 2–3 weeks | End-to-end pipeline: scrape → enrich |
| **4 — ML v1** | Feature engineering, LightGBM trainer, ONNX scorer, deal scores | 2–3 weeks | All active listings scored, MAPE <10% |
| **5 — Frontend + AI Chat** | Next.js app, dashboard, map, AI chat UI + backend, voice input | 4–5 weeks | Conversational search working E2E |
| **6 — Alerts** | Go alert engine + dispatcher, Telegram/email channels | 2 weeks | Personal deal alerts flowing |
| **7 — Multi-source** | Fotocasa + Immobiliare.it + SeLoger spiders, cross-portal dedup | 3 weeks | 3 countries, 5+ portals |
| **8 — Monetization** | Auth, Stripe, subscriptions, feature gating, public landing page | 2–3 weeks | First paying subscribers |
| **9 — Polish** | Zone analytics, portfolio tracker, admin panel, visual refs library | 3 weeks | Feature-complete product |
| **10 — Scale** | HPA tuning, read replicas, CDN, US portal spiders, model per country | 2–3 weeks | Production-grade, multi-region |

**Total: ~26–32 weeks** (solo developer, part-time) / **~14–18 weeks** (full-time)
