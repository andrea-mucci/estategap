# Development Backlog — Real Estate EstateGap

**Format:** SpecKit-compatible task breakdown  
**Date:** April 2026  
**Estimation:** T-shirt sizes (XS: <2h, S: 2-4h, M: 4-8h, L: 1-2d, XL: 2-5d)  
**Dependencies:** `→` means "depends on"

---

## Epic 0 — Project Bootstrap & SpecKit Setup

> Set up the monorepo, SpecKit configuration, shared contracts, and CI skeleton.

### 0.1 — Repository & Tooling

- [ ] **T-0.1.1** — Initialize monorepo structure  
  **Size:** S  
  Create the root directory structure: `services/`, `frontend/`, `proto/`, `helm/`, `docs/`, `.github/workflows/`. Add root `Makefile`, `.gitignore`, `README.md`. Initialize git.  
  **Acceptance:** `tree -L 2` matches the structure defined in architecture doc §9. All directories exist with placeholder READMEs.

- [ ] **T-0.1.2** — Initialize SpecKit configuration  
  **Size:** XS  
  Run `specify init estategap --ai claude`. Configure the constitution with project principles: polyglot Go+Python, K8s-native, event-driven, NATS+gRPC comms, no ORM in Go (raw pgx), Pydantic validation in Python.  
  **Acceptance:** `.speckit/` directory exists. Constitution file reflects project principles.

- [ ] **T-0.1.3** — Set up Go workspace  
  **Size:** S  
  Create `go.work` at root. Initialize `go.mod` for each Go service (`api-gateway`, `ws-server`, `scrape-orchestrator`, `proxy-manager`, `alert-engine`, `alert-dispatcher`). Add shared `pkg/` directory for common Go code (logger, config, NATS client wrapper, gRPC client helpers).  
  **Acceptance:** `go build ./...` succeeds in each service directory. Shared packages importable.

- [ ] **T-0.1.4** — Set up Python workspace  
  **Size:** S  
  Create `pyproject.toml` for each Python service (`spider-workers`, `pipeline`, `ml`, `ai-chat`). Use `uv` as package manager. Create shared `libs/common/` Python package for Pydantic models, NATS client wrapper, DB session helpers, logging config.  
  **Acceptance:** `uv sync` succeeds in each service. Shared lib importable. `ruff check` and `mypy` pass on empty projects.

- [ ] **T-0.1.5** — Define Protobuf contracts  
  **Size:** M  
  Create `proto/` directory with `.proto` files for all gRPC services: `ai_chat.proto`, `ml_scoring.proto`, `proxy.proto`, `listings.proto`, `common.proto` (shared types). Configure `buf.gen.yaml` for Go and Python code generation.  
  **Acceptance:** `buf generate` produces Go and Python stubs. All service contracts match architecture doc §7.

- [ ] **T-0.1.6** — Create Dockerfiles for all services  
  **Size:** M  
  Create multi-stage Dockerfiles: Go services use `FROM golang:1.23 AS builder` → `FROM scratch` (or `gcr.io/distroless/static`). Python services use `FROM python:3.12-slim`. Frontend uses `FROM node:22-alpine` with Next.js standalone output. Optimize for layer caching.  
  **Acceptance:** `docker build` succeeds for every service. Go images < 20MB. Python images < 200MB. Frontend image < 100MB.

- [ ] **T-0.1.7** — Create CI pipelines (GitHub Actions)  
  **Size:** L  
  Create `.github/workflows/`: `ci-go.yml` (lint with golangci-lint, test, build), `ci-python.yml` (lint with ruff+mypy, test with pytest, build), `ci-frontend.yml` (lint, type-check, build), `ci-proto.yml` (buf lint + generate). Trigger on PR and push to main.  
  **Acceptance:** All CI jobs pass on an empty but valid codebase. Badge in README.

### 0.2 — Helm Charts & K8s Foundation

- [ ] **T-0.2.1** — Create Helm chart skeleton  
  **Size:** L → T-0.1.1  
  Create `helm/estategap/` with `Chart.yaml`, `values.yaml`, `values-staging.yaml`, `values-production.yaml`. Define templates for: namespaces (6), ConfigMap, SealedSecret placeholder, Ingress (Traefik IngressRoute).  
  **Acceptance:** `helm template estategap ./helm/estategap` renders valid YAML. `helm lint` passes.

- [ ] **T-0.2.2** — Deploy NATS JetStream to K8s  
  **Size:** M  
  Add NATS Helm chart as dependency (or create StatefulSet template). Configure JetStream with 3 replicas, persistent storage (10Gi PVC). Define streams: `raw-listings`, `normalized-listings`, `enriched-listings`, `scored-listings`, `alerts-triggers`, `alerts-notifications`, `scraper-commands`, `price-changes`.  
  **Acceptance:** NATS cluster running. `nats stream ls` shows all 8 streams. Pub/sub test message works from a test pod.

- [ ] **T-0.2.3** — Deploy PostgreSQL + PostGIS to K8s  
  **Size:** L  
  Deploy using CloudNativePG operator (or Bitnami Helm chart). Configure primary + 1 read replica. PostGIS extension enabled. 200Gi PVC. Daily backup CronJob to MinIO/S3.  
  **Acceptance:** `psql` connects. `SELECT PostGIS_Version();` returns 3.4+. Replication lag < 1s. Backup CronJob runs successfully.

- [ ] **T-0.2.4** — Deploy Redis to K8s  
  **Size:** S  
  Deploy using Bitnami Redis Helm chart. Single instance + Sentinel. 1Gi memory limit. Persistence enabled (AOF).  
  **Acceptance:** `redis-cli ping` returns PONG. Persistence verified after pod restart.

- [ ] **T-0.2.5** — Deploy MinIO to K8s  
  **Size:** S  
  Deploy MinIO operator or standalone StatefulSet. Create buckets: `ml-models`, `training-data`, `listing-photos`, `exports`, `backups`.  
  **Acceptance:** `mc ls minio/` shows all buckets. Upload/download test file works.

- [ ] **T-0.2.6** — Deploy observability stack  
  **Size:** L  
  Deploy `kube-prometheus-stack` Helm chart (Prometheus + Grafana + AlertManager). Deploy Loki + Promtail for logging. Deploy Tempo for tracing. Configure Grafana data sources.  
  **Acceptance:** Grafana accessible via Ingress. Prometheus targets show K8s node metrics. Loki receiving logs from all namespaces.

