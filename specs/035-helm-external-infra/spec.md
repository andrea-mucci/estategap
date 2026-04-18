# Feature Specification: Helm Chart External Infrastructure Refactor

**Feature Branch**: `035-helm-external-infra`
**Created**: 2026-04-17
**Status**: Draft
**Input**: Refactor the Helm chart to stop deploying infrastructure services and connect to existing shared cluster services.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy Without Redundant Infrastructure (Priority: P1)

A platform engineer installs or upgrades EstateGap on a cluster that already provides Kafka, PostgreSQL, Prometheus, and Grafana as shared services. The Helm chart must not create duplicate instances of those services, and must instead wire EstateGap services to the existing shared endpoints.

**Why this priority**: The brownfield cluster already has production-grade managed services. Deploying duplicates would waste resources, cause naming conflicts, and violate cluster policies. This is the primary blocker before any production rollout.

**Independent Test**: `helm template` with `components.kafka.deploy=false` and `components.postgresql.deploy=false` produces zero StatefulSet or Cluster resources for those services. The chart installs cleanly on a kind cluster with pre-installed Strimzi Kafka and Bitnami PostgreSQL.

**Acceptance Scenarios**:

1. **Given** a cluster with Strimzi Kafka running, **When** `helm install` is run with `components.kafka.deploy: false`, **Then** no Kafka StatefulSet or KafkaTopic CRDs are rendered by the chart.
2. **Given** `components.postgresql.deploy: false`, **When** `helm template` is run, **Then** no CloudNativePG Cluster, ScheduledBackup, or cloudnative-pg operator resources appear in the output.
3. **Given** `components.prometheus.deploy: false`, **When** `helm template` is run, **Then** no kube-prometheus-stack, Loki, or Tempo resources appear.
4. **Given** `components.grafana.deploy: false`, **When** `helm template` is run, **Then** no Grafana Deployment or PersistentVolumeClaim appears.

---

### User Story 2 - Configure External Service Connections (Priority: P1)

A platform engineer provides connection details for the shared Kafka, PostgreSQL, and S3 services via `values.yaml`. All EstateGap application services must automatically receive the correct connection environment variables without any manual secret injection.

**Why this priority**: All application services need valid connection strings at startup. Misconfigured connections cause cascading failures across all pipelines.

**Independent Test**: After `helm install` with external connection values, each pod's environment contains `KAFKA_BROKERS`, `DATABASE_URL`, `S3_ENDPOINT`, and the secret mounts resolve. Verifiable with `kubectl exec -- env | grep KAFKA_BROKERS`.

**Acceptance Scenarios**:

1. **Given** `kafka.brokers` is set, **When** any EstateGap pod starts, **Then** its `KAFKA_BROKERS` env var matches the configured broker address.
2. **Given** `postgresql.external.credentialsSecret` references a valid K8s Secret, **When** a pod starts, **Then** `DATABASE_URL` is constructed from the external host, port, database, and credentials—not from a self-deployed CloudNativePG endpoint.
3. **Given** `s3.credentialsSecret` references a valid K8s Secret, **When** any ML or pipeline pod starts, **Then** `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` are populated from that secret.
4. **Given** `kafka.sasl.enabled: true` with a `credentialsSecret`, **When** a pod starts, **Then** `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD` are injected from the referenced secret.

---

### User Story 3 - Database Schema Migrates Automatically on Deploy (Priority: P2)

A platform engineer runs `helm upgrade` and the database schema is automatically migrated to the latest version before any application pods are updated, with no manual intervention.

**Why this priority**: Prevents application pods from starting against a stale schema. Automates what would otherwise be a fragile manual step.

**Independent Test**: On `helm upgrade`, a migration Job appears in the cluster, completes successfully, and the upgrade proceeds. On failure, the Job pod remains available for log inspection and the upgrade halts.

**Acceptance Scenarios**:

1. **Given** a fresh install, **When** `helm install` runs, **Then** a migration Job executes before any Deployment is created.
2. **Given** a failed migration, **When** the Job exits non-zero, **Then** the Helm upgrade is marked as failed and all application Deployments remain at their previous version.
3. **Given** `postgresql.migrations.enabled: false`, **When** `helm install` runs, **Then** no migration Job is created.

---

### User Story 4 - Metrics Visible in Existing Prometheus (Priority: P2)

A platform engineer adds EstateGap to a cluster with an existing Prometheus operator. EstateGap service metrics automatically appear in Prometheus targets without adding manual scrape configs to the shared Prometheus instance.

