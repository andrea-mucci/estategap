# Feature Specification: Helm Chart Values Documentation

**Feature Branch**: `036-helm-values-documentation`
**Created**: 2026-04-18
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Deploy from Scratch Using Quick Start (Priority: P1)

A new operator unfamiliar with the EstateGap codebase follows the HELM_VALUES.md Quick Start section end-to-end — creating the required Secrets, writing a minimal values-override.yaml, and running `helm install` — without reading any template source code.

**Why this priority**: The primary value of documentation is enabling zero-prior-knowledge deployments. If an operator cannot succeed with Quick Start, all other sections are secondary.

**Independent Test**: A person who has never seen the EstateGap codebase can deploy a working cluster by following only HELM_VALUES.md Quick Start, with no questions asked.

**Acceptance Scenarios**:

1. **Given** a fresh cluster with Kafka/PostgreSQL/S3 already running, **When** the operator follows Quick Start verbatim, **Then** `helm install` completes and all pods reach Running state.
2. **Given** a missing required Secret, **When** `helm install` runs, **Then** a clear error message identifies which Secret and key is missing.
3. **Given** `helm install` with a value that violates the schema (e.g. invalid `sslmode`), **When** Helm validates the values, **Then** the error message names the exact field and lists valid options.

---

### User Story 2 — Look Up Any Value Without Reading Source (Priority: P1)

An operator wants to understand what `kafka.sasl.mechanism` does, what values are valid, and whether it is required. They find the answer in under 30 seconds by reading values.yaml inline comments or HELM_VALUES.md.

**Why this priority**: Day-to-day operational work requires value lookup; if every lookup requires grep-ing templates, the documentation has failed its purpose.

**Independent Test**: For any value in values.yaml, the inline comment answers: what it does, its type, whether required, its default, and an example for non-obvious values.

**Acceptance Scenarios**:

1. **Given** any key in values.yaml, **When** an operator reads the inline comment above it, **Then** they know the type, required/optional status, default, and (for non-obvious values) an example.
2. **Given** HELM_VALUES.md Section 2, **When** an operator searches for a Kafka configuration value, **Then** they find a table row with description, type, default, and required flag.
3. **Given** values.schema.json, **When** `helm install` is run with an invalid value, **Then** the error cites the exact field path and constraint.

---

### User Story 3 — Troubleshoot a Failed Deployment (Priority: P2)

An operator whose deployment has a CrashLoopBackOff or connection refused error opens HELM_VALUES.md Section 9 and finds the root cause and fix within 5 minutes.

**Why this priority**: Operators spend more time debugging than deploying. A good troubleshooting section prevents repeated support escalations.

**Independent Test**: Each of the top 10 errors has a cause, diagnostic command, and fix in the troubleshooting section.

**Acceptance Scenarios**:

1. **Given** a pod in CrashLoopBackOff, **When** the operator reads the troubleshooting section for that service, **Then** they find at least 3 common causes and the `kubectl logs` command to diagnose.
2. **Given** "database connection refused", **When** the operator reads the PostgreSQL troubleshooting entry, **Then** they find steps covering credentials, SSL mode, network policy, and host resolution.
3. **Given** Kafka consumer not receiving messages, **When** the operator reads the Kafka entry, **Then** they find commands to verify topic existence, consumer group offset, and SASL config.

---

### User Story 4 — Scale the Deployment for Production (Priority: P2)

An operator planning a production deployment consults the Scaling Guide to pick appropriate replica counts and resource limits for their listing volume and country count.

**Why this priority**: Under-provisioned production deployments cause incidents; over-provisioned ones waste budget. The guide eliminates guesswork.

**Independent Test**: The Scaling Guide has three tiers (Small/Medium/Large) with concrete replica counts, memory limits, and HPA settings per service.

**Acceptance Scenarios**:

1. **Given** < 10k listings and 1 country, **When** the operator reads the Small profile, **Then** they find specific `replicaCount`, memory requests/limits, and HPA min/max for every service.
2. **Given** 100k+ listings and 15+ countries, **When** the operator reads the Large profile, **Then** they find HA configuration with HPA enabled and multi-replica settings.
3. **Given** any scaling profile, **When** the operator copies its values into their override file, **Then** `helm lint` passes with those values.

---

### User Story 5 — Validate Schema Before Deploying (Priority: P2)

An operator running `helm install` with a missing required field or invalid enum receives a meaningful Helm schema validation error before any Kubernetes resources are created.

**Why this priority**: Schema validation prevents partial installs caused by misconfiguration — catching errors at `helm install` time rather than at pod startup.

