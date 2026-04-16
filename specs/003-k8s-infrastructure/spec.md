# Feature Specification: Kubernetes Infrastructure

**Feature Branch**: `003-k8s-infrastructure`
**Created**: 2026-04-16
**Status**: Draft
**Input**: User description: "Set up the complete Kubernetes infrastructure for the EstateGap platform."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy Core Data Infrastructure (Priority: P1)

A platform engineer runs `helm install` on a fresh Kubernetes cluster and gets a fully operational data tier: NATS JetStream for messaging, PostgreSQL 16 + PostGIS for persistence, Redis for caching, and MinIO for object storage — all configured, secured, and ready to receive application traffic.

**Why this priority**: Without the data tier, no application service can function. This is the critical path for every other feature team.

**Independent Test**: Can be fully tested by running connectivity checks from a temporary pod: `nats stream ls` shows 8 streams; `psql` connects and `SELECT PostGIS_Version()` returns 3.4+; `redis-cli ping` returns PONG; MinIO console lists 5 buckets.

**Acceptance Scenarios**:

1. **Given** a Kubernetes cluster with no EstateGap components, **When** `helm install estategap helm/estategap` is run, **Then** NATS cluster (3 replicas), PostgreSQL primary + replica, Redis Sentinel, and MinIO are all Running within 5 minutes.
2. **Given** a running NATS JetStream cluster, **When** `nats stream ls` is executed, **Then** exactly 8 streams are listed: raw-listings, normalized-listings, enriched-listings, scored-listings, alerts-triggers, alerts-notifications, scraper-commands, price-changes.
3. **Given** a running PostgreSQL cluster, **When** `psql` connects and queries, **Then** PostGIS version 3.4+ is reported and the primary-replica replication lag is under 1 second.
4. **Given** a running Redis deployment, **When** a pod is restarted, **Then** data written before restart is available after restart (AOF persistence verified).
5. **Given** a running MinIO instance, **When** the setup job completes, **Then** 5 buckets exist: ml-models, training-data, listing-photos, exports, backups.

---

### User Story 2 - Observability and Monitoring (Priority: P2)

A platform engineer accesses Grafana via ingress and sees live Kubernetes node metrics, application logs via Loki, and distributed traces via Tempo — all in a single dashboard without manual configuration.

**Why this priority**: Observability is required before any production traffic to detect failures, SLA breaches, and capacity issues.

**Independent Test**: Access Grafana at `grafana.estategap.com`, verify pre-loaded dashboards show node CPU/memory, log streams from all namespaces, and traces from instrumented services.

**Acceptance Scenarios**:

1. **Given** kube-prometheus-stack is deployed, **When** Grafana ingress is accessed, **Then** Kubernetes node metrics and pod resource dashboards are visible.
2. **Given** Loki and Promtail are deployed, **When** any pod emits logs, **Then** logs are queryable in Grafana's Explore tab within 30 seconds.
3. **Given** Tempo is deployed, **When** a distributed trace is submitted, **Then** the trace is viewable in Grafana Tempo data source.

---

### User Story 3 - GitOps Continuous Deployment (Priority: P3)

A developer merges a change to `main` and ArgoCD automatically detects the diff, applies it to the staging namespace, and reports the sync status in its UI — without any manual `kubectl` or `helm` commands.

**Why this priority**: GitOps enables safe, auditable deployments. Required before the first application services are deployed.

**Independent Test**: Modify a value in `values-staging.yaml`, commit, push — ArgoCD UI shows OutOfSync, then Synced within its polling interval (3 minutes default).

**Acceptance Scenarios**:

1. **Given** ArgoCD Application CR is deployed pointing to `helm/` in the repo, **When** `values-staging.yaml` changes are pushed to `main`, **Then** ArgoCD detects the diff and auto-syncs the staging namespace.
2. **Given** a sync failure occurs, **When** ArgoCD detects the error, **Then** the Application shows Degraded status and an error message in the ArgoCD UI.

---

### User Story 4 - Helm Chart Application Skeleton (Priority: P4)

An application developer deploys a new microservice by adding its resource block to `values.yaml` and running `helm upgrade` — namespaces, ConfigMaps, Sealed Secrets, and Traefik IngressRoutes are all provisioned without writing raw manifests.

**Why this priority**: Reduces the barrier to deploying new services and enforces consistent resource declaration.

**Independent Test**: Add a minimal service definition to `values.yaml`, run `helm template` and verify namespaces, ConfigMaps, and IngressRoutes render correctly.

**Acceptance Scenarios**:

1. **Given** the Helm chart skeleton is deployed, **When** `helm template` is run, **Then** all 6 namespaces (estategap-system, estategap-gateway, estategap-scraping, estategap-pipeline, estategap-intelligence, estategap-notifications) are rendered.
2. **Given** a Sealed Secret is defined in `sealed-secrets.yaml`, **When** it is applied to the cluster, **Then** the Sealed Secrets controller decrypts it and creates the corresponding Kubernetes Secret.
3. **Given** Traefik IngressRoutes are deployed, **When** requests arrive at `app.estategap.com`, `api.estategap.com`, and `ws.estategap.com`, **Then** they are routed to the correct backend services.

---

### Edge Cases