- [ ] **T-0.2.7** — Create ArgoCD Application manifest  
  **Size:** S → T-0.2.1  
  Configure ArgoCD to watch the `helm/` directory in the repo. Auto-sync staging, manual sync production.  
  **Acceptance:** ArgoCD UI shows the estategap application. Changes to `values-staging.yaml` auto-deploy.

---

## Epic 1 — Database Schema & Shared Models

> Create the database schema and shared data models used across all services.

- [ ] **T-1.1** — Create Alembic migration project  
  **Size:** S  
  Initialize Alembic in `services/pipeline/`. Configure `alembic.ini` with PostgreSQL connection from env var. Create initial empty migration.  
  **Acceptance:** `alembic upgrade head` runs successfully on empty database.

- [ ] **T-1.2** — Create core schema: countries & portals tables  
  **Size:** M → T-1.1  
  Migration for: `countries` (code, name, currency, active, config JSONB), `portals` (name, country, base_url, spider_class, enabled, scrape_config JSONB), `exchange_rates` (currency, rate_to_eur, date).  
  **Acceptance:** Tables exist. Seed data for 5 launch countries (ES, IT, PT, FR, GB) and 10 priority portals inserted.

- [ ] **T-1.3** — Create core schema: listings table (partitioned)  
  **Size:** L → T-1.1  
  Migration for the `listings` table as defined in architecture doc §8. Partitioned by country (LIST partitioning). Create partitions for ES, FR, IT, PT, DE, GB, NL, US, and DEFAULT. All spatial/deal score indexes.  
  **Acceptance:** Insert test listing in each partition. PostGIS spatial query works. `EXPLAIN` shows partition pruning.

- [ ] **T-1.4** — Create core schema: price_history table  
  **Size:** S → T-1.3  
  Append-only table with FK to listings. Timestamp + price + price_per_m2. Index on (listing_id, recorded_at DESC).  
  **Acceptance:** Insert and query price history for a test listing.

- [ ] **T-1.5** — Create core schema: zones table  
  **Size:** M → T-1.1  
  `zones` table with PostGIS MultiPolygon geometry, hierarchy (parent_id self-reference), level enum (country/region/city/district/neighborhood/postal/custom). GiST index on geometry.  
  **Acceptance:** Insert sample zone for Madrid Centro polygon. `ST_Contains` query returns listings within zone.

- [ ] **T-1.6** — Create core schema: users & subscriptions  
  **Size:** M → T-1.1  
  Tables: `users` (email, password_hash, name, google_id, preferred_language, preferred_currency, subscription_tier, stripe_customer_id), `subscriptions` (user_id, tier, stripe_subscription_id, status, current_period_start/end).  
  **Acceptance:** Create test user, update subscription. Unique constraints on email work.

- [ ] **T-1.7** — Create core schema: alert_rules & alert_log  
  **Size:** M → T-1.6  
  `alert_rules` (user_id, name, countries[], zones UUID[], filters JSONB, min_deal_tier, channels TEXT[], frequency, is_active). `alert_log` (rule_id, listing_id, channel, status, sent_at, opened_at, clicked_at).  
  **Acceptance:** Insert rule with complex JSONB filter. Query rules matching a given country + zone.

- [ ] **T-1.8** — Create core schema: AI conversations  
  **Size:** M → T-1.6  
  `ai_conversations` and `ai_messages` tables as defined in architecture doc §8. JSONB for criteria_state snapshots.  
  **Acceptance:** Insert conversation with 5 turns. Query latest criteria state.

- [ ] **T-1.9** — Create core schema: ML model_versions  
  **Size:** S → T-1.1  
  `model_versions` table (version, country, zone_scope, algorithm, metrics JSONB, artifact_path, trained_at, is_active, training_rows).  
  **Acceptance:** Insert model version. Query active model for country "ES".

- [ ] **T-1.10** — Create core schema: materialized views  
  **Size:** M → T-1.3, T-1.5  
  Materialized views: `zone_statistics` (zone_id, median_price_m2, avg_days_on_market, listing_count, deal_count_tier1, deal_count_tier2, updated_at). Refresh function. Index on zone_id.  
  **Acceptance:** `REFRESH MATERIALIZED VIEW CONCURRENTLY zone_statistics;` completes. Query returns stats per zone.

- [ ] **T-1.11** — Create shared Pydantic models (Python)  
  **Size:** L  
  In `libs/common/models/`: `Listing`, `RawListing`, `NormalizedListing`, `PriceHistory`, `Zone`, `AlertRule`, `ScoringResult`, `ConversationState`, `Country`, `Portal`. Use Pydantic v2 with strict types. Add validators (price > 0, area > 0, valid country codes).  
  **Acceptance:** All models pass unit tests with valid and invalid data. JSON serialization/deserialization round-trips correctly.

- [ ] **T-1.12** — Create shared Go types  
  **Size:** M  
  In `pkg/models/`: Go structs mirroring key Pydantic models (Listing, AlertRule, ScoringResult, User). Use `pgx` compatible types. JSON tags for API serialization.  
  **Acceptance:** Go structs scan from PostgreSQL rows. JSON marshal matches Python Pydantic output.

---

## Epic 2 — API Gateway (Go)

> The public-facing REST API, authentication, rate limiting, and Stripe integration.

- [ ] **T-2.1** — API Gateway skeleton  
  **Size:** M → T-0.1.3  
  Create `services/api-gateway/cmd/main.go`. Set up `chi` router, structured logging (`slog`), graceful shutdown, health endpoint (`GET /healthz`), readiness endpoint (`GET /readyz`, checks DB + Redis + NATS). Load config from env vars via `viper`.  
  **Acceptance:** Service starts, `/healthz` returns 200. Dockerfile builds. Helm deployment works in K8s.

- [ ] **T-2.2** — PostgreSQL connection pool  
  **Size:** S → T-2.1  
  Set up `pgx` connection pool in api-gateway. Read replica connection for queries, primary for writes. Connection health check integrated into `/readyz`.  
  **Acceptance:** Pool connects to primary + replica. Query test succeeds. Pool stats exposed as Prometheus metric.

- [ ] **T-2.3** — Redis client setup  
  **Size:** XS → T-2.1  
  Initialize `go-redis` client. Used for: session cache, rate limit counters, hot data cache (zone stats, top deals).  
  **Acceptance:** Redis ping succeeds. Set/Get test key works.

