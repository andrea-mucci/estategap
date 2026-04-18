# Tasks: Helm Chart External Infrastructure Refactor

**Input**: Design documents from `specs/035-helm-external-infra/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: Establish directory structure and review existing chart state before making changes.

- [X] T001 Create `helm/estategap/dashboards/` directory (required for Grafana dashboard JSON files and `Files.Get` in template)
- [X] T002 Create `specs/035-helm-external-infra/contracts/` placeholder (no external contracts — internal Helm chart; skip contract tasks)

**Checkpoint**: Directory structure ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core restructuring that blocks ALL user stories — values schema, sub-chart removal, shared helpers. Must complete before any user story phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Update `helm/estategap/Chart.yaml`: remove `cloudnative-pg` (alias: cnpg), `kube-prometheus-stack` (alias: prometheus), `loki-stack` (alias: loki), and `tempo` dependencies; keep only `redis` (Bitnami) and `keda`; update `redis` condition from `redis.enabled` to `components.redis.deploy`
- [X] T004 [P] Update `helm/estategap/values.yaml`: add `components` section (`redis.deploy: true`, `mlflow.deploy: true`, `kafka.deploy: false`, `postgresql.deploy: false`, `prometheus.deploy: false`, `grafana.deploy: false`); replace `postgresql.*` self-deploy keys with `postgresql.external.*` (host, port, database, sslmode, credentialsSecret) and `postgresql.readReplica.*` and `postgresql.migrations.*`; rename `kafka.sasl.secretName` → `kafka.sasl.credentialsSecret`, remove `kafka.sasl.username`, rename `kafka.initJob.*` → `kafka.topicInit.*`; rename `s3.credentials.secret` → `s3.credentialsSecret`; replace entire `prometheus.*` sub-chart passthrough with `prometheus.serviceMonitor.*` and `prometheus.rules.*`; replace `grafana.*` sub-chart passthrough with `grafana.dashboards.*`; remove `observability.*`, `cnpg.*`, `loki.*`, `tempo.*` sections
- [X] T005 [P] Update `helm/estategap/values-staging.yaml`: set `components.kafka.deploy: false`, `components.postgresql.deploy: false`, `components.prometheus.deploy: false`, `components.grafana.deploy: false`, `components.redis.deploy: true`, `components.mlflow.deploy: true`; set `postgresql.external.host`, `kafka.topicInit.replicationFactor: 1`; remove any overrides for removed sub-charts (cnpg, prometheus stack, loki, tempo)
- [X] T006 [P] Update `helm/estategap/values-production.yaml`: same component flag pattern as staging but with production endpoints; remove sub-chart overrides
- [X] T007 [P] Update `helm/estategap/values-test.yaml`: set all `components.*.deploy: false` except `redis` and `mlflow`; remove sub-chart overrides; ensure test-specific overrides still work
- [X] T008 Update `helm/estategap/templates/_helpers.tpl` — `estategap.commonEnv`: replace hardcoded `estategap-postgres-rw.estategap-system.svc.cluster.local` with `valueFrom.configMapKeyRef` for `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_SSLMODE`; add conditional `DATABASE_RO_HOST` when `postgresql.readReplica.enabled`; remove hardcoded `DATABASE_RO_HOST` line
- [X] T009 [P] Update `helm/estategap/templates/_helpers.tpl` — `estategap.kafkaEnv`: replace `kafka.sasl.username` inline value and `kafka.sasl.secretName` secret ref with `kafka.sasl.credentialsSecret` ref for both `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD`
- [X] T010 [P] Update `helm/estategap/templates/_helpers.tpl` — `estategap.s3CredentialEnv`: replace `.Values.s3.credentials.secret` with `.Values.s3.credentialsSecret`
- [X] T011 Update `helm/estategap/templates/configmap.yaml`: add `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_SSLMODE` from `postgresql.external.*`; add conditional `DATABASE_RO_HOST` and `DATABASE_RO_PORT` when `postgresql.readReplica.enabled`; update `gdpr.hardDeleteCron.database.host` default value from CNPG service DNS to `postgresql.external.host` value
- [X] T012 Update `helm/estategap/values.yaml`: update `gdpr.hardDeleteCron.database.host` default from `estategap-postgres-rw.estategap-system.svc.cluster.local` to match `postgresql.external.host` default

**Checkpoint**: Foundation ready — values schema restructured, helpers updated, sub-charts removed. User story phases can begin.

---

## Phase 3: User Story 1 — Deploy Without Redundant Infrastructure (Priority: P1) 🎯 MVP

**Goal**: Feature flags correctly suppress all self-deployed infrastructure when `components.*.deploy: false`. No CloudNativePG, kube-prometheus-stack, Loki, or Tempo resources rendered in default/staging profile.

**Independent Test**: `helm template estategap helm/estategap -f values.yaml -f values-staging.yaml | grep 'kind:' | sort | uniq` — output must NOT contain `Cluster`, `ScheduledBackup`, `Prometheus`, `Grafana`, `Alertmanager`, or Loki/Tempo resources. `helm lint` passes on all four profiles.

- [X] T013 [US1] Update `helm/estategap/templates/postgresql-cluster.yaml`: change guard from `{{- if .Values.postgresql.enabled }}` to `{{- if .Values.components.postgresql.deploy }}`
- [X] T014 [US1] Update `helm/estategap/templates/postgresql-backup.yaml`: change guard from `{{- if and .Values.postgresql.enabled .Values.postgresql.backup.enabled }}` to `{{- if .Values.components.postgresql.deploy }}`
- [X] T015 [P] [US1] Update `helm/estategap/templates/grafana-datasources.yaml`: change guard from `{{- if .Values.observability.prometheus.enabled }}` to `{{- if .Values.prometheus.serviceMonitor.enabled }}` (datasource ConfigMap only relevant when talking to existing Prometheus/Grafana)
- [X] T016 [P] [US1] Update `helm/estategap/tests/feature-flags_test.yaml`: add test cases — `components.postgresql.deploy: false` → `postgresql-cluster.yaml` has 0 documents; `components.postgresql.deploy: false` → `postgresql-backup.yaml` has 0 documents; `prometheus.rules.enabled: false` → `prometheus-rules.yaml` has 0 documents; `grafana.dashboards.enabled: false` → `grafana-dashboards.yaml` has 0 documents; `prometheus.serviceMonitor.enabled: false` → `servicemonitor.yaml` has 0 documents
- [X] T017 [P] [US1] Update `helm/estategap/tests/postgres_test.yaml`: add test — external host value flows into ConfigMap `DATABASE_HOST` key; add test — external port value flows into ConfigMap `DATABASE_PORT` key; update any existing tests that reference old `postgresql.enabled` key

**Checkpoint**: US1 complete. `helm template` with staging values produces no CNPG/Prometheus/Loki/Tempo resources. `helm lint` passes on all profiles.

---

## Phase 4: User Story 2 — Configure External Service Connections (Priority: P1)

**Goal**: All application pods receive correct Kafka, PostgreSQL, and S3 connection env vars sourced from external config and K8s Secret references.

**Independent Test**: `helm template ... | grep 'DATABASE_HOST'` shows `configMapKeyRef` pointing to `estategap-config`. `helm template ... | grep 'KAFKA_SASL_USERNAME'` shows `secretKeyRef` pointing to `kafka.sasl.credentialsSecret` when SASL enabled.

- [X] T018 [US2] Update `helm/estategap/templates/kafka-configmap.yaml`: add `KAFKA_SASL_MECHANISM` key from `kafka.sasl.mechanism` when SASL enabled; remove any username values (username now in secret only)
- [X] T019 [US2] Update `helm/estategap/templates/kafka-topics-init-job.yaml`: replace `kafka.sasl.username` inline env var with `secretKeyRef` from `kafka.sasl.credentialsSecret` for `KAFKA_SASL_USERNAME`; replace `kafka.sasl.secretName` secret ref with `kafka.sasl.credentialsSecret` for `KAFKA_SASL_PASSWORD`; rename image path from `.Values.kafka.initJob.image` to `.Values.kafka.topicInit.image`; rename replication factor from `.Values.kafka.initJob.replicationFactor` to `.Values.kafka.topicInit.replicationFactor`; add dead-letter topic creation conditional on `kafka.deadLetter.enabled`
- [X] T020 [P] [US2] Update `helm/estategap/templates/postgresql-cluster.yaml`: update `s3Credentials` block to use `.Values.s3.credentialsSecret` instead of hardcoded `estategap-s3-credentials` / old key path
- [X] T021 [P] [US2] Update `helm/estategap/tests/kafka_test.yaml`: add test — when `kafka.sasl.enabled: true`, init Job env references `credentialsSecret` for `KAFKA_SASL_USERNAME`; add test — `KAFKA_SASL_PASSWORD` secretKeyRef uses `credentialsSecret` name

**Checkpoint**: US2 complete. External connection env vars verified through helm template assertions.

---

## Phase 5: User Story 3 — Database Schema Migrates Automatically on Deploy (Priority: P2)

**Goal**: A pre-install/pre-upgrade Helm hook Job runs Alembic migrations with PostgreSQL credentials from the referenced secret. Helm halts on failure; pod retained for debugging.

**Independent Test**: `helm template ... | grep 'kind: Job'` shows `estategap-db-migrate` with `helm.sh/hook: pre-install,pre-upgrade` annotation and `backoffLimit: 0`.

- [X] T022 [US3] Create `helm/estategap/templates/db-migration-job.yaml`: Helm hook Job with annotations `helm.sh/hook: pre-install,pre-upgrade`, `helm.sh/hook-weight: "-5"`, `helm.sh/hook-delete-policy: before-hook-creation`; `restartPolicy: Never`; `backoffLimit: 0`; `activeDeadlineSeconds: {{ .Values.postgresql.migrations.timeout }}`; container image `{{ .Values.postgresql.migrations.image }}`; command `["alembic", "-c", "/app/alembic.ini", "upgrade", "head"]`; `envFrom.secretRef` for `{{ .Values.postgresql.external.credentialsSecret }}`; `DATABASE_URL` env constructed from external host/port/database/sslmode using `$(PGUSER)` and `$(PGPASSWORD)` variable substitution; entire template guarded by `{{- if .Values.postgresql.migrations.enabled }}`

**Checkpoint**: US3 complete. Migration Job renders with correct hook annotations and credential wiring.

---

## Phase 6: User Story 4 — Metrics Visible in Existing Prometheus (Priority: P2)

**Goal**: One ServiceMonitor CRD per EstateGap service (where `serviceMonitor.enabled: true`), labelled to match the existing Prometheus operator selector.

**Independent Test**: `helm template ... | grep 'kind: ServiceMonitor' | wc -l` returns ≥ 7 (number of services with serviceMonitor.enabled).

- [X] T023 [US4] Create `helm/estategap/templates/servicemonitor.yaml`: outer guard `{{- if .Values.prometheus.serviceMonitor.enabled }}`; `range $name, $svc := .Values.services`; inner guard `{{- if and $svc.enabled (and $svc.serviceMonitor $svc.serviceMonitor.enabled) }}`; each ServiceMonitor metadata includes `{{- toYaml $.Values.prometheus.serviceMonitor.labels | nindent 4 }}` for operator selector matching; `spec.selector.matchLabels` uses `estategap.serviceSelectorLabels` helper; `spec.endpoints[0].path` from `$svc.serviceMonitor.path`; `spec.endpoints[0].port: http`; `spec.endpoints[0].interval` from `$svc.serviceMonitor.interval` or global default; separator `---` between documents in range

**Checkpoint**: US4 complete. ServiceMonitors render for all enabled services with correct labels.

---

## Phase 7: User Story 5 — Grafana Dashboards Auto-Imported (Priority: P3)

**Goal**: Seven Grafana dashboard ConfigMaps with `grafana_dashboard: "1"` label created in configured namespace, loaded from JSON files via `Files.Get`.

**Independent Test**: `helm template ... | grep 'estategap-dashboard-' | wc -l` returns 7. Each ConfigMap is in `grafana.dashboards.namespace`.

- [X] T024 [US5] Create `helm/estategap/dashboards/scraping-health.json`: minimal valid Grafana 9.x dashboard JSON; title "EstateGap — Scraping Health"; one time-series panel with PromQL `rate(estategap_scraper_requests_total{status="success"}[5m]) / rate(estategap_scraper_requests_total[5m]) * 100`; dashboard uid `estategap-scraping-health`
- [X] T025 [P] [US5] Create `helm/estategap/dashboards/pipeline-throughput.json`: title "EstateGap — Pipeline Throughput"; panel PromQL `rate(estategap_pipeline_messages_processed_total[5m])`; uid `estategap-pipeline-throughput`
- [X] T026 [P] [US5] Create `helm/estategap/dashboards/ml-metrics.json`: title "EstateGap — ML Metrics"; panels for prediction rate and error rate; PromQL `rate(estategap_ml_scorer_predictions_total[5m])` and `rate(estategap_ml_scorer_errors_total[5m])`; uid `estategap-ml-metrics`
- [X] T027 [P] [US5] Create `helm/estategap/dashboards/alert-latency.json`: title "EstateGap — Alert Latency"; panel PromQL `histogram_quantile(0.99, rate(estategap_alert_processing_duration_seconds_bucket[5m]))`; uid `estategap-alert-latency`
- [X] T028 [P] [US5] Create `helm/estategap/dashboards/api-performance.json`: title "EstateGap — API Performance"; panel PromQL `histogram_quantile(0.99, rate(estategap_http_request_duration_seconds_bucket[5m]))`; uid `estategap-api-performance`
- [X] T029 [P] [US5] Create `helm/estategap/dashboards/websocket-connections.json`: title "EstateGap — WebSocket Connections"; panel PromQL `estategap_websocket_active_connections`; uid `estategap-websocket-connections`
- [X] T030 [P] [US5] Create `helm/estategap/dashboards/kafka-consumer-lag.json`: title "EstateGap — Kafka Consumer Lag"; panel PromQL `estategap_kafka_consumer_lag`; uid `estategap-kafka-consumer-lag`
- [X] T031 [US5] Create `helm/estategap/templates/grafana-dashboards.yaml`: outer guard `{{- if .Values.grafana.dashboards.enabled }}`; `range $name := list "scraping-health" "pipeline-throughput" "ml-metrics" "alert-latency" "api-performance" "websocket-connections" "kafka-consumer-lag"`; each ConfigMap in `{{ $.Values.grafana.dashboards.namespace }}`; labels from `{{- toYaml $.Values.grafana.dashboards.labels | nindent 4 }}` plus `estategap.labels`; `data` key `{{ $name }}.json` loaded via `$.Files.Get (printf "dashboards/%s.json" $name) | nindent 4`; separator `---` between documents

**Checkpoint**: US5 complete. All 7 dashboard ConfigMaps render with correct labels and JSON content.

---

## Phase 8: User Story 6 — Alerting Rules Visible in Prometheus (Priority: P3)

**Goal**: A PrometheusRule resource with 7 alert groups covering all critical EstateGap subsystems, guarded by `prometheus.rules.enabled`.

**Independent Test**: `helm template ... | grep 'kind: PrometheusRule' | wc -l` returns 1. Rule contains groups: `estategap.scraping`, `estategap.pipeline`, `estategap.ml`, `estategap.api`, `estategap.kafka`, `estategap.pods`, `estategap.storage`.

- [X] T032 [US6] Rewrite `helm/estategap/templates/prometheus-rules.yaml`: change guard from `{{- if .Values.prometheus.enabled }}` to `{{- if .Values.prometheus.rules.enabled }}`; add metadata labels from `{{- toYaml .Values.prometheus.rules.labels | nindent 4 }}`; replace single `estategap.kafka` group with 7 groups:
  - `estategap.scraping`: alert `ScraperSuccessRateLow` — expr `rate(estategap_scraper_requests_total{status="success"}[10m]) / rate(estategap_scraper_requests_total[10m]) < 0.8`, for `5m`, severity `warning`
  - `estategap.pipeline`: alert `PipelineLagHigh` — expr `estategap_pipeline_consumer_lag_seconds > 300`, for `5m`, severity `warning`
  - `estategap.ml`: alert `MLScorerErrorRateHigh` — expr `rate(estategap_ml_scorer_errors_total[5m]) / rate(estategap_ml_scorer_predictions_total[5m]) > 0.05`, for `5m`, severity `warning`
  - `estategap.api`: alert `APILatencyP99High` — expr `histogram_quantile(0.99, rate(estategap_http_request_duration_seconds_bucket[5m])) > 2`, for `5m`, severity `warning`
  - `estategap.kafka`: alert `KafkaConsumerLagHigh` (existing) — expr `estategap_kafka_consumer_lag > 10000`, for `2m`, severity `warning`
  - `estategap.pods`: alert `PodRestartCountHigh` — expr `increase(kube_pod_container_status_restarts_total{namespace=~"estategap-.*"}[15m]) > 3`, for `0m`, severity `critical`
  - `estategap.storage`: alert `PVCDiskUsageHigh` — expr `kubelet_volume_stats_used_bytes{namespace=~"estategap-.*"} / kubelet_volume_stats_capacity_bytes > 0.8`, for `5m`, severity `warning`

**Checkpoint**: US6 complete. PrometheusRule renders with all 7 alert groups and correct labels.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and cleanup completing the full chart refactor.

- [X] T033 [P] Rewrite `helm/estategap/HELM_VALUES.md`: document all new sections (`components.*`, `postgresql.external.*`, `postgresql.readReplica.*`, `postgresql.migrations.*`, `kafka.sasl.credentialsSecret`, `kafka.topicInit.*`, `kafka.deadLetter.*`, `s3.credentialsSecret`, `prometheus.serviceMonitor.*`, `prometheus.rules.*`, `grafana.dashboards.*`); document removed sections; document K8s Secret contracts for each credentialsSecret reference
- [X] T034 [P] Update `helm/estategap/templates/sealed-secrets.yaml`: review and update any references to old `s3.credentials.secret` key or old `postgresql.enabled` values; ensure sealed secrets template still renders correctly with new values structure
- [ ] T035 Run `helm dependency update helm/estategap` to regenerate `Chart.lock` with reduced dependency set (only redis + keda)
- [X] T036 [P] Run `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml` — fix any lint errors
- [X] T037 [P] Run `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-production.yaml` — fix any lint errors
- [X] T038 [P] Run `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-test.yaml` — fix any lint errors
- [X] T039 Run spot-check template assertions from `quickstart.md`: verify zero `kind: Cluster` resources, ≥7 `kind: ServiceMonitor` resources, 1 `kind: PrometheusRule`, 7 `estategap-dashboard-*` ConfigMaps with staging values
- [X] T040 [P] Update `specs/034-s3-migration/plan.md`: mark as superseded by 035 for S3 credential key rename (`s3.credentials.secret` → `s3.credentialsSecret`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **Phase 3 (US1)**: Depends on Phase 2 — template guards for removed sub-charts
- **Phase 4 (US2)**: Depends on Phase 2 — Kafka SASL and DB connection helpers must be updated first
- **Phase 5 (US3)**: Depends on Phase 2 — migration Job needs external PG values schema
- **Phase 6 (US4)**: Depends on Phase 2 — ServiceMonitor needs `prometheus.serviceMonitor.*` values
- **Phase 7 (US5)**: Depends on T001 (dashboards/ dir) — dashboard JSON and template are independent
- **Phase 8 (US6)**: Depends on Phase 2 — PrometheusRule needs `prometheus.rules.*` values
- **Phase 9 (Polish)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no inter-story dependencies
- **US2 (P1)**: After Phase 2 — no inter-story dependencies; parallelizable with US1
- **US3 (P2)**: After Phase 2 — no inter-story dependencies; parallelizable with US1, US2
- **US4 (P2)**: After Phase 2 — no inter-story dependencies; parallelizable with US1, US2, US3
- **US5 (P3)**: After T001 only — dashboard JSON files have no chart dependencies; template after Phase 2
- **US6 (P3)**: After Phase 2 — no inter-story dependencies

### Within Each Phase

- T003 (Chart.yaml) must complete before `helm dependency update` in T035
- T004, T005, T006, T007 (values restructure) must complete before any template tasks that reference new value paths
- T008, T009, T010 (helpers) must complete before T036-T039 (lint/template checks)
- T011 (configmap.yaml) must complete before T036-T039

### Parallel Opportunities

- T004–T007: All values file updates — different files, no conflicts
- T008–T010: All `_helpers.tpl` named blocks — edit different `define` blocks in same file; do sequentially or carefully
- T013, T014: Both postgresql template guards — different files
- T015, T016, T017: Different files, fully parallel
- T024–T030: All 7 dashboard JSON files — fully independent, different files
- T036–T038: Different lint profiles — can run simultaneously
- T033, T034: Documentation + sealed-secrets review — different files

---

## Parallel Example: Phase 2 (Foundational)

```
# Wave 1 — can all start immediately after Phase 1:
Task T003: Update Chart.yaml (dependency list)
Task T004: Restructure values.yaml
Task T005: Update values-staging.yaml
Task T006: Update values-production.yaml
Task T007: Update values-test.yaml