- What happens when a PostgreSQL primary pod is evicted? The CloudNativePG operator must promote a replica automatically.
- What happens when NATS loses quorum (2 of 3 replicas fail)? JetStream must refuse writes rather than silently losing messages.
- What happens when MinIO init job runs on an already-configured instance? Bucket creation must be idempotent.
- What happens when Sealed Secrets private key is rotated? Existing secrets must be re-encrypted before rotation.
- What happens when a node is added to the cluster? Promtail DaemonSet must automatically deploy to it and begin collecting logs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST deploy NATS JetStream as a 3-replica StatefulSet with 10Gi persistent storage per replica, accessible via ClusterIP within the cluster.
- **FR-002**: System MUST pre-create 8 NATS streams (raw-listings, normalized-listings, enriched-listings, scored-listings, alerts-triggers, alerts-notifications, scraper-commands, price-changes) via an init job or init container on first deployment.
- **FR-003**: System MUST deploy PostgreSQL 16 with PostGIS 3.4 extension via CloudNativePG operator with 1 primary and 1 read replica, 200Gi persistent storage, and daily backups to MinIO via barman.
- **FR-004**: System MUST deploy Redis 7 with Sentinel mode enabled, 1Gi memory limit, AOF persistence, and `allkeys-lru` eviction policy.
- **FR-005**: System MUST deploy MinIO with 50Gi persistent storage and automatically create 5 buckets (ml-models, training-data, listing-photos, exports, backups) via an init job.
- **FR-006**: System MUST deploy the observability stack: kube-prometheus-stack (Prometheus + Grafana + AlertManager), Loki + Promtail DaemonSet, and Tempo.
- **FR-007**: System MUST deploy ArgoCD Application CR configured to watch the `helm/` directory of the repository, with auto-sync enabled for the staging namespace.
- **FR-008**: System MUST declare 6 Kubernetes namespaces: estategap-system, estategap-gateway, estategap-scraping, estategap-pipeline, estategap-intelligence, estategap-notifications.
- **FR-009**: System MUST provision NetworkPolicies such that: the gateway namespace can reach all other namespaces; scraping, pipeline, and intelligence namespaces can only reach the system namespace.
- **FR-010**: System MUST store all sensitive configuration (database passwords, Redis password, API keys) as Sealed Secrets — never as plain Kubernetes Secrets in the repository.
- **FR-011**: System MUST define Traefik IngressRoutes routing `app.estategap.com` to the frontend, `api.estategap.com` to the API gateway, and `ws.estategap.com` to the WebSocket server, with TLS via cert-manager Let's Encrypt.
- **FR-012**: System MUST define Horizontal Pod Autoscalers for: api-gateway (CPU 60%), spider-workers (NATS queue depth), ml-scorer (CPU 70%), ai-chat (CPU 60%).

### Key Entities

- **Helm Release**: A versioned, parameterized deployment unit. Contains Chart.yaml, values files per environment, and templates. Deployed via `helm install/upgrade`.
- **NATS Stream**: A durable JetStream stream with a defined subject, retention policy, and consumer configuration. Created at cluster boot via init container.
- **CloudNativePG Cluster CR**: A custom Kubernetes resource specifying PostgreSQL topology (primary + replicas), storage, backup schedule, and PostGIS init SQL.
- **Sealed Secret**: An encrypted Kubernetes Secret that can be committed safely to git. Decrypted at apply-time by the Sealed Secrets controller.
- **ArgoCD Application CR**: A custom resource declaring the source repo, target cluster, and sync policy for GitOps deployment.
- **NetworkPolicy**: A Kubernetes resource enforcing egress/ingress rules between namespaces, implementing the least-privilege connectivity model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Complete platform infrastructure is deployed from a single `helm install` command in under 10 minutes on a 3-node cluster.
- **SC-002**: NATS cluster sustains 100,000 messages/second without message loss, verified by a load test publish/subscribe cycle.
- **SC-003**: PostgreSQL replication lag stays below 1 second under normal write load.
- **SC-004**: Redis data survives a pod restart without loss (AOF persistence verified by write-restart-read test).
- **SC-005**: Grafana dashboards are accessible within 5 minutes of helm install, showing live node metrics from all cluster nodes.
- **SC-006**: ArgoCD detects a `values-staging.yaml` change and completes auto-sync within 3 minutes of the commit being pushed.
- **SC-007**: Zero plain-text secrets exist in the git repository — verified by scanning for Kubernetes Secret manifests outside of Sealed Secrets.

## Assumptions

- Kubernetes 1.28+ cluster is pre-provisioned and accessible via `kubectl`.
- Traefik Ingress Controller is pre-installed on the cluster (not managed by this chart).
- cert-manager is pre-installed on the cluster with a working ACME/Let's Encrypt ClusterIssuer.
- Sealed Secrets controller is pre-installed on the cluster.
- CloudNativePG operator is pre-installed on the cluster (or installed as a chart dependency).
- ArgoCD is pre-installed on the cluster with access to the git repository.
- The cluster has a default StorageClass that supports ReadWriteOnce PVCs.
- DNS entries for `app.estategap.com`, `api.estategap.com`, `ws.estategap.com`, and `grafana.estategap.com` point to the cluster's ingress IP.
- MinIO is deployed in standalone mode (not distributed/operator mode) for the initial version; distributed mode is a future upgrade path.