**Why this priority**: Observability coverage is required before production promotion. ServiceMonitors are the standard way to register scrape targets with an operator.

**Independent Test**: After install, `kubectl get servicemonitor -n estategap-system` lists monitors for each service. The Prometheus UI shows estategap targets as UP.

**Acceptance Scenarios**:

1. **Given** `prometheus.serviceMonitor.enabled: true`, **When** `helm install` runs, **Then** a ServiceMonitor resource is created for each EstateGap service with metrics.
2. **Given** the ServiceMonitor label selector matches the existing Prometheus operator's selector, **When** Prometheus rescans, **Then** all EstateGap targets appear as UP.
3. **Given** `prometheus.serviceMonitor.enabled: false`, **When** `helm template` runs, **Then** no ServiceMonitor resources are rendered.

---

### User Story 5 - Grafana Dashboards Auto-Imported (Priority: P3)

An operator opens Grafana after install and finds EstateGap dashboards already imported—covering scraping health, pipeline throughput, ML metrics, API performance, WebSocket connections, alert latency, and Kafka consumer lag.

**Why this priority**: Dashboards accelerate incident response. Auto-import via ConfigMap sidecar is the standard pattern for shared Grafana clusters.

**Independent Test**: After install, `kubectl get configmap -n monitoring -l grafana_dashboard=1` lists 7 ConfigMaps. Grafana's sidecar picks them up within its poll interval.

**Acceptance Scenarios**:

1. **Given** `grafana.dashboards.enabled: true`, **When** `helm install` runs, **Then** 7 ConfigMaps with label `grafana_dashboard: "1"` are created in the configured namespace.
2. **Given** a Grafana instance with the dashboard sidecar enabled, **When** the sidecar polls for ConfigMaps, **Then** all 7 dashboards appear in Grafana.
3. **Given** `grafana.dashboards.enabled: false`, **When** `helm template` runs, **Then** no dashboard ConfigMaps are rendered.

---

### User Story 6 - Alerting Rules Visible in Prometheus (Priority: P3)

A platform engineer can see EstateGap-specific alert rules in the Prometheus rules page without manually editing the shared Prometheus configuration.

**Why this priority**: Alert coverage for scraper failures, pipeline lag, ML errors, and Kafka lag is needed before production.

**Independent Test**: After install, `kubectl get prometheusrule -n estategap-system` shows the rule resource. The Prometheus UI shows the rules active under "Rules".

**Acceptance Scenarios**:

1. **Given** `prometheus.rules.enabled: true`, **When** `helm install` runs, **Then** a PrometheusRule resource with all 7 alert groups is created.
2. **Given** consumer lag exceeds 10,000, **When** Prometheus evaluates the rule, **Then** a KafkaConsumerLagHigh alert fires.
3. **Given** `prometheus.rules.enabled: false`, **When** `helm template` runs, **Then** no PrometheusRule resource is rendered.

---

### Edge Cases