- [ ] **T-2.4** — JWT authentication middleware  
  **Size:** M → T-2.1  
  Implement JWT middleware using `golang-jwt/jwt`. Access tokens (15min, HS256). Refresh tokens (7d, stored in Redis). Endpoints: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`. Password hashing with bcrypt (12 rounds).  
  **Acceptance:** Register → login → receive tokens → access protected endpoint → refresh token → logout. Unit tests for all flows. Invalid/expired tokens rejected with 401.

- [ ] **T-2.5** — Google OAuth2 login  
  **Size:** M → T-2.4  
  Implement `GET /auth/google` (redirect) and `GET /auth/google/callback`. Use Go stdlib `oauth2` package. Create or link user on first Google login.  
  **Acceptance:** Full OAuth2 flow works with Google. Existing email users linked correctly. New users created with Google ID.

- [ ] **T-2.6** — Rate limiting middleware  
  **Size:** S → T-2.3  
  Implement token-bucket rate limiting using Redis. Limits per subscription tier: Free (30 req/min), Basic (120), Pro (300), Global (600), API (1200). Return `429 Too Many Requests` with `Retry-After` header.  
  **Acceptance:** Rate limit enforced per user. Prometheus counter for rate-limited requests. Headers `X-RateLimit-Remaining` present.

- [ ] **T-2.7** — Listings API: search endpoint  
  **Size:** L → T-2.2, T-1.3  
  `GET /api/v1/listings` — Paginated search with filters: country, city, zone_id, property_category, property_type, min/max price, min/max area, bedrooms, deal_tier, status, source, sort_by (deal_score/price/recency/price_m2), sort_dir. Return unified JSON. Read from replica.  
  **Acceptance:** 20+ filter combinations tested. Pagination (cursor-based) works. Response < 500ms for 100k listings. Subscription tier gates applied (free = delayed data).

- [ ] **T-2.8** — Listings API: detail endpoint  
  **Size:** M → T-2.2, T-1.3  
  `GET /api/v1/listings/{id}` — Full listing detail including: all fields, price_history array, deal score + confidence, SHAP top 5 features (from JSONB), comparable listings (IDs + summary), zone stats.  
  **Acceptance:** Returns complete listing with nested objects. SHAP features formatted for frontend. 404 for missing ID.

- [ ] **T-2.9** — Zones API  
  **Size:** M → T-2.2, T-1.5  
  `GET /api/v1/zones` — List zones by country, level, parent_id. `GET /api/v1/zones/{id}` — Zone detail with stats. `GET /api/v1/zones/{id}/analytics` — Time-series price trends, volume, deal frequency. `GET /api/v1/zones/compare?ids=a,b,c` — Side-by-side comparison.  
  **Acceptance:** Zone hierarchy traversal works. Analytics returns 12-month time series. Comparison works cross-country.

- [ ] **T-2.10** — Countries & Portals API  
  **Size:** S → T-2.2  
  `GET /api/v1/countries` — Active countries with summary stats. `GET /api/v1/portals` — Active portals with status and health metrics.  
  **Acceptance:** Returns correct data. Admin-only endpoints for enable/disable.

- [ ] **T-2.11** — Alert Rules API  
  **Size:** M → T-2.4, T-1.7  
  CRUD: `GET /api/v1/alerts/rules`, `POST /api/v1/alerts/rules`, `PUT /api/v1/alerts/rules/{id}`, `DELETE /api/v1/alerts/rules/{id}`. `GET /api/v1/alerts/history` — Past triggered alerts with delivery status. Enforce max rules per subscription tier.  
  **Acceptance:** Full CRUD works. Tier limits enforced (free=0, basic=3, pro=unlimited). Alert history paginated.

- [ ] **T-2.12** — Stripe subscription integration  
  **Size:** XL → T-2.4  
  Implement Stripe Checkout session creation, webhook handler (`POST /webhooks/stripe`) for events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`. Update user subscription tier on events. Products/prices configured in Stripe dashboard.  
  **Acceptance:** Full subscription lifecycle: checkout → active → upgrade → downgrade → cancel. Webhook signature verification. Idempotent event processing.

- [ ] **T-2.13** — Currency conversion middleware  
  **Size:** S → T-2.2  
  Support `?currency=USD` query param on listings endpoints. Convert prices using `exchange_rates` table. Add header `X-Currency` and `X-Exchange-Rate-Date`.  
  **Acceptance:** Prices converted correctly. Unsupported currency returns 400. No conversion overhead when currency matches listing's native currency.

- [ ] **T-2.14** — OpenAPI documentation  
  **Size:** M → T-2.7 through T-2.11  
  Auto-generate OpenAPI 3.1 spec from handler annotations or write manually. Serve Swagger UI at `/api/docs`. Include all endpoints, auth schemes, request/response schemas.  
  **Acceptance:** Swagger UI accessible. All endpoints documented. "Try it out" works with valid JWT.

- [ ] **T-2.15** — gRPC clients to internal services  
  **Size:** M → T-0.1.5  
  Implement gRPC client connections from api-gateway to: `ml-scorer` (on-demand valuation), `ai-chat-service` (conversation management). Connection pooling, timeouts, circuit breaker (using `go-kit` or manual).  
  **Acceptance:** gRPC calls succeed between services in K8s. Timeout at 5s. Circuit breaker opens after 5 consecutive failures.

---

## Epic 3 — Scraping Infrastructure

> The Go orchestrator, Python spider framework, proxy manager, and first portal spider.

- [ ] **T-3.1** — Scrape orchestrator skeleton (Go)  
  **Size:** M → T-0.2.2  
  Create `services/scrape-orchestrator/`. Reads portal configuration from DB. Publishes scraping jobs to NATS `scraper.commands.{country}.{portal}` on configurable cron schedules (per portal). Tracks job status.  
  **Acceptance:** Orchestrator starts, reads 10 portals from DB, publishes jobs to NATS on schedule. Job status queryable via internal API.

- [ ] **T-3.2** — Proxy manager service (Go)  
  **Size:** L  
  Create `services/proxy-manager/`. gRPC service implementing `ProxyService` (GetProxy, ReportResult). Manages pool of residential proxy IPs per country. Rotation strategy: round-robin with health weighting. Blacklists IPs that receive 403/429. Sticky sessions for paginated crawls.  
  **Acceptance:** GetProxy returns healthy proxy for requested country. ReportResult with failure blacklists IP for 30min. Health stats exposed as Prometheus metrics.

- [ ] **T-3.3** — Spider worker base framework (Python)  
  **Size:** L → T-0.1.4, T-0.1.5  
  Create `services/spider-workers/`. Implement `BaseSpider` abstract class with methods: `scrape_search_page()`, `scrape_listing_detail()`, `detect_new_listings()`. NATS consumer that receives jobs from `scraper.commands.*`, dispatches to appropriate spider. gRPC client to proxy-manager for proxy assignment. Publishes raw listings to `raw.listings.{country}`.  
  **Acceptance:** Framework loads spider plugins dynamically. NATS consumer processes test job. Proxy assigned via gRPC. Raw listing published to NATS.

