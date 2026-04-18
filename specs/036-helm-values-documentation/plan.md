# Implementation Plan: Helm Chart Values Documentation

**Branch**: `036-helm-values-documentation` | **Date**: 2026-04-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/036-helm-values-documentation/spec.md`

## Summary

Add exhaustive inline documentation to `helm/estategap/values.yaml` using the `# --` helm-docs convention, rewrite `HELM_VALUES.md` with 9 operator-oriented sections, enhance `values.schema.json` with enum/pattern constraints, and create `helm/estategap/README.md`. This is a pure documentation change — no template logic, no application code.

## Technical Context

**Language/Version**: YAML (Helm 3.14+), JSON Schema 2020-12, Markdown
**Primary Dependencies**: Helm 3.14+; no new packages
**Storage**: N/A
**Testing**: `helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml` and against values-test.yaml
**Target Platform**: Kubernetes cluster (any version compatible with Helm 3.14+)
**Project Type**: Helm chart documentation
**Performance Goals**: N/A (documentation)
**Constraints**: Schema must not break existing `helm lint` for all four value profiles
**Scale/Scope**: ~150 values across 15 top-level sections, 13 services

## Constitution Check

**Principle VII (Brownfield Kubernetes-Native Deployment)**:
> "Every Helm value MUST be documented in `values.yaml` comments AND in a dedicated `HELM_VALUES.md`."

This feature directly fulfills this constitutional requirement. **GATE: PASS** — this work is mandated by the constitution, not a violation.

**Principle VI (Security & Ethical Scraping)**:
> "Secrets management: No secrets in code, ever."

The documentation must reinforce this — examples must use `kubectl create secret` commands with `--from-literal`, never hardcoded values. HELM_VALUES.md must explicitly warn against putting secrets directly in `values.yaml`. **GATE: PASS**

No violations. No Complexity Tracking table needed.

## Project Structure

### Documentation (this feature)

```text
specs/036-helm-values-documentation/
├── plan.md              # This file
├── research.md          # Phase 0 output (complete)
├── quickstart.md        # Phase 1 output — Quick Start section draft
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (modified files)

```text
helm/estategap/
├── values.yaml                  # MODIFY — add # -- comments to every key
├── HELM_VALUES.md               # REWRITE — 9-section operator reference
├── values.schema.json           # ENHANCE — enum/pattern constraints
└── README.md                    # CREATE — short intro + link to HELM_VALUES.md
```

## Phase 0: Research

**Status**: COMPLETE — see [research.md](./research.md)

Resolved:
- Comment convention: `# --` helm-docs format
- Full secret inventory: 8 Secrets with exact key names (see research.md §2)
- All ~150 values catalogued (see research.md §3)
- JSON Schema enhancement strategy (see research.md §4)
- Top 10 deployment errors (see research.md §8)

## Phase 1: Design & Contracts

### values.yaml — Comment Convention Applied to All Sections

Every key follows this pattern:
```yaml
# -- One-line description of what this value controls.
# Type: string | int | bool | object | list
# Required: yes | no
# Default: "value" (or: none — must be provided)
# Example: "kafka-bootstrap.kafka.svc.cluster.local:9092"  # (non-obvious values only)
key: value
```

**Section-by-section documentation plan**:

**global** (3 keys):
```yaml
# -- Override storage class for all PersistentVolumeClaims in this chart.
# Type: string
# Required: no
# Default: "" (uses cluster default storage class)
storageClass: ""

# -- Prefix registry for all service images (e.g., a private mirror).
# Type: string
# Required: no
# Default: "" (uses image repository as-is)
# Example: "registry.internal.company.com"
imageRegistry: ""

# -- List of image pull secret names injected into all pod specs.
# Type: list
# Required: no
# Default: [] (no pull secrets)
imagePullSecrets: []
```

**cluster** (3 keys — environment has enum constraint):
```yaml
# -- Deployment environment name. Injected as CLUSTER_ENVIRONMENT into all pods.
# Type: string
# Required: yes
# Default: "staging"
# Allowed: "test" | "staging" | "production"
environment: staging
```

**components** (6 feature flags):
Each flag gets:
```yaml
# -- Deploy Bitnami Redis sub-chart. Set false to use an external Redis.
# Type: bool
# Required: no
# Default: true
# Note: Redis is self-deployed by EstateGap (not available as shared cluster service).
deploy: true
```

**kafka** (13 keys — all annotated):