# Wave 2 — after Chart.yaml restructure confirms new value paths:
Task T008: Update _helpers.tpl commonEnv (DATABASE_HOST)
Task T009: Update _helpers.tpl kafkaEnv (SASL credentialsSecret)
Task T010: Update _helpers.tpl s3CredentialEnv
Task T011: Update configmap.yaml (add external DB keys)
Task T012: Update gdpr hardDelete DB host default in values.yaml
```

## Parallel Example: User Stories 1–4 (after Phase 2)

```
# All four P1/P2 user story phases can start in parallel:
Stream A: T013 → T014 → T015 → T016 → T017  (US1: component flags)
Stream B: T018 → T019 → T020 → T021          (US2: connection wiring)
Stream C: T022                                (US3: migration job)
Stream D: T023                                (US4: service monitors)

# P3 phases can start in parallel with P2:
Stream E: T024 → T025 → ... → T030 → T031   (US5: dashboards — only needs T001)
Stream F: T032                               (US6: prometheus rules)
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (values restructure + helpers + Chart.yaml)
3. Complete Phase 3 (US1): Component flags — suppress redundant infra
4. Complete Phase 4 (US2): External connection wiring
5. **STOP and VALIDATE**: `helm template` + `helm lint` + spot checks
6. Ship: chart installs on kind with external infra, no duplicates, correct env vars

### Incremental Delivery

1. Setup + Foundational → chart structure ready
2. US1 + US2 (P1 stories) → no redundant infra + correct connections → **MVP: production-safe install**
3. US3 (P2) → automated migrations on deploy
4. US4 (P2) → metrics in Prometheus
5. US5 + US6 (P3) → dashboards + alert rules → **Full observability**
6. Polish → lint clean, HELM_VALUES.md complete

### Single Developer Sequential Order

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015 → T016 → T017 → T018 → T019 → T020 → T021 → T022 → T023 → T024 → T025 → T026 → T027 → T028 → T029 → T030 → T031 → T032 → T033 → T034 → T035 → T036 → T037 → T038 → T039 → T040

---

## Notes

- [P] tasks = different files, no conflicts — safe to run concurrently
- `_helpers.tpl` tasks T008–T010 edit different named `define` blocks but the same file — execute sequentially to avoid conflicts
- All value path renames must be consistent across `values.yaml`, all override files, templates, and tests
- After T003 + T035 (`helm dependency update`), commit `Chart.lock` alongside `Chart.yaml`
- `helm lint` is the primary validation gate — run after every template change
- The sealed-secrets template (T034) only needs review for key renames; the encrypted values themselves don't change