- [ ] **T-3.4** — Idealista Spain spider  
  **Size:** XL → T-3.3, T-3.2  
  Implement `IdealistaSpider(BaseSpider)` for `idealista.com`. Scrape search pages (paginated), listing detail pages. Parse all fields from FR-ACQ-040 table. Handle: mobile API endpoints (reverse-engineered), HTML fallback, pagination, photo URL extraction, geo-coordinates.  
  **Acceptance:** Scrapes 100+ listings from Idealista Spain. All schema fields populated where available. Data completeness > 80%. No blocks in 500-request test run (with proxies). Price, area, rooms, GPS correctly parsed.

- [ ] **T-3.5** — Fotocasa Spain spider  
  **Size:** XL → T-3.3, T-3.2  
  Implement `FotocasaSpider(BaseSpider)` for `fotocasa.es`. Same scope as T-3.4 but for Fotocasa's HTML/API structure.  
  **Acceptance:** Same criteria as T-3.4 but for Fotocasa.

- [ ] **T-3.6** — New listing detection mode  
  **Size:** L → T-3.4  
  Implement incremental polling in `IdealistaSpider.detect_new_listings()`. Sort by newest, compare against last-seen IDs in Redis, scrape only new ones. Runs every 15min for priority zones.  
  **Acceptance:** Detects new listings within 15min of publication on Idealista. No duplicate processing. Redis tracks last-seen state per zone.

- [ ] **T-3.7** — Scraping metrics & health dashboard  
  **Size:** M → T-3.1, T-0.2.6  
  Expose Prometheus metrics from orchestrator and spider workers: `listings_scraped_total{country,portal}`, `scrape_errors_total{country,portal,error_type}`, `scrape_duration_seconds`, `proxy_health_ratio{country}`, `proxy_blocks_total`. Create Grafana dashboard.  
  **Acceptance:** Grafana dashboard shows real-time scraping activity per portal/country. Alerts trigger when success rate drops below 80%.

---

## Epic 4 — Data Pipeline

> Normalizer, deduplicator, enricher, and change detector.

- [ ] **T-4.1** — Pipeline normalizer service  
  **Size:** L → T-1.11, T-0.2.2  
  Create `services/pipeline/normalizer/`. NATS consumer on `raw.listings.*`. Maps portal-specific fields to unified `NormalizedListing` Pydantic model. Currency normalization (to EUR), area normalization (to m²), property type mapping (per-country taxonomy table). Validates with Pydantic. Writes to PostgreSQL. Publishes to `normalized.listings`.  
  **Acceptance:** Processes raw Idealista listing → writes valid row to `listings` table. All field mappings correct. Invalid data quarantined (logged, not written). Data completeness score calculated.

- [ ] **T-4.2** — Pipeline deduplicator service  
  **Size:** L → T-4.1  
  Create `services/pipeline/deduplicator/`. NATS consumer on `normalized.listings`. Three-stage dedup: (1) PostGIS `ST_DWithin(location, location, 50)` for GPS proximity, (2) feature similarity (area ±10%, rooms match, type match), (3) `rapidfuzz` Levenshtein on normalized address (threshold > 85%). Merges duplicates: assigns `canonical_id`, keeps both source records. Publishes to `enriched.listings` stream (or next queue).  
  **Acceptance:** Two identical listings from Idealista + Fotocasa merged under same canonical_id. False positive rate < 5% on test set of 1000 listings.

- [ ] **T-4.3** — Pipeline enricher: Spain Catastro  
  **Size:** L → T-4.1  
  Implement `SpainCatastroEnricher(BaseEnricher)`. Calls Catastro INSPIRE WFS to get: cadastral reference, official built area, year of construction, building geometry. Flags area discrepancies (portal vs official > 10%). Updates listing in DB.  
  **Acceptance:** 80%+ of Madrid listings enriched with cadastral data. Area discrepancy flag correctly set. API rate limits respected (1 req/s).

- [ ] **T-4.4** — Pipeline enricher: POI distances  
  **Size:** M → T-4.1  
  Calculate distances from listing GPS to nearest: metro/train station, city center, coastline, green area (park). Use OpenStreetMap Overpass API or pre-loaded POI database. Store as listing fields.  
  **Acceptance:** Distances calculated for all listings with GPS coordinates. Metro distance verified against Google Maps for 10 sample listings (tolerance ±200m).

- [ ] **T-4.5** — Pipeline change detector  
  **Size:** M → T-4.1  
  Create `services/pipeline/change_detector/`. Runs on every scraping cycle. Compares current listing data with previous snapshot. Detects: price drops (inserts into `price_history`), delistings (sets `delisted_at`), re-listings, description changes. Publishes price drops to `price.changes` NATS stream.  
  **Acceptance:** Price drop of €10k detected and recorded in price_history. Delisting detected within one scraping cycle. No false positives on unchanged listings.

- [ ] **T-4.6** — Full pipeline integration test  
  **Size:** L → T-4.1 through T-4.5  
  End-to-end test: inject raw listing JSON into NATS → verify it flows through normalizer → dedup → enricher → appears in DB with all fields populated. Test with 100 sample listings from each supported portal.  
  **Acceptance:** 100% of valid listings arrive in DB. Pipeline latency < 30s per listing. No message loss (NATS JetStream ack verification).

---

## Epic 5 — ML Pipeline

> Feature engineering, model training, scoring service, and explainability.

- [ ] **T-5.1** — Feature engineering pipeline  
  **Size:** XL → T-1.3, T-4.3, T-4.4  
  Create `services/ml/features/`. Implement `FeatureEngineer` class that transforms a listing row into a feature vector. Features as defined in architecture doc §5.2. Handle missing values (median imputation for numerical, mode for categorical). One-hot encode categoricals. Cyclical encoding for month. Spatial features (distances). Zone-level aggregates (median price/m², listing density).  
  **Acceptance:** Feature vector generated for 10k Spanish listings. No NaN/Inf in output. Feature dimensions match spec (~35 features). Unit tests for each feature transformation.