`brokers` — required, pattern-constrained in schema
`topicPrefix` — required, pattern-constrained
`tls.enabled`, `tls.caSecret` — conditional group
`sasl.enabled`, `sasl.mechanism` (enum), `sasl.credentialsSecret` — conditional group
`consumer.maxRetries` — int with minimum
`topicInit.enabled`, `topicInit.replicationFactor`, `topicInit.image` — init job controls
`deadLetter.enabled`, `deadLetter.retentionDays` — DLQ controls

**postgresql** (11 keys — all annotated):

`external.host`, `external.port`, `external.database` — required group
`external.sslmode` — enum (disable/require/verify-ca/verify-full)
`external.credentialsSecret` — required, keys: PGUSER, PGPASSWORD
`readReplica.enabled`, `readReplica.host`, `readReplica.port` — replica group
`migrations.enabled`, `migrations.image`, `migrations.timeout` — migration job controls

**redis** (13 keys — Bitnami pass-through subset):

`fullnameOverride` — controls Service DNS name (must be "redis" for internal resolution)
`architecture` — enum: standalone/replication
`auth.enabled`, `auth.existingSecret`, `auth.existingSecretPasswordKey`
`sentinel.enabled`, `sentinel.quorum`
`master.persistence.size`, `master.resources`
`replica.replicaCount`, `replica.persistence.size`, `replica.resources`
`commonConfiguration` — Redis server config block

**s3** (10 keys — all required except buckets):

`endpoint` — required, must be https URL
`region`, `bucketPrefix`, `forcePathStyle`, `credentialsSecret` — all required
`buckets.mlModels`, `buckets.trainingData`, `buckets.listingPhotos`, `buckets.exports`, `buckets.backups`

**prometheus** (5 keys):

`serviceMonitor.enabled`, `serviceMonitor.interval`, `serviceMonitor.labels`
`rules.enabled`, `rules.labels`
Note: labels.release must match Prometheus operator's `serviceMonitorSelector`

**grafana** (4 keys):

`dashboards.enabled`, `dashboards.namespace`, `dashboards.labels`
Note: namespace must match Grafana sidecar watched namespace

**keda** (1 key): `enabled`

**argocd** (7 keys): `enabled`, `applicationName`, `repoURL` (required if enabled), `targetRevision`, `valueFiles`, `syncPolicy.prune`, `syncPolicy.selfHeal`

**sealedSecrets** (9 subsections):
Each subsection annotated as a block with a comment explaining which Secret it creates, in which namespace, and which service consumes it. Individual keys documented as "encrypted value — replace with `kubeseal` output".

**stripe** (11 keys): URLs annotated with note about Stripe Dashboard source. Price IDs annotated with note they come from Stripe Dashboard.

**mlTrainer** (6 keys): image, schedule (cron), pushgateway URL, resources

**mlScorer** (7 keys): all ports, batch sizes, intervals, shapTimeoutSeconds

**gdpr** (12 keys): cron config, database/redis connection with secretRef pattern

**loadTests** (9 keys): all annotated, note that `enabled: false` by default

**services** (13 services):
For each service, annotate common sub-keys once with a comment at the top explaining the pattern, then annotate unique sub-keys:
- `enabled` — deploy this service (bool, default: true)
- `namespace` — Kubernetes namespace for this service's resources (string, must not be changed without updating network policies)
- `replicaCount` — initial replica count (overridden by HPA when enabled)
- `port` — container port; also used by Service spec
- `image.repository`, `image.tag`
- `resources.requests/limits`
- `env.*` — service-specific environment overrides
- `livenessProbe`, `readinessProbe`
- `serviceMonitor.enabled`, `serviceMonitor.path`, `serviceMonitor.interval`
- `hpa.enabled`, `hpa.minReplicas`, `hpa.maxReplicas`, `hpa.cpuTarget`
- `keda.*` (spider-workers only)
- `config.*` (alert-dispatcher only)

---

### values.schema.json — Enhancements

Add to existing schema (targeted additions only):

1. **`kafka` $def** — add `required: ["brokers"]` and patterns:
   ```json
   "brokers": {
     "type": "string",
     "minLength": 1,
     "pattern": "^[a-z0-9._-]+(:[0-9]+)?(,[a-z0-9._-]+(:[0-9]+)?)*$"
   },
   "topicPrefix": {
     "type": "string",
     "minLength": 1,
     "pattern": "^[a-z0-9._-]+$"
   }
   ```
   Add SASL mechanism enum:
   ```json
   "mechanism": {
     "type": "string",
     "enum": ["PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"]
   }
   ```

2. **`postgresql` $def → external** — add `required: ["host", "database", "credentialsSecret"]` and sslmode enum:
   ```json
   "sslmode": {
     "type": "string",
     "enum": ["disable", "require", "verify-ca", "verify-full"],
     "default": "require"
   }
   ```

