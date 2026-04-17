# Feature Specification: Kind Cluster & Helm Validation

**Feature Branch**: `029-kind-helm-validation`  
**Created**: 2026-04-17  
**Status**: Draft  

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Spins Up Full Local Platform (Priority: P1)

A developer clones the repo, runs `make kind-reset`, and within 5 minutes has the entire EstateGap platform running locally with realistic seed data, ready to develop against any service.

**Why this priority**: Fastest path to developer productivity. Without this, every developer must rely on staging, blocking parallel development and creating environment conflicts.

**Independent Test**: Running `make kind-reset` on a clean machine with Docker installed results in all pods Running, port forwards active, and `curl localhost:8080/healthz` returning 200.

**Acceptance Scenarios**:

1. **Given** Docker is installed and no kind cluster exists, **When** `make kind-reset` is run, **Then** a 3-node cluster starts, Helm chart deploys, seed data loads, and port forwards are active — all within 5 minutes.
2. **Given** a running cluster, **When** `make kind-down` is run, **Then** the cluster is destroyed and all port forwards are killed.
3. **Given** a running cluster, **When** `make kind-logs` is run, **Then** logs stream from all pods in real time.

---

### User Story 2 - Helm Chart Passes All Validation Gates (Priority: P1)

A developer or CI pipeline validates the Helm chart before deploying, catching broken templates, schema violations, and conformance failures before they reach any cluster.

**Why this priority**: The Helm chart is the deployment contract. A broken chart means nothing ships.

**Independent Test**: Running `helm lint` + `helm template` + `helm unittest` locally exits 0 with no errors or warnings across all four values profiles.

**Acceptance Scenarios**:

1. **Given** all four values files (default, staging, production, test), **When** `helm lint` is run against each, **Then** zero errors and zero warnings are reported.
2. **Given** `values.schema.json` is present, **When** an invalid value is passed to `helm install`, **Then** Helm rejects the install with a descriptive schema error.
3. **Given** the helm-unittest suite (≥20 test cases), **When** `helm unittest helm/estategap` is run, **Then** all tests pass.

---

### User Story 3 - Helm Install/Upgrade/Rollback Is Verified (Priority: P2)

A release engineer verifies that installing, upgrading, and rolling back the Helm chart completes without data loss or downtime, providing confidence before deploying to staging or production.

**Why this priority**: Upgrade/rollback correctness is required before any production release cycle.

**Independent Test**: `tests/helm/upgrade-test.sh` runs the full install → seed → upgrade → diff → rollback cycle and exits 0.

**Acceptance Scenarios**:

1. **Given** a kind cluster, **When** `helm install` is followed by `helm upgrade`, **Then** all Deployments become Ready within 5 minutes and no DB rows are lost.
2. **Given** a successful upgrade, **When** `helm rollback` is run, **Then** the previous release is restored and services respond to health checks.

---

### User Story 4 - Seed Data Populates Realistic Test State (Priority: P2)

A developer or E2E test suite needs realistic data (users, listings, zones, ML models, alerts) to develop or test features without hitting production or staging.

**Why this priority**: Meaningful testing requires representative data; empty databases are not testable.

**Independent Test**: Running `make kind-seed` after `make kind-deploy` results in 1,000 listings, 5 users, 7 city zone polygons, and 10 alert rules queryable from the API.

**Acceptance Scenarios**:

1. **Given** a deployed cluster, **When** `make kind-seed` is run, **Then** the PostgreSQL DB contains expected fixture counts and MinIO contains ONNX model artifacts.
2. **Given** seeded data, **When** `GET /api/v1/listings?country=ES` is called, **Then** Spanish listings from fixtures are returned.

---

### User Story 5 - Test Mode Isolates External Dependencies (Priority: P3)

A developer running locally does not trigger real Stripe charges, real LLM API calls, or real portal scraping — all external calls are intercepted by test doubles.

**Why this priority**: Local development must be safe and cost-free; real external calls would cause billing or rate-limit issues.

**Independent Test**: With `ESTATEGAP_TEST_MODE=true`, running a scrape cycle produces fixture data, Stripe webhooks return success, and AI chat replies with deterministic responses.

**Acceptance Scenarios**:

1. **Given** `ESTATEGAP_TEST_MODE=true`, **When** the scrape orchestrator triggers a cycle, **Then** listings come from fixture files, not live portals.
2. **Given** `ESTATEGAP_TEST_MODE=true`, **When** a Stripe webhook is delivered, **Then** the fake endpoint returns 200 without contacting Stripe.

---

### Edge Cases