- [ ] **T-5.2** — Model training pipeline  
  **Size:** XL → T-5.1  
  Create `services/ml/trainer/`. Implements: (1) Training data export from PostgreSQL (listings with known prices, sold or > 30 days on market). (2) Train/validation/test split (70/15/15, stratified by city). (3) LightGBM training with Optuna hyperparameter tuning (50 trials). (4) Evaluation metrics: MAE, MAPE, R², per city. (5) If MAPE improves: export to ONNX, register in MLflow, upload artifact to MinIO. (6) Record model version in DB.  
  **Acceptance:** Model trained on 10k+ Spanish listings. MAPE < 12% nationally, < 10% for Madrid/Barcelona. ONNX export loads in ONNX Runtime. MLflow shows experiment run.

- [ ] **T-5.3** — ML scorer service  
  **Size:** L → T-5.2, T-0.1.5  
  Create `services/ml/scorer/`. gRPC service implementing `MLScoringService`. Loads latest ONNX model per country from MinIO. NATS consumer on `enriched.listings`: batch-scores new listings. Computes: estimated_price, deal_score, deal_tier, confidence_low/high. Writes scores to DB. Publishes to `scored.listings`.  
  **Acceptance:** Scores a listing in < 100ms. Batch of 100 listings in < 3s. Model hot-reload when new version registered. gRPC endpoint works for on-demand scoring.

- [ ] **T-5.4** — SHAP explainability  
  **Size:** M → T-5.3  
  Integrate SHAP `TreeExplainer` for LightGBM. For Tier 1 and Tier 2 deals, compute top 5 SHAP features. Store as JSONB in listing row. Cache results (not recomputed unless model version changes).  
  **Acceptance:** SHAP top-5 features returned for Tier 1 deal. Feature names human-readable ("Zone median price pushes estimate up +€15,000"). Computation < 500ms per listing.

- [ ] **T-5.5** — Comparable properties finder  
  **Size:** M → T-5.1  
  Implement KNN search on feature space to find 5 most similar listings in the same zone. Uses scikit-learn `NearestNeighbors` with precomputed feature matrix per zone (cached in memory, refreshed hourly).  
  **Acceptance:** Returns 5 comps for a given listing. Comps are in the same city, similar area/rooms/type. Response < 200ms.

- [ ] **T-5.6** — ML training CronJob (K8s)  
  **Size:** S → T-5.2  
  Create K8s CronJob in Helm chart. Runs weekly (Sunday 3 AM UTC). Triggers `ml-trainer` container. On success: new model active. On failure: alert to Telegram/email + keeps previous model.  
  **Acceptance:** CronJob executes weekly. Success notification sent. Failure doesn't break scoring (previous model continues).

---

## Epic 6 — Alert Engine & Notifications

> Rule matching, multi-channel dispatch, and digest compilation.

- [ ] **T-6.1** — Alert engine service (Go)  
  **Size:** L → T-0.2.2, T-1.7  
  Create `services/alert-engine/`. NATS consumer on `scored.listings` and `price.changes`. For each event: (1) load active rules from Redis cache (refreshed every 60s from DB), (2) evaluate each rule: country match, PostGIS zone intersection, JSONB filter evaluation, tier match, (3) dedup check (Redis set of sent listing+user pairs), (4) instant rules → publish to `alerts.notifications`, (5) digest rules → buffer in Redis sorted set by user+frequency.  
  **Acceptance:** Scored listing matching 3 user rules → 3 notification events published. Non-matching rules skipped. Dedup prevents re-sending same listing.

- [ ] **T-6.2** — Alert dispatcher: email channel  
  **Size:** M → T-6.1  
  Implement email sending via AWS SES. HTML email template with: property photo, address, price, deal score badge, key features, CTA buttons ("View Analysis", "View on Portal"). Template in user's preferred language.  
  **Acceptance:** Email received within 30s of scored event. Renders correctly in Gmail/Outlook. Unsubscribe link works. Open/click tracking via pixel + redirect.

- [ ] **T-6.3** — Alert dispatcher: Telegram channel  
  **Size:** M → T-6.1  
  Implement Telegram Bot API integration. Message with: photo, formatted text (Markdown), inline keyboard buttons ("View", "Dismiss"). Bot registration: user sends `/start` with linking token.  
  **Acceptance:** Telegram message received within 15s. Photo renders. Buttons work. User linking flow complete.

- [ ] **T-6.4** — Alert dispatcher: WhatsApp channel  
  **Size:** M → T-6.1  
  Implement WhatsApp Business API via Twilio. Template message with: property summary, link. Requires pre-approved template.  
  **Acceptance:** WhatsApp message received. Template approved by Meta. Opt-in/opt-out flow works.

- [ ] **T-6.5** — Alert dispatcher: Push notifications  
  **Size:** M → T-6.1  
  Implement Firebase Cloud Messaging (FCM) for web push. Service worker in frontend for push subscription. Notification with title, body, image, click URL.  
  **Acceptance:** Browser push notification received. Click opens listing detail page. Permission request flow works.

- [ ] **T-6.6** — Alert dispatcher: Webhook channel  
  **Size:** S → T-6.1  
  HTTP POST to user-configured URL with JSON payload containing listing data + deal score. HMAC signature for verification. Retry 3x with exponential backoff.  
  **Acceptance:** Webhook delivered to test endpoint. Signature verifiable. Retry on 5xx.

- [ ] **T-6.7** — Digest compiler (Go)  
  **Size:** M → T-6.1, T-6.2  
  CronJob (hourly and daily). Reads buffered alerts from Redis per user+frequency. Compiles into ranked digest (sorted by deal_score desc, grouped by country). Sends as single email or Telegram message.  
  **Acceptance:** Daily digest email with 10 deals, ranked, grouped by country. Sent at user's preferred time (default 8 AM local).

---

## Epic 7 — AI Conversational Search

> The LLM-powered chat interface: backend service, WebSocket server, and frontend UI.

- [ ] **T-7.1** — AI chat service skeleton (Python)  
  **Size:** M → T-0.1.4, T-0.1.5  
  Create `services/ai-chat/`. gRPC service implementing `AIChatService`. Conversation state management (Redis). Session creation/loading. Turn counter. Subscription tier limits enforcement.  
  **Acceptance:** gRPC `Chat` streaming RPC works. Conversation created and retrieved. Turn counter increments.

- [ ] **T-7.2** — LLM provider abstraction layer  
  **Size:** L → T-7.1  
  Implement `BaseLLMProvider` interface with methods: `generate(messages, system_prompt) → stream[tokens]`. Concrete implementations: `ClaudeProvider` (Anthropic SDK), `OpenAIProvider` (OpenAI SDK), `LiteLLMProvider` (any model via LiteLLM). Provider selected via env var `LLM_PROVIDER`. Streaming support for all providers.  
  **Acceptance:** Same conversation produces coherent response from Claude, GPT-4o, and Llama-3 via LiteLLM. Token streaming works for all providers. Fallback to secondary provider on error.

