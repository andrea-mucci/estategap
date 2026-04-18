# Tasks: Helm Chart Values Documentation

**Input**: Design documents from `specs/036-helm-values-documentation/`
**Branch**: `036-helm-values-documentation`
**Plan**: plan.md | **Spec**: spec.md | **Research**: research.md | **Quick Start draft**: quickstart.md

**Organization**: Tasks grouped by user story for independent implementation and testing.
No tests requested — this is a pure documentation feature.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared-file conflicts)
- **[Story]**: User story label [US1]–[US5]
- All file paths are relative to the repository root

---

## Phase 1: Foundational — Annotate values.yaml

**Purpose**: Add `# --` inline comments to every key in `helm/estategap/values.yaml`. This is a
prerequisite for all HELM_VALUES.md sections (writers need annotated values for accuracy) and
directly fulfills US2 (look up any value without reading source).

**⚠️ CRITICAL**: Every task in this phase edits the same file (`helm/estategap/values.yaml`) and
must be executed sequentially. Work top-to-bottom through the file.

**Comment convention** (apply consistently to every key):
```yaml
# -- One-line description of what this value controls.
# Type: string | int | bool | object | list
# Required: yes | no
# Default: "value" (or: none — must be provided)
# Example: "value"   ← only for non-obvious values
key: value
```

- [x] T001 Annotate `global` and `cluster` sections in `helm/estategap/values.yaml` — 6 keys: `global.storageClass`, `global.imageRegistry`, `global.imagePullSecrets`, `cluster.environment` (note enum: test/staging/production), `cluster.domain`, `cluster.certIssuer`

- [x] T002 Annotate `components` section in `helm/estategap/values.yaml` — 6 deploy-toggle keys: `components.redis.deploy`, `components.mlflow.deploy`, `components.kafka.deploy`, `components.postgresql.deploy`, `components.prometheus.deploy`, `components.grafana.deploy`; each comment must explain what the flag controls and its implication (e.g. "always false — Kafka is an external shared-cluster service")

- [x] T003 Annotate `kafka` section in `helm/estategap/values.yaml` — 13 keys: `brokers` (required, note it feeds KAFKA_BROKERS env), `topicPrefix`, `tls.enabled`, `tls.caSecret`, `sasl.enabled`, `sasl.mechanism` (note valid values: PLAIN/SCRAM-SHA-256/SCRAM-SHA-512), `sasl.credentialsSecret` (note required keys: KAFKA_SASL_USERNAME, KAFKA_SASL_PASSWORD), `consumer.maxRetries`, `topicInit.enabled`, `topicInit.replicationFactor`, `topicInit.image.repository`, `topicInit.image.tag`, `deadLetter.enabled`, `deadLetter.retentionDays`

- [x] T004 Annotate `postgresql` section in `helm/estategap/values.yaml` — 11 keys: `external.host` (required), `external.port`, `external.database` (required), `external.sslmode` (note valid values: disable/require/verify-ca/verify-full), `external.credentialsSecret` (required, note keys: PGUSER, PGPASSWORD used by migration Job via envFrom), `readReplica.enabled`, `readReplica.host`, `readReplica.port`, `migrations.enabled`, `migrations.image` (note: must contain Alembic + migration scripts), `migrations.timeout`

- [x] T005 Annotate `redis` section in `helm/estategap/values.yaml` — 13 keys (Bitnami sub-chart pass-through): `fullnameOverride` (note: must stay "redis" — all services use redis.estategap-system.svc.cluster.local), `architecture`, `auth.enabled`, `auth.existingSecret`, `auth.existingSecretPasswordKey`, `sentinel.enabled`, `sentinel.quorum`, `master.persistence.size`, `master.resources.requests/limits`, `replica.replicaCount`, `replica.persistence.size`, `replica.resources.requests/limits`, `commonConfiguration` (note: multiline Redis config block)

