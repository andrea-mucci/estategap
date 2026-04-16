# Tasks: Kubernetes Infrastructure

**Input**: Design documents from `specs/003-k8s-infrastructure/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/helm-values-schema.md ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to ([US1]–[US4])
- Exact file paths are included in every description

---

## Phase 1: Setup (Chart Fundamentals)

**Purpose**: Wire up the Helm chart skeleton and dependency manifest so all downstream phases can pull in sub-charts.

- [X] T001 Update `helm/estategap/Chart.yaml` — add full `dependencies` block: nats-io/nats, cloudnative-pg, bitnami/redis, kube-prometheus-stack, grafana/loki-stack, grafana/tempo, kedacore/keda
- [X] T002 Expand `helm/estategap/values.yaml` to the complete schema defined in `specs/003-k8s-infrastructure/contracts/helm-values-schema.md` — cluster identity, NATS, PostgreSQL, Redis, MinIO, observability, ArgoCD, and per-service resource blocks
- [X] T003 [P] Create `helm/estategap/values-staging.yaml` with staging overrides: single NATS replica, 1 PostgreSQL instance, reduced PVC sizes, `letsencrypt-staging` issuer
- [X] T004 [P] Create `helm/estategap/values-production.yaml` with production overrides: full replica counts, `letsencrypt-prod` issuer, pinned `image.tag` values
- [ ] T005 Run `helm dependency update` in `helm/estategap/` and commit the generated `helm/estategap/Chart.lock`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core manifests that every user story depends on — namespaces, shared config, helpers, security layer. No user story work can begin until this phase is complete.

**⚠️ CRITICAL**: All Phase 3–6 work is blocked until this phase is complete.

- [X] T006 Write `helm/estategap/templates/namespaces.yaml` — declare all 6 namespaces (estategap-system, estategap-gateway, estategap-scraping, estategap-pipeline, estategap-intelligence, estategap-notifications) with labels `app.kubernetes.io/managed-by: helm` and `estategap.io/tier: <tier>`
- [X] T007 [P] Write `helm/estategap/templates/configmap.yaml` — `estategap-config` ConfigMap in `estategap-system` with keys: `DATABASE_HOST`, `DATABASE_RO_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_SENTINEL_HOST`, `REDIS_SENTINEL_PORT`, `NATS_URL`, `MINIO_ENDPOINT`, and all five `MINIO_BUCKET_*` keys
- [X] T008 [P] Extend `helm/estategap/templates/_helpers.tpl` — add `estategap.namespace` helper (looks up `services.<name>.namespace` from values) and `estategap.serviceImage` helper (renders `repository:tag` with optional `global.imageRegistry` prefix)
- [X] T009 Write `helm/estategap/templates/sealed-secrets.yaml` — add SealedSecret CR template structure for `estategap-app-secrets` and `postgresql-backup-credentials`; include a comment block with the `kubeseal` commands from `specs/003-k8s-infrastructure/quickstart.md` to guide secret generation
- [X] T010 [P] Write `helm/estategap/templates/network-policies.yaml` — one NetworkPolicy per namespace enforcing the egress rules from `specs/003-k8s-infrastructure/data-model.md`: gateway → all; scraping/pipeline/intelligence → system only; notifications → system + gateway

**Checkpoint**: Run `helm template helm/estategap --dry-run` — must render namespaces, ConfigMap, and NetworkPolicies without errors.

---

## Phase 3: User Story 1 — Core Data Infrastructure (Priority: P1) 🎯 MVP

**Goal**: NATS JetStream (3 replicas, 8 streams), PostgreSQL 16 + PostGIS (primary + replica, 200Gi, daily backup to MinIO), Redis 7 (Sentinel, AOF), and MinIO (50Gi, 5 buckets) all deployed and verified via `helm install`.

**Independent Test**: From a temporary pod, `nats stream ls` shows 8 streams; `psql` returns `PostGIS 3.4+`; `redis-cli ping` returns `PONG`; `mc ls local/` shows 5 buckets. See `specs/003-k8s-infrastructure/quickstart.md` §6 for exact commands.

### Implementation for User Story 1

- [X] T011 [US1] Add NATS sub-chart configuration block to `helm/estategap/values.yaml` under the `nats:` key — enable JetStream, set `replicas: 3`, configure 10Gi PVC per replica, set `maxMemory: 1Gi` and `maxStorage: 10Gi`, expose ports 4222 (client) and 8222 (monitor)
- [X] T012 [P] [US1] Write `helm/estategap/templates/nats-streams-job.yaml` — Helm post-install/post-upgrade Job using `natsio/nats-box` image that idempotently creates all 8 streams from the `nats.streams` values list; Job must wait for NATS StatefulSet to be Ready before running; use `nats stream add --config` with a config file rendered from a ConfigMap
- [X] T013 [US1] Configure CloudNativePG Cluster CR: write `helm/estategap/templates/postgresql-cluster.yaml` — `instances: 2`, `storage.size: 200Gi`, `bootstrap.initdb.postInitSQL` running `CREATE EXTENSION IF NOT EXISTS postgis` and `CREATE EXTENSION IF NOT EXISTS postgis_topology`, `primaryUpdateStrategy: unsupervised`, and connection to `estategap-app-secrets` for passwords
- [X] T014 [P] [US1] Write `helm/estategap/templates/postgresql-backup.yaml` — CloudNativePG `ScheduledBackup` CR and `barmanObjectStore` config referencing `postgresql-backup-credentials` Secret, MinIO endpoint from ConfigMap, `schedule: "0 2 * * *"`, `retentionPolicy: "30d"`
- [X] T015 [P] [US1] Add Bitnami Redis sub-chart configuration to `helm/estategap/values.yaml` under the `redis:` key — `architecture: replication`, `sentinel.enabled: true`, `sentinel.quorum: 2`, `replicaCount: 1`, `master.persistence.size: 8Gi`, `master.resources.limits.memory: 1Gi`, `commonConfiguration` block with `maxmemory 1gb`, `maxmemory-policy allkeys-lru`, `appendonly yes`, `appendfsync everysec`, `existingSecret: redis-credentials`
- [X] T016 [US1] Write `helm/estategap/templates/minio.yaml` — MinIO StatefulSet (1 replica, 50Gi PVC), headless Service, ClusterIP Service exposing port 9000 (API) and 9001 (console); environment variables read from `minio-credentials` Sealed Secret; resource limits from values
- [X] T017 [P] [US1] Write `helm/estategap/templates/minio-setup-job.yaml` — Helm post-install/post-upgrade Job using `minio/mc` image that runs `mc mb --ignore-existing` for each bucket in `minio.buckets` values list; Job waits for MinIO pod Ready before running
- [ ] T018 [US1] Add Helm repo commands and `helm dependency update` step to `helm/estategap/Chart.yaml` comments; verify `helm install estategap helm/estategap --dry-run --values values.yaml --values values-staging.yaml` completes without errors

**Checkpoint**: Deploy to staging cluster; run all US1 smoke tests from `specs/003-k8s-infrastructure/quickstart.md` §6. All 5 checks must pass.

---

## Phase 4: User Story 2 — Observability Stack (Priority: P2)

**Goal**: Prometheus + Grafana + AlertManager (kube-prometheus-stack), Loki + Promtail DaemonSet, and Tempo deployed and accessible. Grafana shows live node metrics, logs from all namespaces, and accepts traces. Grafana reachable at `grafana.estategap.com`.

**Independent Test**: Access Grafana ingress; confirm Prometheus, Loki, and Tempo data sources all show green status; query logs for at least one pod from each application namespace.

### Implementation for User Story 2

- [X] T019 [P] [US2] Add `kube-prometheus-stack` sub-chart configuration to `helm/estategap/values.yaml` under `observability.prometheus:` — enable `prometheus.prometheusSpec.retention: 15d`, `prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage: 50Gi`, Grafana persistence 10Gi, Grafana admin secret from `grafana-credentials`, Grafana ingress disabled (handled by IngressRoute in US4), custom `additionalScrapeConfigs` with PodMonitor selectors for all 5 application namespaces
- [X] T020 [P] [US2] Add `loki-stack` sub-chart configuration to `helm/estategap/values.yaml` under `observability.loki:` — enable Loki with 20Gi PVC, enable Promtail DaemonSet with `extraVolumes` to mount `/var/log/pods` and `/var/lib/docker/containers`, configure Loki as log aggregation target
- [X] T021 [P] [US2] Add Tempo sub-chart configuration to `helm/estategap/values.yaml` under `observability.tempo:` — enable Tempo with 10Gi PVC, set receiver for OTLP gRPC (port 4317) and HTTP (port 4318), configure retention
- [X] T022 [US2] Write `helm/estategap/templates/grafana-datasources.yaml` — Kubernetes ConfigMap with Grafana datasource provisioning YAML (label `grafana_datasource: "1"`) defining three data sources: Prometheus at `http://prometheus-operated:9090`, Loki at `http://loki:3100`, Tempo at `http://tempo:3100` with trace-to-logs correlation enabled