- [ ] **T-7.3** — System prompt engineering  
  **Size:** L → T-7.2  
  Create `services/ai-chat/prompts/system_prompt.jinja2`. Defines: role (expert real estate advisor), available property types (injected from DB), available countries and zones, progressive refinement flow (10 dimensions), output format (chat message + structured JSON criteria + optional visual trigger). Localized instruction to respond in user's language.  
  **Acceptance:** Prompt tested with 10 diverse user inputs in 4 languages. Assistant follows flow, outputs valid JSON criteria, asks one question at a time. Context injection (zone stats, deal counts) works.

- [ ] **T-7.4** — Market context injection  
  **Size:** M → T-7.1, T-2.9  
  Before each LLM call, fetch relevant context: zone median prices, active listing count, deal counts per tier, recent price trends. Inject into prompt as structured data block. gRPC call to api-gateway for zone stats.  
  **Acceptance:** Assistant quotes correct zone median price in conversation. Suggests alternatives when budget doesn't match zone prices. Deal count mentioned is accurate.

- [ ] **T-7.5** — Criteria state parser  
  **Size:** M → T-7.3  
  Parse LLM response into: `chat_message` (string), `criteria_state` (CriteriaJSON), `visual_trigger` (optional), `suggested_chips` (list). Validate criteria against platform taxonomy. Handle malformed LLM output gracefully (retry once, fallback to text-only response).  
  **Acceptance:** Criteria JSON parsed correctly for 50 sample conversations. Invalid JSON handled without crash. All criteria fields validated against allowed values.

- [ ] **T-7.6** — Visual reference library  
  **Size:** L  
  Create `services/ai-chat/visual_refs/`. Database table or JSON config with curated images organized by tags: style (modern, classic, industrial, minimalist, rustic, Mediterranean), feature (terrace, garden, pool, views, open-plan), type (flat, house, loft, penthouse, warehouse, land). 200+ royalty-free images from Unsplash/Pexels. API endpoint to query by tags.  
  **Acceptance:** Query `style=industrial,type=loft` returns 4-5 relevant images. Images load < 1s. Library covers all property types and styles from FR-AI-070.

- [ ] **T-7.7** — Criteria finalization & search launch  
  **Size:** L → T-7.5, T-2.7, T-2.11  
  When `criteria_state.status == "ready"`: (1) build summary card JSON, (2) on user confirmation: convert criteria to search query → call Listings API → return results, (3) simultaneously create alert rule via Alert Rules API. Return both results and confirmation to frontend.  
  **Acceptance:** Full flow: chat → criteria ready → summary card → confirm → results + alert created. Alert rule matches conversation criteria exactly. Results sorted by deal score.

- [ ] **T-7.8** — WebSocket server: AI chat protocol (Go)  
  **Size:** L → T-7.1  
  Create `services/ws-server/`. WebSocket endpoint `/ws/chat`. Protocol: JSON messages with types (`chat_message`, `text_chunk`, `chips`, `image_carousel`, `criteria_summary`, `search_results`, `error`). Auth via JWT in initial handshake. Connection lifecycle management. Forwards to `ai-chat-service` via gRPC bidirectional streaming. Streams LLM tokens back to client.  
  **Acceptance:** WebSocket connects with JWT. User message → streamed response tokens appear in < 500ms. Image carousel message type works. Connection survives 30min idle (ping/pong). 1000 concurrent connections per pod.

- [ ] **T-7.9** — WebSocket server: real-time notifications  
  **Size:** M → T-7.8  
  Subscribe to `alerts.notifications` NATS stream filtered by connected user IDs. Push deal alerts to connected users in real-time via WebSocket.  
  **Acceptance:** User connected via WS receives deal alert within 5s of scoring, without needing email/Telegram.

---

## Epic 8 — Frontend

> Next.js application with AI chat, dashboard, listings, maps, and admin.

### 8.1 — Foundation

- [ ] **T-8.1.1** — Next.js project setup  
  **Size:** M  
  Initialize `frontend/` with Next.js 15, TypeScript, Tailwind CSS 4, shadcn/ui. Configure next-intl for 10 languages (en, es, fr, it, de, pt, nl, pl, sv, el). App Router with `[locale]` segment. Create layout with header, sidebar (collapsible), and main content area.  
  **Acceptance:** App renders in all 10 languages. Language switcher works. Layout responsive (mobile/tablet/desktop). Lighthouse performance > 90.

- [ ] **T-8.1.2** — Authentication (NextAuth.js)  
  **Size:** M → T-2.4, T-2.5  
  Configure NextAuth.js v5 with credentials provider (email/password via API) and Google OAuth. JWT session. Protected routes middleware. User context provider.  
  **Acceptance:** Login, register, Google OAuth flows work. Protected pages redirect to login. User info displayed in header.

- [ ] **T-8.1.3** — API client & React Query setup  
  **Size:** M → T-2.14  
  Create typed API client (`frontend/src/lib/api.ts`) auto-generated from OpenAPI spec. Configure TanStack Query for data fetching with caching, refetching, optimistic updates.  
  **Acceptance:** All API endpoints callable from frontend. Loading/error states handled. Cache invalidation on mutations.

- [ ] **T-8.1.4** — WebSocket client  
  **Size:** M → T-7.8  
  Create WebSocket client (`frontend/src/lib/ws.ts`). Auto-reconnect with exponential backoff. Message type dispatching. Integration with Zustand store for chat state and real-time notifications.  
  **Acceptance:** WS connects on app load (authenticated users). Reconnects after disconnect. Messages dispatched to correct handlers.

### 8.2 — AI Chat Interface (Home Page)

- [ ] **T-8.2.1** — Chat input component  
  **Size:** M  
  Create the main "¿Qué estás buscando?" input: large text area (auto-expanding), microphone button (voice input), send button. Placeholder localized. Centered on home page with search-engine-like prominence.  
  **Acceptance:** Input renders on `/`. Typing and sending messages works. Enter key sends. Shift+Enter for newline. Mobile-friendly.

- [ ] **T-8.2.2** — Voice input component  
  **Size:** L  
  Implement `VoiceInput.tsx`. Uses Web Speech API (`SpeechRecognition`) for browser-native STT. Fallback to Whisper API for unsupported browsers. Visual feedback: pulsing microphone during recording, waveform visualization. Auto-stop after 2s silence. Transcription shown in input before sending.  
  **Acceptance:** Voice input works in Chrome, Edge, Safari. Spanish, English, French recognized correctly. User can edit transcription before sending. Graceful degradation on unsupported browsers.