- What happens if a port (80, 443, 8080) is already in use on the host? `kind-up` should fail fast with a clear error.
- What if Docker does not have enough resources (< 4 CPU, < 8GB RAM)? Provisioning may time out; document minimum requirements.
- What if `helm upgrade` fails mid-deploy? Rollback must leave the cluster in the previous working state.
- What if seed data loader runs against an empty database (migrations not applied)? Loader must detect and error clearly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide `tests/kind/cluster.yaml` defining a 3-node kind cluster (1 control-plane + 2 workers) with Kubernetes 1.30+.
- **FR-002**: System MUST provide Makefile targets: `kind-up`, `kind-down`, `kind-build`, `kind-load`, `kind-deploy`, `kind-seed`, `kind-test`, `kind-logs`, `kind-shell`, `kind-reset`.
- **FR-003**: `make kind-reset` MUST complete cluster provisioning (up through seed) in under 5 minutes on a machine with images pre-built.
- **FR-004**: System MUST provide `tests/fixtures/load.py` seeding 5 users, 1,000 listings, city zone polygons, ONNX models, 10 alert rules, and sample conversations.
- **FR-005**: System MUST provide `helm/estategap/values-test.yaml` enabling test mode with minimal replicas and no autoscaling.
- **FR-006**: `helm lint` MUST pass with zero errors/warnings for all four values profiles (default, staging, production, test).
- **FR-007**: `helm template` MUST render valid YAML for all four values profiles.
- **FR-008**: `helm/estategap/values.schema.json` MUST cover all top-level chart values with type, description, and defaults.
- **FR-009**: helm-unittest suite at `helm/estategap/tests/` MUST contain at least 20 test cases covering: image tags, replica counts, HPA conditionals, ingress routes, network policies, secret references, and feature flag toggles.
- **FR-010**: `tests/helm/install-test.sh` MUST verify all Deployments reach Ready within 3 minutes and all `/readyz` endpoints respond within 60 seconds.
- **FR-011**: `tests/helm/upgrade-test.sh` MUST verify install → upgrade → data-diff → rollback cycle without data loss.
- **FR-012**: `tests/helm/conformance.py` MUST assert that all Deployment/StatefulSet resources have: namespace, standard K8s labels, resource requests+limits, `securityContext.runAsNonRoot=true`, liveness+readiness probes, and no `:latest` image tags.
- **FR-013**: `make kind-deploy` MUST automatically start port forwards: 8080→api-gateway, 8081→ws-server, 3000→frontend, 3001→Grafana, 9090→Prometheus, 5432→PostgreSQL.
- **FR-014**: `ESTATEGAP_TEST_MODE=true` MUST disable real scraping (fixture spider), mock Stripe webhooks, use FakeLLMProvider, and enable `NOW_OVERRIDE` support across all services.
- **FR-015**: Image change detection MUST only reload changed images into kind, using Dockerfile+source hash comparison against `.make-cache/`.

### Key Entities

- **Kind Cluster**: 3-node local Kubernetes cluster with NodePort mappings and local registry.
- **Helm Values Profile**: One of four environment configurations (default/staging/production/test), each with validated schema.
- **Fixture Dataset**: Reproducible set of 1,000 listings, 5 users, 7 zones, 10 alerts, ONNX models — loaded deterministically.
- **Test Mode**: Runtime flag toggling external dependency mocking across all 10 services.
- **Conformance Report**: Automated check output asserting K8s resource compliance against defined standards.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `make kind-reset` completes successfully on a machine with Docker installed (no prior cluster), with all pods Running within 5 minutes of cluster creation.
- **SC-002**: `helm lint` returns exit code 0 with zero warnings across all four values profiles.
- **SC-003**: helm-unittest suite passes all ≥20 test cases with zero failures.
- **SC-004**: All Deployments reach Ready state within 3 minutes of `helm install` completion.
- **SC-005**: Upgrade from v0.1.0 → v0.2.0 and rollback to v0.1.0 both succeed with no data loss (DB diff shows no rows lost).
- **SC-006**: All chart conformance checks pass: 100% of Deployments/StatefulSets have resource limits, security contexts, and health probes defined.
- **SC-007**: `curl localhost:8080/healthz` returns HTTP 200 within 60 seconds of `make kind-deploy` completing.
- **SC-008**: `make kind-seed` loads 1,000 listings and all fixture data in under 30 seconds.
- **SC-009**: With `ESTATEGAP_TEST_MODE=true`, no outbound calls are made to Stripe, LLM providers, or scraping targets.

## Assumptions

- Docker Desktop or Docker Engine is installed with at least 4 CPU and 8GB RAM available to the Docker daemon.
- `kind`, `helm`, `kubectl`, and `helm unittest` plugin are available in the developer's PATH (or installed by a prerequisite check script).
- The existing Helm chart templates in `helm/estategap/templates/` are functional; this feature adds `values-test.yaml`, `values.schema.json`, helm-unittest tests, and conformance scripts around them.
- ML ONNX model fixtures are minimal stubs (not production-quality models) sufficient for pipeline testing.
- The `values-staging.yaml` and `values-production.yaml` files already exist and are not modified by this feature except to ensure they pass `helm lint`.
- Port 80, 443, 8080, 8081, 3000, 3001, 9090, and 5432 are available on the developer's machine.
- Seed data does not need to be cryptographically realistic (e.g., passwords are bcrypt hashes of known test values).