**Checkpoint**: Deploy US2 changes; confirm Grafana at `grafana.estategap.com` shows all three data sources healthy and a node CPU dashboard is visible.

---

## Phase 5: User Story 3 — GitOps Continuous Deployment (Priority: P3)

**Goal**: ArgoCD Application CR deployed and pointing to `helm/estategap/` with `values-staging.yaml`. Auto-sync enabled so that merging a `values-staging.yaml` change triggers automatic cluster reconciliation within 3 minutes.

**Independent Test**: Edit any value in `values-staging.yaml`, commit and push to `main`. ArgoCD UI transitions from Synced → OutOfSync → Synced within 3 minutes without manual intervention.

### Implementation for User Story 3

- [X] T023 [US3] Write `helm/estategap/templates/argocd-application.yaml` — ArgoCD `Application` CR in namespace `argocd` (conditional on `argocd.enabled`); set `source.repoURL` from `argocd.repoURL` value, `targetRevision: main`, `path: helm/estategap`, `helm.valueFiles: [values-staging.yaml]`; set `destination.server: https://kubernetes.default.svc`, `destination.namespace: estategap-system`; `syncPolicy.automated.prune: false`, `syncPolicy.automated.selfHeal: true`
- [X] T024 [US3] Set `argocd.repoURL` in both `helm/estategap/values-staging.yaml` and `helm/estategap/values-production.yaml` to the actual repository URL; add validation comment noting this field is required
- [ ] T025 [US3] Apply the ArgoCD Application CR to the staging cluster via `kubectl apply` (one-time bootstrap); verify `argocd app get estategap-staging` shows `Synced` status; document this bootstrap step in `specs/003-k8s-infrastructure/quickstart.md` §5