- [ ] **T-8.2.3** — Chat message components  
  **Size:** L  
  Create: `MessageBubble.tsx` (user + assistant variants), `ChipSelector.tsx` (tappable quick-reply buttons), `ImageCarousel.tsx` (horizontal scrolling image cards with "like this" / "not this" actions), `CriteriaSummaryCard.tsx` (final criteria display with edit buttons), `TypingIndicator.tsx` (streaming animation).  
  **Acceptance:** All components render correctly. Streaming text appears token-by-token. Chips send selection as message. Image carousel swipeable on mobile. Summary card fields editable.

- [ ] **T-8.2.4** — Chat window integration  
  **Size:** L → T-8.2.1, T-8.2.3, T-8.1.4  
  Create `ChatWindow.tsx`. Full conversation view with: message history, auto-scroll, typing indicator during LLM streaming, chips/images/summary inline. State managed in Zustand. Conversation list sidebar (recent conversations with preview snippets).  
  **Acceptance:** Full conversation flow works end-to-end: type message → see streamed response → tap chips → see images → review summary → launch search. Conversation history persists across page navigations.

- [ ] **T-8.2.5** — Search results inline display  
  **Size:** L → T-8.2.4, T-8.1.3  
  After criteria confirmation, display search results below the chat: listing cards with photo, price, deal score badge, key stats. "Show on map" toggle. Infinite scroll pagination. Sort controls.  
  **Acceptance:** Results appear within 2s of confirmation. Deal score badge color-coded by tier. Clicking card navigates to listing detail.

### 8.3 — Dashboard & Map

- [ ] **T-8.3.1** — Dashboard page  
  **Size:** XL  
  Create `/[locale]/dashboard`. Cards: total listings (by country), new today, Tier 1 deals today, recent price drops. Zone heatmap (MapLibre). Trend charts (Recharts): price/m² over time, listing volume, deal frequency. Country filter tabs.  
  **Acceptance:** Dashboard loads in < 3s. All cards show correct data. Heatmap renders zones with color intensity = deal frequency. Charts interactive (hover tooltips).

- [ ] **T-8.3.2** — Interactive map component  
  **Size:** XL  
  Create `Map.tsx` using MapLibre GL JS. Features: listings as color-coded pins (Tier 1=green, 2=blue, 3=gray, 4=red), clustering at zoom-out, popup on click (mini listing card), zone polygons overlay, "draw custom zone" tool, pan/zoom across countries.  
  **Acceptance:** 50k+ pins rendered without lag (clustering). Popup shows correct listing. Custom zone drawable and saveable. Mobile touch gestures work.

### 8.4 — Listings

- [ ] **T-8.4.1** — Listing search page  
  **Size:** XL  
  Create `/[locale]/search`. Filter sidebar: country, city, zone, property category/type, price range (slider), area range, bedrooms, deal tier, status, source portal. Results: card grid or list view toggle. Sort dropdown. Saved searches.  
  **Acceptance:** All filters work correctly and update URL params (shareable). Results update in real-time on filter change. Saved search CRUD works.

- [ ] **T-8.4.2** — Listing detail page  
  **Size:** XL  
  Create `/[locale]/listing/[id]`. Sections: photo gallery (lightbox), key stats bar, deal score card (with confidence range), SHAP explanation chart (horizontal bar), price history chart (line), comparable properties carousel, zone statistics card, mini-map with POIs, description (with translate button), listing metadata, CRM actions (favorite/contacted/visited/offer/discard), private notes textarea.  
  **Acceptance:** All sections render with correct data. Photo gallery swipeable. SHAP chart readable. Translate button calls DeepL and caches result. CRM status saved to DB.

### 8.5 — Zone Analytics & Portfolio

- [ ] **T-8.5.1** — Zone analytics page  
  **Size:** L  
  Create `/[locale]/zones/[id]`. Metrics: median price/m², trend (12mo), volume, avg days on market, inventory, price distribution histogram, deal frequency. Comparison tool (select up to 5 zones, side-by-side table + overlay charts).  
  **Acceptance:** Zone stats accurate. Comparison works cross-country. Charts interactive.

- [ ] **T-8.5.2** — Portfolio tracker page  
  **Size:** L  
  Create `/[locale]/portfolio`. Add owned properties (manual entry: address, purchase price, date, rental income). Dashboard: total invested, current estimated value (from ML model), unrealized gain/loss, rental yield. Multi-currency support.  
  **Acceptance:** CRUD for portfolio properties. Value estimates update when model retrains. Gain/loss calculation correct with currency conversion.

### 8.6 — Admin Panel

- [ ] **T-8.6.1** — Admin panel  
  **Size:** XL  
  Create `/[locale]/admin` (admin-only route). Tabs: Scraping Health (per portal/country: success %, listings/hr, blocks), ML Models (MAPE/MAE per country, model version history, manual retrain button), Users (list, subscription tier, activity), Countries (enable/disable, portal config), System (NATS queue depths, DB stats, Redis stats).  
  **Acceptance:** All admin data displays correctly. Manual model retrain triggers CronJob. Country enable/disable works. Admin-only access enforced.

---

## Epic 9 — Multi-Country Expansion

> Additional spiders, enrichment sources, and country-specific ML models.

- [ ] **T-9.1** — Immobiliare.it spider (Italy)  
  **Size:** XL → T-3.3  
  Implement spider for immobiliare.it. Italian field mapping. Parse all listing fields.  
  **Acceptance:** 1000+ Italian listings scraped. Field mapping correct. Price in EUR.

- [ ] **T-9.2** — SeLoger spider (France)  
  **Size:** XL → T-3.3  
  Implement spider for seloger.com. French field mapping (pièces → bedrooms conversion). Parse DPE energy rating.  
  **Acceptance:** 1000+ French listings scraped. "Pièces" correctly mapped. DPE → unified energy cert scale.

- [ ] **T-9.3** — LeBonCoin spider (France)  
  **Size:** XL → T-3.3  
  Implement spider for leboncoin.fr (immobilier section). Handle both professional and private listings.  
  **Acceptance:** 1000+ French listings. Private vs agency listings distinguished.

- [ ] **T-9.4** — France DVF enricher  
  **Size:** L  
  Implement `FranceDVFEnricher`. Import open transaction data from data.gouv.fr. Match by address proximity. Provides: actual historical sale prices for comparable properties.  
  **Acceptance:** DVF data loaded for Île-de-France. 60%+ of Paris listings enriched with nearby transaction prices.