**Independent Test**: Running `helm install` with `kafka.brokers: ""` or `postgresql.external.sslmode: "invalid"` produces a schema validation error with the field name and constraint.

**Acceptance Scenarios**:

1. **Given** `kafka.brokers` is empty, **When** `helm install` runs, **Then** schema validation fails with a message identifying `kafka.brokers` as required.
2. **Given** `postgresql.external.sslmode: "optional"` (invalid enum), **When** `helm install` runs, **Then** the error lists the valid enum values.
3. **Given** all valid values, **When** `helm lint` is run against all four value profiles, **Then** schema validation passes with zero errors.

---

### Edge Cases

- What if an operator uses both a `sealedSecrets` block and a manually created Secret with the same name? The SealedSecret controller overwrites the manual Secret; this must be documented.
- What if `grafana.dashboards.namespace` is set to a namespace that doesn't exist? Dashboard ConfigMaps are created but never picked up; the troubleshooting section covers this.
- What if the operator sets `kafka.sasl.enabled: true` but does not create `kafka.sasl.credentialsSecret`? The pod starts but Kafka connection fails at runtime — documented in troubleshooting.
- What if values.schema.json has stricter constraints than the actual templates accept? Schema errors block valid deployments; all schema constraints must be tested against all four value profiles.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every key in values.yaml MUST have an inline comment using the `# --` convention specifying description, type, required/optional, default, and example (for non-obvious values).
- **FR-002**: HELM_VALUES.md MUST contain all 9 sections as specified, in order.
- **FR-003**: HELM_VALUES.md Quick Start section MUST include copy-paste `kubectl create secret` commands for every required Secret with exact key names.
- **FR-004**: HELM_VALUES.md Section 2 MUST document every external service value in a table with columns: value path, description, type, default, required.
- **FR-005**: HELM_VALUES.md Section 4 MUST list every required Kubernetes Secret, its namespace, all expected keys, and a `kubectl create secret generic` command to create it.
- **FR-006**: HELM_VALUES.md Section 9 MUST cover at least the top 10 deployment errors, each with diagnostic commands and fixes.
- **FR-007**: values.schema.json MUST mark all required fields, provide enum constraints for `sslmode` and `sasl.mechanism`, and provide pattern constraints for broker addresses and URLs.
- **FR-008**: `helm lint` MUST pass against values.yaml, values-staging.yaml, values-test.yaml with the updated schema.
- **FR-009**: README.md in `helm/estategap/` MUST exist with a short description of the chart and a link to HELM_VALUES.md.
- **FR-010**: The comment convention MUST be consistent across the entire values.yaml file — no values left without a comment.

### Key Entities

- **values.yaml**: YAML configuration file; every key annotated with inline `# --` comments.
- **HELM_VALUES.md**: Standalone reference document with 9 sections; lives at `helm/estategap/HELM_VALUES.md`.
- **values.schema.json**: JSON Schema (draft 2020-12) for Helm values validation; lives at `helm/estategap/values.schema.json`.
- **README.md**: Chart root intro file; lives at `helm/estategap/README.md`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `helm lint helm/estategap` passes with zero errors against all four value profiles (base, staging, test, and a minimal override with only required fields).
- **SC-002**: Running `helm install` with a missing required value produces a schema validation error naming the exact field.
- **SC-003**: Every key in values.yaml has an inline `# --` comment (verifiable by diffing the annotated file against the unannotated original — zero unannotated keys remain).
- **SC-004**: HELM_VALUES.md contains all 9 sections with at least one copy-paste-ready code block per section.
- **SC-005**: The Required Secrets table in HELM_VALUES.md lists every Secret referenced in the chart templates with exact key names (verifiable by grep-ing templates against the table).
- **SC-006**: The Scaling Guide contains three tiers with concrete values for every major service.
- **SC-007**: The Troubleshooting section contains at least 10 distinct error scenarios with diagnostic commands.

## Assumptions

- The existing values.yaml, values-staging.yaml, values-test.yaml are the authoritative source of truth for all configurable values.
- The existing values.schema.json is extended (not replaced) — existing validations are preserved and new ones added.
- No new Helm template functionality is introduced; this feature is documentation-only.
- The `helm/estategap/` directory is the chart root and is where README.md, HELM_VALUES.md, and values.schema.json live.
- All Secret names referenced in templates are discovered by reading templates; no interviews with service owners are required.
- The Migration Guide (v2 → v3) refers to the brownfield migration completed in features 033–035 (NATS→Kafka, MinIO→S3, external infra refactor).