**Checkpoint**: Push a whitespace-only change to `values-staging.yaml`; confirm ArgoCD auto-syncs within 3 minutes and `argocd app get estategap-staging` shows `Synced, Healthy`.

---

## Phase 6: User Story 4 — Application Service Helm Skeleton (Priority: P4)

**Goal**: All 9 application service templates render correctly in `helm template`, declaring Deployments, Services, HPAs (where applicable), and KEDA ScaledObject (spider-workers). All 6 namespaces receive correct Traefik IngressRoutes and TLS certificates. NetworkPolicies gate inter-namespace traffic correctly.

**Independent Test**: `helm template helm/estategap --values values.yaml --values values-staging.yaml` renders all 9 service Deployments, 3 IngressRoutes, 4 HPAs, 1 KEDA ScaledObject, and 1 Certificate without errors.

### Implementation for User Story 4

- [X] T026 [P] [US4] Write `helm/estategap/templates/certificates.yaml` — cert-manager `Certificate` CR covering domains `app.estategap.com`, `api.estategap.com`, `ws.estategap.com`, `grafana.estategap.com`; `issuerRef` reads from `cluster.certIssuer` value
- [X] T027 [US4] Write `helm/estategap/templates/ingress.yaml` — four Traefik `IngressRoute` CRs: `app.estategap.com → frontend:3000`, `api.estategap.com → api-gateway:8080`, `ws.estategap.com → websocket-server:8081` (with WebSocket upgrade middleware), `grafana.estategap.com → grafana:80`; include `Middleware` for HTTPS redirect and API rate limiting (100 req/s)
- [X] T028 [P] [US4] Write `helm/estategap/templates/services/api-gateway.yaml` — Deployment (namespace: estategap-gateway), ClusterIP Service (port 8080), `HorizontalPodAutoscaler` with `minReplicas: 2`, `maxReplicas: 20`, CPU target 60%; image from `services.api-gateway.image`, resources from `services.api-gateway.resources`
- [X] T029 [P] [US4] Write `helm/estategap/templates/services/websocket-server.yaml` — Deployment (namespace: estategap-gateway), ClusterIP Service (port 8081); image and resources from `services.websocket-server` values block
- [X] T030 [P] [US4] Write `helm/estategap/templates/services/alert-engine.yaml` — Deployment (namespace: estategap-notifications), ClusterIP Service; image and resources from `services.alert-engine` values block
- [X] T031 [P] [US4] Write `helm/estategap/templates/services/scrape-orchestrator.yaml` — Deployment (namespace: estategap-scraping), ClusterIP Service; image and resources from `services.scrape-orchestrator` values block
- [X] T032 [P] [US4] Write `helm/estategap/templates/services/spider-workers.yaml` — Deployment (namespace: estategap-scraping), ClusterIP Service; image and resources from `services.spider-workers` values block; no HPA (KEDA handles scaling)
- [X] T033 [P] [US4] Write `helm/estategap/templates/services/pipeline.yaml` — Deployment (namespace: estategap-pipeline), ClusterIP Service; image and resources from `services.pipeline` values block
- [X] T034 [P] [US4] Write `helm/estategap/templates/services/ml-scorer.yaml` — Deployment (namespace: estategap-intelligence), ClusterIP Service, `HorizontalPodAutoscaler` with `minReplicas: 1`, `maxReplicas: 10`, CPU target 70%; image and resources from `services.ml-scorer` values block
- [X] T035 [P] [US4] Write `helm/estategap/templates/services/ai-chat.yaml` — Deployment (namespace: estategap-intelligence), ClusterIP Service, `HorizontalPodAutoscaler` with `minReplicas: 1`, `maxReplicas: 8`, CPU target 60%; image and resources from `services.ai-chat` values block
- [X] T036 [P] [US4] Write `helm/estategap/templates/services/frontend.yaml` — Deployment (namespace: estategap-gateway), ClusterIP Service (port 3000); image and resources from `services.frontend` values block
- [X] T037 [US4] Write `helm/estategap/templates/keda-scaledobject.yaml` — KEDA `ScaledObject` targeting `spider-workers` Deployment; trigger type `nats-jetstream`, stream `scraper-commands`, consumer `spider-worker-group`, `lagThreshold: "100"`, `minReplicaCount: 1`, `maxReplicaCount: 50`; guard with `if .Values.services.spider-workers.keda.enabled`