- [ ] **T-9.5** — Rightmove spider (UK)  
  **Size:** XL → T-3.3  
  Implement spider for rightmove.co.uk. UK-specific fields (council tax band, leasehold/freehold, EPC rating). Prices in GBP.  
  **Acceptance:** 1000+ UK listings. GBP prices correctly stored and EUR-converted. Council tax band parsed.

- [ ] **T-9.6** — UK Land Registry enricher  
  **Size:** L  
  Implement `UKLandRegistryEnricher`. Import Price Paid Data (open CSV). Match by address. Provides: complete transaction history per property since 1995.  
  **Acceptance:** Land Registry data loaded for Greater London. 70%+ of London listings matched with transaction history.

- [ ] **T-9.7** — Zillow spider (USA)  
  **Size:** XL → T-3.3  
  Implement spider for zillow.com. US-specific fields (HOA fees, lot size in sqft, Zestimate reference). Prices in USD. Area in sqft (converted to m² internally).  
  **Acceptance:** 1000+ US listings (NYC metro). sqft→m² conversion correct. HOA fees parsed.

- [ ] **T-9.8** — Country-specific ML models  
  **Size:** XL → T-5.2  
  Train separate LightGBM models for Italy, France, UK, and US. Country-specific feature sets (DPE for France, council tax for UK, HOA for US). Evaluate MAPE per country.  
  **Acceptance:** MAPE < 12% for each country. Models registered in MLflow. Scorer loads correct model per country.

- [ ] **T-9.9** — Administrative zone import  
  **Size:** L → T-1.5  
  Import admin boundary polygons from OpenStreetMap/GADM for: Italy (regione→provincia→comune), France (région→département→commune→arrondissement), UK (region→county→district→ward), Netherlands (provincie→gemeente), USA (state→county→city). Store in zones table.  
  **Acceptance:** Zone hierarchy browsable for each country. PostGIS queries return correct zone for given GPS coordinates.

---

## Epic 10 — Polish & Launch

> Final features, performance optimization, and production hardening.

- [ ] **T-10.1** — Landing page & marketing site  
  **Size:** L  
  Create public landing page at `estategap.com`. Hero section with demo video, feature highlights, pricing table, testimonials, CTA to sign up. SEO optimized. Multilingual (at least EN/ES/FR).  
  **Acceptance:** Lighthouse SEO > 95. Page load < 2s. CTA links to app registration. Mobile responsive.

- [ ] **T-10.2** — Onboarding flow  
  **Size:** M  
  After registration: guided tour (3 steps). (1) "What are you looking for?" → AI chat, (2) "Set up your first alert", (3) "Explore the dashboard". Skippable. Shows subscription upgrade prompt at end.  
  **Acceptance:** Onboarding completes in < 2min. Skip works. Tour highlights UI elements correctly.

- [ ] **T-10.3** — Performance optimization  
  **Size:** L  
  Redis caching for: zone stats (TTL 5min), top deals (TTL 1min), user alert rules (TTL 60s). DB query optimization: verify all queries use indexes, `EXPLAIN ANALYZE` on slow queries. Frontend: Next.js ISR for zone pages, image lazy loading, bundle size < 200KB gzipped.  
  **Acceptance:** API p95 < 300ms on listing search. Dashboard load < 2s. DB query plans show index usage.

- [ ] **T-10.4** — Security hardening  
  **Size:** L  
  CORS whitelist configuration. CSP headers. SQL injection review (all queries parameterized). XSS prevention (React default + CSP). Secrets in K8s Sealed Secrets. Dependency scanning (pip-audit, govulncheck, npm audit) in CI. Rate limiting on auth endpoints (5 attempts/min).  
  **Acceptance:** OWASP ZAP scan shows no high/critical findings. All secrets encrypted at rest. Dependency scan clean.

- [ ] **T-10.5** — GDPR compliance implementation  
  **Size:** M  
  Cookie consent banner. Privacy policy page (all supported languages). Data export endpoint (`GET /api/v1/me/export`). Account deletion endpoint (`DELETE /api/v1/me` → cascade delete all data). Agent data removal request form.  
  **Acceptance:** Cookie consent works. Data export returns JSON with all user data. Account deletion removes all data within 24h. Deletion confirmed via email.

- [ ] **T-10.6** — Load testing  
  **Size:** L  
  K6 load test scripts for: listing search (1000 concurrent users), AI chat (100 concurrent conversations), alert dispatch (10k alerts in 5min), scraping pipeline (50k listings throughput). Identify bottlenecks. Tune HPA thresholds.  
  **Acceptance:** System handles target load without errors. HPA scales correctly. P99 latency within SLA. No OOM kills.

- [ ] **T-10.7** — Runbook & documentation  
  **Size:** M  
  Create `docs/runbook.md`: incident response procedures, common failure modes and fixes, scaling procedures, model retraining manual process, database backup/restore, disaster recovery plan. API documentation finalized.  
  **Acceptance:** Runbook covers all operational scenarios. Reviewed by operator. Backup restore tested successfully.

---

## Summary

| Epic | Tasks | Estimated Effort |
|---|---|---|
| 0 — Bootstrap & K8s | 14 | ~3 weeks |
| 1 — Database & Models | 12 | ~2 weeks |
| 2 — API Gateway (Go) | 15 | ~3 weeks |
| 3 — Scraping Infrastructure | 7 | ~3 weeks |
| 4 — Data Pipeline | 6 | ~2 weeks |
| 5 — ML Pipeline | 6 | ~2.5 weeks |
| 6 — Alerts & Notifications | 7 | ~2 weeks |
| 7 — AI Conversational Search | 9 | ~3 weeks |
| 8 — Frontend | 12 | ~5 weeks |
| 9 — Multi-Country Expansion | 9 | ~4 weeks |
| 10 — Polish & Launch | 7 | ~3 weeks |
| **Total** | **104 tasks** | **~32 weeks (part-time)** |

### SpecKit Workflow Mapping

```
Our Documents              →  SpecKit Phase
─────────────────────────────────────────────
functional-requirements.md →  /speckit.specify  (specification)
technical-architecture.md  →  /speckit.plan     (implementation plan)
THIS BACKLOG               →  /speckit.tasks    (task breakdown)
Code                       →  /speckit.implement (execute per task)
```

To use with SpecKit:
1. Place the requirements + architecture docs in your `.speckit/` spec directory.
2. Use this backlog as the task list (or let `/speckit.tasks` regenerate from the spec+plan).
3. Execute tasks sequentially within each epic: `/speckit.implement T-0.1.1`.
4. After each epic, validate against acceptance criteria before proceeding.