- What if `postgresql.external.credentialsSecret` does not exist at deploy time? Migration Job and application pods will fail to start with a CrashLoopBackOff; this is expected and documented.
- What if `kafka.topicInit.enabled: true` but Kafka is unreachable? The init Job retries with backoff; Helm upgrade blocks until `activeDeadlineSeconds` is reached.
- What if both `components.redis.deploy: true` and an external Redis address are configured? Self-deployed Redis takes precedence; documented in HELM_VALUES.md.
- What if `grafana.dashboards.namespace` differs from the Grafana sidecar's watched namespace? Dashboards will not appear; the value must match the sidecar `LABEL_VALUE` configuration.
- What if the migration Job from a previous run still exists? The `before-hook-creation` delete policy removes the old Job before the new one runs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Helm chart MUST NOT deploy a CloudNativePG Cluster or ScheduledBackup when `components.postgresql.deploy: false`.
- **FR-002**: The Helm chart MUST NOT deploy kube-prometheus-stack, Loki, or Tempo sub-charts when `components.prometheus.deploy: false`.
- **FR-003**: The Helm chart MUST NOT deploy a Grafana instance when `components.grafana.deploy: false`.
- **FR-004**: All EstateGap application pods MUST receive `DATABASE_URL` and `DATABASE_READ_URL` derived from `postgresql.external.*` values and the referenced credentials Secret.
- **FR-005**: All EstateGap application pods MUST receive `KAFKA_BROKERS`, `KAFKA_TOPIC_PREFIX`, and optional `KAFKA_SASL_*` env vars from the Kafka ConfigMap and referenced SASL Secret.
- **FR-006**: All EstateGap application pods MUST receive `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET_PREFIX`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` from `s3.*` values and the referenced credentials Secret.
- **FR-007**: A Kafka topic init Job MUST run as a Helm pre-install/pre-upgrade hook and create all required topics idempotently when `kafka.topicInit.enabled: true`.
- **FR-008**: A database migration Job MUST run as a Helm pre-install/pre-upgrade hook when `postgresql.migrations.enabled: true`, using the same credentials as the application.
- **FR-009**: On migration Job failure, the Helm operation MUST halt and the Job pod MUST be retained for debugging.
- **FR-010**: One ServiceMonitor resource MUST be created per EstateGap service with metrics, when `prometheus.serviceMonitor.enabled: true` globally.
- **FR-011**: Seven Grafana dashboard ConfigMaps MUST be created with the `grafana_dashboard: "1"` label in the configured namespace when `grafana.dashboards.enabled: true`.
- **FR-012**: A PrometheusRule resource with 7 alert rule groups MUST be created when `prometheus.rules.enabled: true`.
- **FR-013**: Redis MUST remain self-deployed by the chart (Bitnami sub-chart) unchanged.
- **FR-014**: MLflow MUST remain self-deployed by the chart when `components.mlflow.deploy: true`.
- **FR-015**: `helm lint` MUST pass for `values.yaml`, `values-staging.yaml`, `values-production.yaml`, and `values-test.yaml`.
- **FR-016**: All sensitive credentials (DB passwords, S3 keys, Kafka SASL) MUST be sourced from referenced Kubernetes Secrets, never hardcoded in `values.yaml`.

### Key Entities

- **External PostgreSQL**: Host, port, database name, SSL mode, primary credentials Secret, optional read-replica endpoint.
- **External Kafka**: Broker addresses, topic prefix, SASL mechanism and credentials Secret, TLS CA Secret, topic init config.
- **External S3**: Endpoint URL, region, bucket prefix, path-style flag, credentials Secret.
- **ServiceMonitor**: Per-service scrape target declaration for Prometheus operator; label selector must match the operator's `serviceMonitorSelector`.
- **PrometheusRule**: Grouped alert expressions covering all critical EstateGap subsystems.
- **Grafana Dashboard ConfigMap**: One ConfigMap per dashboard, labelled for Grafana sidecar pickup, in the Grafana-watched namespace.
- **Migration Job**: Pre-hook Kubernetes Job running Alembic; retains pod on failure; times out after 5 minutes.
- **Feature Flag**: Boolean `deploy` field under `components.*` controlling whether the chart renders each optional infrastructure component.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `helm lint` passes with zero errors across all four value profiles.
- **SC-002**: `helm template` with any `components.*.deploy: false` flag produces no resources of the corresponding type.
- **SC-003**: All EstateGap pods reach Running state on a kind cluster with pre-installed external infrastructure within 10 minutes of `helm install`.
- **SC-004**: All application pods resolve `DATABASE_URL` to the external PostgreSQL host—verifiable via `kubectl exec -- env | grep DATABASE_URL`.
- **SC-005**: ServiceMonitors appear in the Prometheus targets list as UP within 2 minutes of install.
- **SC-006**: All 7 Grafana dashboards are visible in Grafana within 5 minutes of install.
- **SC-007**: The PrometheusRule resource is accepted by the Prometheus operator and rules appear on the /rules page.
- **SC-008**: A successful migration Job completes in under 5 minutes on install and upgrade.
- **SC-009**: A failing migration Job halts the Helm operation and retains the pod for debugging.

## Assumptions

- The target cluster runs Prometheus operator ≥ 0.63 (required for ServiceMonitor v1 CRD support).
- The Grafana sidecar is configured to watch ConfigMaps with label `grafana_dashboard: "1"` in the namespace specified by `grafana.dashboards.namespace`.
- The external Kafka, PostgreSQL, and Hetzner S3 services are accessible from the `estategap-system` namespace before `helm install` runs.
- The migration image (`postgresql.migrations.image`) contains Alembic and the EstateGap database migration scripts.
- Redis and MLflow are not available as shared cluster services and must remain self-deployed.
- The `cloudnative-pg`, `kube-prometheus-stack`, `loki-stack`, and `tempo` Helm sub-chart dependencies are removed from `Chart.yaml`.
- NATS has already been removed in feature 033; no NATS templates exist to delete.
- MinIO has already been removed in feature 034; no MinIO templates exist to delete.