**Checkpoint**: Run `helm template helm/estategap -f values.yaml -f values-staging.yaml | grep "kind:" | sort | uniq -c` — must show Deployment ×9, Service ×9+, HorizontalPodAutoscaler ×3, ScaledObject ×1, IngressRoute ×4, Certificate ×1, NetworkPolicy ×5.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: CI integration, smoke test automation, and final validation across all user stories.

- [ ] T038 [P] Add `helm lint` and `helm template --validate` steps to `.github/workflows/ci.yml` — run on every PR that touches `helm/` directory; fail the build on any lint error
- [X] T039 [P] Write `scripts/smoke-test.sh` — executable bash script that runs every verification command from `specs/003-k8s-infrastructure/quickstart.md` §6 (NATS stream count, PostGIS version, Redis PONG, MinIO bucket count, Grafana HTTP 200); exits non-zero on any failure
- [ ] T040 Run `helm install estategap helm/estategap --dry-run --debug -f values.yaml -f values-staging.yaml` end-to-end and resolve any template rendering errors
- [X] T041 [P] Add Helm deploy commands and prerequisite check commands to `CLAUDE.md` under a new `## Kubernetes / Helm` section so future contributors know how to bootstrap the cluster

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
  └── Phase 2 (Foundational) — blocked until Phase 1 complete
        ├── Phase 3 (US1 — Data Infrastructure)  ← start here for MVP
        ├── Phase 4 (US2 — Observability)         ← can run in parallel with US1 once Foundational done
        ├── Phase 5 (US3 — GitOps)                ← can run in parallel with US1/US2
        └── Phase 6 (US4 — App Skeleton)          ← can run in parallel with US1/US2/US3
              └── Phase 7 (Polish) — after all desired stories complete