- [x] T006 Annotate `s3` section in `helm/estategap/values.yaml` — 10 keys: `endpoint` (required, must be https URL, example: Hetzner endpoint), `region` (required), `bucketPrefix` (required, note: prepended to all bucket names), `forcePathStyle` (required true for Hetzner/MinIO-compatible storage), `credentialsSecret` (required, note exact keys: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY), `buckets.mlModels`, `buckets.trainingData`, `buckets.listingPhotos`, `buckets.exports`, `buckets.backups`

- [x] T007 Annotate `prometheus`, `grafana`, `keda`, `argocd` sections in `helm/estategap/values.yaml` — 13 keys total: `prometheus.serviceMonitor.enabled`, `prometheus.serviceMonitor.interval`, `prometheus.serviceMonitor.labels` (note: `release` label must match Prometheus operator's serviceMonitorSelector), `prometheus.rules.enabled`, `prometheus.rules.labels`, `grafana.dashboards.enabled`, `grafana.dashboards.namespace` (note: must match the namespace the Grafana sidecar watches), `grafana.dashboards.labels`, `keda.enabled`, `argocd.enabled`, `argocd.applicationName`, `argocd.repoURL` (note: required if argocd.enabled), `argocd.targetRevision`, `argocd.valueFiles`, `argocd.syncPolicy.prune`, `argocd.syncPolicy.selfHeal`

- [x] T008 Annotate `sealedSecrets` section in `helm/estategap/values.yaml` — Add a block comment before the section explaining the Sealed Secrets workflow (kubeseal encrypts → placeholder replaced → SealedSecret CR creates K8s Secret). Then annotate each subsection (`appSecrets`, `apiGatewaySecrets`, `productionHardeningSecrets`, `redisCredentials`, `s3Credentials`, `grafanaCredentials`, `mlTrainerSecrets`, `mlScorerSecrets`, `aiChatSecrets`, `alertEngineSecrets`, `alertDispatcherSecrets`) with: which Secret it creates, which namespace it lands in, which service consumes it, and a note that every leaf value must be replaced with `kubeseal --raw` output.

- [x] T009 Annotate `stripe` section in `helm/estategap/values.yaml` — 11 keys: `successUrl`, `cancelUrl`, `portalReturnUrl` (all note: must be full HTTPS URLs), then 8 `price*` keys (note: obtain IDs from Stripe Dashboard → Products)

- [x] T010 Annotate `mlTrainer` and `mlScorer` sections in `helm/estategap/values.yaml` — `mlTrainer`: `image.repository`, `image.tag`, `schedule` (note: cron syntax, default Sunday 3 AM), `prometheusPushgatewayUrl` (optional, empty disables metrics push), `resources.requests.memory/cpu`, `resources.limits.memory/cpu`; `mlScorer`: `grpcPort`, `prometheusPort`, `batchSize`, `batchFlushSeconds`, `modelPollIntervalSeconds`, `comparablesRefreshIntervalSeconds`, `shapTimeoutSeconds` (float, max seconds allowed for SHAP computation before timeout)

- [x] T011 Annotate `gdpr` and `loadTests` sections in `helm/estategap/values.yaml` — `gdpr.hardDeleteCron`: `enabled`, `schedule`, `successfulJobsHistoryLimit`, `failedJobsHistoryLimit`, `database.host/port`, `database.userSecretRef`, `database.passwordSecretRef`, `database.databaseSecretRef`, `redis.host/port`, `redis.passwordSecretRef`; `loadTests`: `enabled` (note: always false in production), `namespace`, `image.repository/tag`, `apiBaseUrl`, `wsUrl`, `alertsTriggerUrl`, `pipelineHttpPublishUrl`, `prometheusRemoteWriteUrl`

- [x] T012 Annotate `services.api-gateway` in `helm/estategap/values.yaml` — Add a block comment before the `services:` key explaining the common sub-key pattern (enabled, namespace, replicaCount, port, image, resources, env, livenessProbe, readinessProbe, serviceMonitor, hpa). Then annotate all `api-gateway` keys: `enabled`, `namespace`, `replicaCount`, `port`, `image.repository/tag`, `resources`, `env.*` (each env key: note whether it comes from ConfigMap, Secret, or inline value), `livenessProbe`, `readinessProbe`, `serviceMonitor`, `hpa.enabled/minReplicas/maxReplicas/cpuTarget`

- [x] T013 Annotate `services.websocket-server`, `services.alert-engine`, `services.alert-dispatcher` in `helm/estategap/values.yaml` — Focus on unique sub-keys: `alert-dispatcher.config.*` (logLevel, healthPort, baseUrl, workerPoolSize, batchSize, awsRegion, awsSesFromAddress, awsSesFromName); standard keys (port, image, resources, probes, serviceMonitor) can reference the api-gateway annotation pattern with shortened descriptions

- [x] T014 Annotate `services.scrape-orchestrator`, `services.proxy-manager`, `services.spider-workers` in `helm/estategap/values.yaml` — Unique keys: `proxy-manager.metricsPort`, `proxy-manager.env.PROXY_*` (note: replace-me values must be replaced with actual proxy credentials and must never be committed as plain values — use Sealed Secrets); `spider-workers.keda.*` (enabled, minReplicas, maxReplicas, stream, consumer, lagThreshold — note: lagThreshold is string type)

- [x] T015 Annotate `services.pipeline`, `services.pipeline-enricher`, `services.pipeline-change-detector`, `services.ml-scorer`, `services.ai-chat`, `services.frontend` in `helm/estategap/values.yaml` — Unique keys: `pipeline-enricher.command`, `pipeline-change-detector.command` (note: overrides Docker ENTRYPOINT), `ml-scorer.hpa`, `ai-chat.metricsPort`, `ai-chat.env.LLM_PROVIDER/FALLBACK_LLM_PROVIDER/LITELLM_MODEL` (note: LLM provider selection), `ai-chat.livenessProbe`/`readinessProbe` (mixed HTTP + TCP pattern)

**Checkpoint**: `grep -c "^# --" helm/estategap/values.yaml` should be ≥ 150. Run `helm lint helm/estategap -f helm/estategap/values.yaml` to confirm YAML is still valid.

---

## Phase 2: User Story 1 — Deploy from Scratch (Priority: P1) 🎯 MVP

**Goal**: A new operator can follow HELM_VALUES.md Quick Start end-to-end and deploy a working cluster without reading any source code.

**Independent Test**: Following only `helm/estategap/HELM_VALUES.md` Section 1 and Section 4, an operator can create all required Secrets and complete `helm install` successfully.

- [x] T016 [US1] Write HELM_VALUES.md Section 1 (Quick Start) in `helm/estategap/HELM_VALUES.md` — Use `specs/036-helm-values-documentation/quickstart.md` as the content source. Section must include: prerequisites checklist, Step 1 (kubectl create secret commands for all 8 required Secrets with exact key names), Step 2 (minimal values-override.yaml with only required fields, copy-paste ready), Step 3 (helm repo add + helm dependency update + helm install command with --namespace --create-namespace --wait --timeout), Step 4 (verification commands: kubectl get pods, helm status, kubectl get jobs, kubectl get servicemonitor)

- [x] T017 [US1] Write HELM_VALUES.md Section 4 (Security Configuration) in `helm/estategap/HELM_VALUES.md` — Must include: (a) Required Secrets table with columns: Secret Name | Namespace | Required Keys | Used By — covering all 8 Secrets from research.md §2; (b) `kubectl create secret generic` command for each Secret with exact `--from-literal` key names; (c) Sealed Secrets integration subsection explaining how to replace kubectl commands with kubeseal workflow; (d) TLS/Ingress subsection explaining `cluster.certIssuer` and cert-manager integration; (e) Network policies subsection explaining the 5 egress policies per namespace tier (gateway: unrestricted; scraping/pipeline/intelligence: only to estategap-system + DNS; notifications: only to estategap-system + gateway + DNS)

- [x] T018 [P] [US1] Create `helm/estategap/README.md` — Short file (≤ 60 lines) with: chart name ("EstateGap"), one-line description, minimum requirements (Helm 3.14+, Kubernetes 1.28+, cert-manager, Prometheus operator ≥ 0.63, KEDA 2.x), quick install snippet (3-line helm install), link to `HELM_VALUES.md` for full reference, link to specific sections (Quick Start, Troubleshooting)

**Checkpoint**: `helm lint helm/estategap -f helm/estategap/values.yaml` still passes. README.md exists. HELM_VALUES.md contains Sections 1 and 4 with copy-paste kubectl commands.

---

## Phase 3: User Story 2 — Look Up Any Value (Priority: P1)

**Goal**: For any value in values.yaml or HELM_VALUES.md, an operator can find description, type, default, required status, and example within 30 seconds.

**Independent Test**: Pick any 5 random keys from values.yaml — each has an inline `# --` comment. Find those same keys in HELM_VALUES.md Section 2 or 3 table — each has a description, type, default, and required flag.

- [x] T019 [US2] Write HELM_VALUES.md Section 2 (External Services Reference) in `helm/estategap/HELM_VALUES.md` — Five subsections (Kafka, PostgreSQL, S3 Object Storage, Prometheus, Grafana), each containing: (a) values table: Value Path | Description | Type | Default | Required; (b) Authentication subsection showing secret format; (c) connection verification command (e.g. `kubectl exec -n kafka deploy/kafka-client -- kafka-topics.sh --bootstrap-server <broker> --list`); (d) troubleshooting mini-table with 2-3 common errors and fixes. Use research.md §2 for secret key names and research.md §3 for value inventory.

- [x] T020 [US2] Write HELM_VALUES.md Section 3 (Application Services Reference) in `helm/estategap/HELM_VALUES.md` — (a) Services overview table: Service | Namespace | Port | Metrics Port | Liveness | Readiness | HPA | KEDA — all 13 services; (b) Common environment variables section listing all vars injected via `estategap.commonEnv` helper (DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_SSLMODE, DATABASE_RO_HOST/PORT if readReplica enabled, REDIS_HOST, REDIS_PORT, REDIS_SENTINEL_HOST/PORT, KAFKA_BROKERS, KAFKA_TOPIC_PREFIX, KAFKA_TLS_ENABLED, KAFKA_MAX_RETRIES, S3_ENDPOINT, S3_REGION, S3_BUCKET_PREFIX, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY); (c) Per-service subsection for services with unique env (api-gateway, alert-engine, alert-dispatcher, ai-chat, spider-workers, proxy-manager) listing service-specific env vars with their sources (ConfigMap key, Secret key, or inline)

- [x] T021 [P] [US2] Write HELM_VALUES.md Section 5 (Observability Configuration) in `helm/estategap/HELM_VALUES.md` — (a) ServiceMonitor setup: explain that `prometheus.serviceMonitor.labels.release` must match the Prometheus operator's `serviceMonitorSelector`; show how to find the selector (`kubectl get prometheus -A -o jsonpath='{.items[*].spec.serviceMonitorSelector}'`); (b) Verification: `kubectl get servicemonitor -A -l app.kubernetes.io/part-of=estategap` and Prometheus targets UI check; (c) Grafana dashboards: explain ConfigMap sidecar pattern, `grafana.dashboards.namespace` must match sidecar watched namespace, verification command; (d) PrometheusRule alert table: Alert Name | Group | Condition | Threshold | For — all 7 rules from `prometheus-rules.yaml`; (e) Log format: all services emit structured JSON via slog (Go) or structlog (Python), key fields: `time`, `level`, `msg`, `service`, `trace_id`

- [x] T022 [P] [US2] Write HELM_VALUES.md Section 6 (Feature Flags) in `helm/estategap/HELM_VALUES.md` — (a) `components.*.deploy` flags table: Flag | Default | What it deploys | Implication of false — for all 6 flags (redis: keep true always; mlflow: reserved, keep true; kafka/postgresql/prometheus/grafana: always false — external services); (b) Template rendering explanation: how `{{- if .Values.components.X.deploy }}` gates template rendering, with example; (c) Service `enabled` flags: explain `services.*.enabled` independently enables/disables each application service; (d) Dependency matrix table: Service | Needs PostgreSQL | Needs Kafka | Needs Redis | Needs S3 | Needs MLflow — for all 13 services

**Checkpoint**: HELM_VALUES.md Sections 2, 3, 5, 6 are complete. Every value in values.yaml appears in at least one section of HELM_VALUES.md.

---

## Phase 4: User Story 3 — Troubleshoot a Failed Deployment (Priority: P2)

**Goal**: An operator with a failing deployment can find the root cause and fix within 5 minutes using HELM_VALUES.md Section 9.

**Independent Test**: Each of the 10 error scenarios has a symptom, at least one diagnostic command, root causes list, and fix.

- [x] T023 [US3] Write HELM_VALUES.md Section 9 (Troubleshooting) in `helm/estategap/HELM_VALUES.md` — Cover all 10 errors from research.md §8, each formatted as: **Error**: symptom text / **Diagnose**: `kubectl` commands / **Root causes**: bullet list / **Fix**: step-by-step. Errors: (1) CrashLoopBackOff: estategap-db-credentials missing; (2) CrashLoopBackOff: api-gateway-secrets missing; (3) Database connection refused (covers: wrong host, SSL mismatch, network policy, credentials); (4) Kafka consumer not receiving (covers: wrong broker, SASL, topic not created, consumer group); (5) S3 access denied (covers: wrong credentials, bucket doesn't exist, wrong endpoint, path-style); (6) ServiceMonitor targets not appearing in Prometheus (covers: label selector mismatch on `release:` label); (7) Grafana dashboards missing (covers: wrong namespace, sidecar not watching label); (8) Migration Job backoffLimit exceeded (covers: schema already at head, DB unreachable, credentials); (9) Spider-workers not scaling via KEDA (covers: KEDA not installed, wrong topic name, wrong consumer group label); (10) TLS certificate not issued (covers: cert-manager issuer name mismatch, ACME rate limit, wrong domain)

**Checkpoint**: HELM_VALUES.md Section 9 exists with 10 error entries. Each entry has at least one copy-paste `kubectl` diagnostic command.

---

## Phase 5: User Story 4 — Scale the Deployment (Priority: P2)

**Goal**: An operator can pick a scaling profile (Small/Medium/Large) from HELM_VALUES.md and apply it as a valid values override.

**Independent Test**: Values from any scaling profile, when applied via `--set` or override file, produce zero `helm lint` errors.

- [x] T024 [US4] Write HELM_VALUES.md Section 7 (Scaling Guide) in `helm/estategap/HELM_VALUES.md` — (a) Three-tier summary table: Profile | Listings | Countries | api-gateway | spider-workers | ml-scorer | pipeline | Redis (as specified in plan.md); (b) Per-service detail subsection for each tier showing concrete values.yaml snippets with `replicaCount`, `resources.requests/limits`, `hpa.minReplicas/maxReplicas`; (c) Small profile: single-replica, minimal resources (api-gateway: 1 replica 256Mi, spider-workers: 1 replica 512Mi, ml-scorer: 1 replica 512Mi, pipeline: 1 replica 512Mi); (d) Medium profile: 2-3 replicas, doubled memory; (e) Large profile: HPA enabled on all services, 3+ replicas, multi-Gi memory, KEDA lagThreshold tuned to 50; (f) Redis sizing subsection: memory limit recommendations per tier with `commonConfiguration maxmemory` value; (g) Note: `helm lint` validation command to verify override file is valid

**Checkpoint**: HELM_VALUES.md Section 7 exists with all 3 tiers and concrete values snippets.

---

## Phase 6: User Story 5 — Schema Validation (Priority: P2)

**Goal**: `helm install` with invalid or missing required values produces a clear schema validation error naming the exact field.

**Independent Test**: `helm lint helm/estategap --set postgresql.external.sslmode=optional` fails with an enum error. `helm lint helm/estategap --set kafka.brokers=""` fails with a minLength error.

- [x] T025 [US5] Enhance `helm/estategap/values.schema.json` — Targeted additions to the existing schema (do not remove existing validations): (a) In `kafka` $def: add `"required": ["brokers"]`; add `"pattern": "^[a-z0-9._-]+(:[0-9]+)?(,[a-z0-9._-]+(:[0-9]+)?)*$"` to `brokers`; add `"pattern": "^[a-z0-9._-]+$"` to `topicPrefix`; add `"enum": ["PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"]` to `sasl.mechanism`; (b) In `postgresql` $def → `external`: add `"required": ["host", "database", "credentialsSecret"]`; add `"enum": ["disable", "require", "verify-ca", "verify-full"]` to `sslmode`; (c) In `s3` $def: add `"required": ["endpoint", "region", "bucketPrefix", "credentialsSecret"]`; add `"pattern": "^https?://"` to `endpoint`; (d) Verify `cluster.environment` enum `["test", "staging", "production"]` is enforced (already exists — confirm)

- [x] T026 [US5] Validate schema against all value profiles in the repository — Run and confirm zero errors: `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml`; `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-test.yaml`; confirm schema rejects invalid values: `helm lint helm/estategap --set postgresql.external.sslmode=optional` (must fail); `helm lint helm/estategap --set kafka.sasl.mechanism=GSSAPI` (must fail). Fix any schema constraint that incorrectly blocks a valid existing profile.

**Checkpoint**: `helm lint` passes for all existing profiles. Invalid enum/pattern values produce errors naming the exact field.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete the remaining HELM_VALUES.md sections, add Table of Contents, and run full end-to-end validation.

- [x] T027 [P] Write HELM_VALUES.md Section 8 (Migration Guide v2 → v3) in `helm/estategap/HELM_VALUES.md` — (a) Pre-migration checklist (cluster prerequisites: cert-manager, Prometheus operator ≥ 0.63, KEDA 2.x; Secrets created; S3 buckets created with legacy MinIO names; Kafka topics exist or topicInit will create them); (b) values.yaml diff table: Key | v2 (removed) | v3 (replacement) — covering: NATS → kafka.brokers, CloudNativePG sub-chart → postgresql.external.*, MinIO sub-chart → s3.endpoint + s3.credentialsSecret, kube-prometheus-stack sub-chart → prometheus.serviceMonitor.labels, Grafana sub-chart → grafana.dashboards.namespace; (c) Data migration steps: "None required — schema and data are unchanged by 033-035 brownfield migration"; (d) Rollback procedure: `helm rollback estategap -n estategap-system` + note that rolling back to v2 requires re-creating sub-chart PVCs

- [x] T028 Assemble the complete `helm/estategap/HELM_VALUES.md` file — Ensure all 9 sections are present in the correct order with the Table of Contents at the top (as defined in plan.md). Add section header anchors matching the ToC links. Sections: 1. Quick Start, 2. External Services, 3. Application Services, 4. Security, 5. Observability, 6. Feature Flags, 7. Scaling Guide, 8. Migration Guide, 9. Troubleshooting. Verify each section has at least one fenced code block with a copy-paste-ready example.

- [ ] T029 Run final end-to-end validation — Execute all verification commands from plan.md: (1) `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml` must pass; (2) `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-test.yaml` must pass; (3) `helm template estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml > /dev/null` must succeed; (4) Count annotated keys: `grep -c "^# --" helm/estategap/values.yaml` — must be ≥ 150; (5) Confirm README.md exists at `helm/estategap/README.md`; (6) Confirm HELM_VALUES.md contains all 9 section headings. Fix any issues found.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational)**: No dependencies — start immediately
- **Phase 2 (US1)**: T016-T017 depend on Phase 1 completion (annotated values inform accurate secret key documentation); T018 [README] can start in parallel with Phase 1
- **Phase 3 (US2)**: Depends on Phase 1 completion (annotated values as reference for table content)
- **Phase 4 (US3)**: Independent of Phases 2-3 — can start after Phase 1
- **Phase 5 (US4)**: Independent of Phases 2-4 — can start after Phase 1
- **Phase 6 (US5)**: T025 (schema) is independent; T026 (validation) depends on T025 + all prior phases
- **Phase 7 (Polish)**: Depends on all user story phases being complete

### User Story Dependencies

- **US1 (P1)**: Needs Phase 1 complete for accurate secret key names
- **US2 (P1)**: Needs Phase 1 complete (annotated values are the source of truth for tables)
- **US3 (P2)**: Needs Phase 1 complete (for accurate kubectl debug commands)
- **US4 (P2)**: Needs Phase 1 complete (for accurate resource values in scaling tiers)
- **US5 (P2)**: Schema changes are independent; validation depends on everything else

### Parallel Opportunities Within Phase 1

T001-T015 all edit `helm/estategap/values.yaml` — they must be **sequential** (same file).
Work top-to-bottom: T001 → T002 → T003 → … → T015.

### Parallel Opportunities After Phase 1

Once Phase 1 is complete, the following can run in parallel (different files):
- T016 (HELM_VALUES.md §1) ∥ T018 (README.md)
- T019 (HELM_VALUES.md §2) ∥ T021 (HELM_VALUES.md §5) ∥ T022 (HELM_VALUES.md §9)
- T023 (HELM_VALUES.md §7) ∥ T025 (values.schema.json)
- T024 (HELM_VALUES.md §3) ∥ T027 (HELM_VALUES.md §8)

---

## Parallel Execution Examples

### Example: After Phase 1 — US1 + US2 start together

```text
# US1 (Quick Start)
Task T016: Write HELM_VALUES.md Section 1 (Quick Start)
Task T017: Write HELM_VALUES.md Section 4 (Security Configuration)

# US2 (Lookup) — run in parallel with US1
Task T018: Create helm/estategap/README.md
Task T019: Write HELM_VALUES.md Section 2 (External Services)
Task T021: Write HELM_VALUES.md Section 5 (Observability)

# US3 + US4 + US5 — start in parallel after Phase 1
Task T022: Write HELM_VALUES.md Section 9 (Troubleshooting)
Task T023: Write HELM_VALUES.md Section 7 (Scaling Guide)
Task T025: Enhance values.schema.json
```

---

## Implementation Strategy

### MVP First (US1 + US2 only)

1. Complete Phase 1 (T001–T015): annotate all values.yaml keys
2. Complete Phase 2 (T016–T018): Quick Start, Security section, README
3. Complete Phase 3 key tasks (T019, T020): External Services + App Services reference
4. **STOP and VALIDATE**: A new operator can deploy using Quick Start, look up any value in the annotated file or HELM_VALUES.md Sections 1–3
5. Ship if deadlines require — Sections 7, 8, 9 add value but are not blocking

### Incremental Delivery

1. Phase 1 complete → values.yaml is self-documenting
2. Phase 1 + 2 complete → Quick Start enables zero-knowledge deployments
3. Phase 1 + 2 + 3 complete → Full external-services and app-services reference
4. Phase 4 complete → Operators can self-serve troubleshooting
5. Phase 5 complete → Scaling guide covers production sizing
6. Phase 6 complete → Schema validation prevents misconfiguration at install time
7. Phase 7 complete → Full migration guide and final validation

---

## Notes

- [P] tasks write to **different files** and have no shared-file conflicts
- Phase 1 tasks all write to `values.yaml` — must be sequential
- No test tasks generated (not requested — pure documentation feature)
- The `helm lint` verification in T026 and T029 is the acceptance gate for US5
- `# --` comment count (≥ 150) is the acceptance gate for US2
- All 9 HELM_VALUES.md sections present is the acceptance gate for US1 + US3 + US4