3. **`s3` $def** — add `required: ["endpoint", "region", "bucketPrefix", "credentialsSecret"]` and endpoint pattern:
   ```json
   "endpoint": {
     "type": "string",
     "minLength": 1,
     "pattern": "^https?://"
   }
   ```

4. **`cluster` $def** — `required: ["environment", "domain"]` already implied; confirm environment enum is enforced.

---

### HELM_VALUES.md — 9-Section Structure

**Section 1: Quick Start**
Content:
- Prerequisites checklist (cluster version, Helm, cert-manager, Prometheus operator, Kafka, PostgreSQL, S3 bucket)
- Step 1: Create required Secrets (copy-paste kubectl commands for each Secret)
- Step 2: Minimal values-override.yaml (copy-paste template with only required fields)
- Step 3: `helm install` command with namespace creation
- Step 4: Verify deployment (kubectl get pods, helm status)

**Section 2: External Services Reference**
Subsections: Kafka, PostgreSQL, S3 Object Storage, Prometheus, Grafana
Each subsection:
- Table: Value Path | Description | Type | Default | Required
- Authentication subsection (options, secret format)
- Connection verification command
- Troubleshooting mini-table

**Section 3: Application Services Reference**
Table of all 13 services with: service name, namespace, port, health endpoints, HPA (Y/N), KEDA (Y/N)
Per-service detail: environment variables (from ConfigMap + service-specific), resource tiers, feature flags

**Section 4: Security Configuration**
Required Secrets table (as in user specification):
| Secret Name | Namespace | Required Keys | Used By |
Full `kubectl create secret generic` command for each Secret.
Sealed Secrets workflow explanation.
TLS/Ingress certificate configuration.
Network policies explanation (egress restrictions per namespace tier).

**Section 5: Observability Configuration**
ServiceMonitor setup and label matching.
How to verify scraping (`kubectl get servicemonitor`, Prometheus targets UI).
Grafana dashboard ConfigMap sidecar setup.
PrometheusRule alert table with thresholds.
Log format (structured JSON, key fields).

**Section 6: Feature Flags**
Table of all `components.*.deploy` flags with implications.
Dependency matrix table:
| Service | Needs PostgreSQL | Needs Kafka | Needs Redis | Needs S3 |

**Section 7: Scaling Guide**
Three-tier table (Small/Medium/Large) as specified.
Per-service resource and replica recommendations.
HPA tuning guidance.
KEDA spider-workers lag threshold guidance.

**Section 8: Migration Guide (v2 → v3)**
Pre-migration checklist.
values.yaml diff (removed keys, added keys, renamed keys).
Data migration steps (none — schema unchanged by 033-035).
Rollback procedure (helm rollback + kubectl commands).

**Section 9: Troubleshooting**
10 error scenarios from research.md §8, each with:
- Error symptom
- Diagnostic commands
- Root causes
- Fix

---

### README.md — Chart Root

Short file (< 60 lines) with:
- Chart name and one-line description
- Minimum Helm/K8s requirements
- Quick `helm install` snippet
- Link to HELM_VALUES.md for full reference
- Link to spec HELM_VALUES.md sections

---

### quickstart.md (Spec artifact)

Draft of Quick Start section content for review before integration into HELM_VALUES.md.

---

## Agent Context Update

After writing the plan, run the agent context update script:
`.specify/scripts/bash/update-agent-context.sh claude`

## Implementation Sequence

Tasks are ordered to avoid rework:

1. **Read and annotate values.yaml** — inline `# --` comments on every key (largest single task, ~150 keys)
2. **Enhance values.schema.json** — add enum/pattern constraints (targeted additions)
3. **Rewrite HELM_VALUES.md** — 9 sections using research.md as the data source
4. **Create README.md** — short intro pointing to HELM_VALUES.md
5. **Validate** — `helm lint` against all value profiles; verify schema rejects invalid values

## Verification Commands

```bash
# Lint against all profiles
helm lint helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml

helm lint helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-test.yaml

# Template renders cleanly
helm template estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  --dry-run > /dev/null

# Schema rejects invalid sslmode
helm lint helm/estategap --set postgresql.external.sslmode=optional
# Expected: Error: ... enum

# Schema rejects missing kafka.brokers
helm lint helm/estategap --set kafka.brokers=""
# Expected: Error: ... minLength

# Count unannotated keys (should be 0 after task 1)
grep -c "^  [a-z]" helm/estategap/values.yaml
# Compare with annotated count
grep -c "^# --" helm/estategap/values.yaml
```