```

### User Story Dependencies

| Story | Depends On | Can Parallelize With |
|-------|-----------|----------------------|
| US1 — Data Infrastructure | Phase 2 complete | US2, US3, US4 |
| US2 — Observability | Phase 2 complete | US1, US3, US4 |
| US3 — GitOps | Phase 2 complete, `argocd.repoURL` set | US1, US2, US4 |
| US4 — App Skeleton | Phase 2 complete | US1, US2, US3 |

### Within Each Phase

- T001 → T002 (values.yaml depends on Chart.yaml dependencies being finalized)
- T002 → T003, T004 (environment overrides extend base values)
- T005 requires T001 complete (`helm dependency update` needs `Chart.yaml`)
- T006–T010 can start as soon as Phase 1 completes (all touch different files)
- US1: T011 → T012 (NATS Job config references stream list from values); T013 → T014 (backup references cluster name from T013)
- US4: T026 → T027 (IngressRoute references TLS secret from Certificate); T028–T036 [P] are all independent service files

---

## Parallel Execution Examples

### Phase 2 (run all at once after Phase 1)

```
[P] T007 — configmap.yaml
[P] T008 — _helpers.tpl
[P] T010 — network-policies.yaml
    T006 — namespaces.yaml        (no ordering constraint, start with others)
    T009 — sealed-secrets.yaml   (no ordering constraint)
```

### Phase 3 — US1 (launch in parallel after T011)

```
[P] T012 — nats-streams-job.yaml
[P] T014 — postgresql-backup.yaml
[P] T015 — Redis values block
[P] T017 — minio-setup-job.yaml
    T013 — postgresql-cluster.yaml   (then T014 after T013)
    T016 — minio.yaml               (then T017 after T016)
```

### Phase 4 — US2 (all three sub-charts independent)

```
[P] T019 — kube-prometheus-stack values
[P] T020 — loki-stack values
[P] T021 — Tempo values
    T022 — grafana-datasources.yaml   (after T019–T021 settled)
```

### Phase 6 — US4 services (all 9 service files fully independent)

```
[P] T028 — api-gateway.yaml
[P] T029 — websocket-server.yaml
[P] T030 — alert-engine.yaml
[P] T031 — scrape-orchestrator.yaml
[P] T032 — spider-workers.yaml
[P] T033 — pipeline.yaml
[P] T034 — ml-scorer.yaml
[P] T035 — ai-chat.yaml
[P] T036 — frontend.yaml
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete **Phase 1** (T001–T005) — chart skeleton with dependencies
2. Complete **Phase 2** (T006–T010) — namespaces, config, security
3. Complete **Phase 3** (T011–T018) — NATS, PostgreSQL, Redis, MinIO
4. **STOP and VALIDATE**: run `scripts/smoke-test.sh` against staging cluster
5. All 5 data-tier smoke tests must pass before proceeding

### Incremental Delivery

1. Phase 1 + 2 → Chart deployable (empty services)
2. + Phase 3 → Data infrastructure live **(MVP)**
3. + Phase 4 → Observability live, metrics and logs visible
4. + Phase 5 → GitOps active, every merge auto-deploys
5. + Phase 6 → All application service slots available for team to fill
6. + Phase 7 → CI gated, smoke tests automated

### Parallel Team Strategy

Once Phase 2 is complete, four work streams can proceed simultaneously:

- **Engineer A**: Phase 3 (US1 — data infrastructure, highest priority)
- **Engineer B**: Phase 4 (US2 — observability)
- **Engineer C**: Phase 5 (US3 — ArgoCD)
- **Engineer D**: Phase 6 (US4 — service templates, all files independent)

---

## Notes

- `[P]` tasks touch different files and have no shared in-flight dependencies — safe to run concurrently
- `[US1]–[US4]` labels map each task to the user story in `specs/003-k8s-infrastructure/spec.md`
- Sealed Secrets (T009) are a template structure only — actual sealed values must be generated out-of-band using `kubeseal` per `quickstart.md` §1 before `helm install`
- `helm dependency update` (T005) must be re-run whenever `Chart.yaml` dependency versions change
- Commit after each Phase checkpoint to keep git history aligned with verified states
- KEDA ScaledObject (T037) will not activate until actual NATS JetStream streams exist (Phase 3 must precede Phase 6 testing)
