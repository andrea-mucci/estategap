# Implementation Plan: Kubernetes Infrastructure

**Branch**: `003-k8s-infrastructure` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/003-k8s-infrastructure/spec.md`

## Summary

Deploy the complete Kubernetes infrastructure for the EstateGap platform as code: NATS JetStream cluster with 8 pre-configured streams, PostgreSQL 16 + PostGIS 3.4 via CloudNativePG, Redis 7 with Sentinel, MinIO object storage, the full observability stack (Prometheus/Grafana/Loki/Tempo), and an ArgoCD Application CR for GitOps. All resources are declared in a single Helm umbrella chart (`helm/estategap/`) with per-environment values overrides, Sealed Secrets for all sensitive config, Traefik IngressRoutes for external access, and NetworkPolicies enforcing least-privilege namespace isolation.

## Technical Context

**Language/Version**: YAML (Helm/Kubernetes manifests), Go 1.23 (application services), Python 3.12 (application services), TypeScript 5.x / Node 22 (frontend)
**Primary Dependencies**: Helm 3.14+, NATS nats-io/nats chart, CloudNativePG 0.x, Bitnami Redis 19.x, kube-prometheus-stack 58.x, grafana/loki-stack 2.x, grafana/tempo 1.x, KEDA 2.x (for NATS-based HPA)
**Storage**: PostgreSQL 16 + PostGIS 3.4 (200Gi), Redis 7 (8Gi), MinIO (50Gi), NATS (10Gi × 3 replicas), Prometheus (50Gi), Loki (20Gi), Grafana (10Gi), Tempo (10Gi)
**Testing**: `helm lint`, `helm template --validate`, `helm install --dry-run`, post-deploy smoke tests via kubectl exec
**Target Platform**: Kubernetes 1.28+ (cloud-agnostic)
**Project Type**: Infrastructure-as-code / platform bootstrap
**Performance Goals**: NATS 100k msg/s, PostgreSQL replication lag < 1s, API gateway p95 < 50ms
**Constraints**: No plain-text secrets in git; all config declarative; Traefik + cert-manager + Sealed Secrets + CloudNativePG operator pre-installed
**Scale/Scope**: 6 application namespaces, 9 application services, 7 infrastructure services

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Helm chart provides deployment manifests for Go, Python, and Next.js services as separate Deployments in separate namespaces |
| II. Event-Driven Communication | ✅ PASS | NATS JetStream deployed with all 8 required streams. No HTTP inter-service routing defined in the infra layer |
| III. Country-First Data Sovereignty | ✅ PASS | PostgreSQL 16 + PostGIS 3.4 deployed; Redis 7 and MinIO also deployed per constitution |
| IV. ML-Powered Intelligence | ✅ PASS | MinIO buckets `ml-models` and `training-data` provisioned; ONNX model storage path ready |
| V. Code Quality Discipline | ✅ PASS | `helm lint` and `helm template --validate` enforced in CI; no runtime code added |
| VI. Security & Ethical Scraping | ✅ PASS | All secrets stored as Sealed Secrets; NetworkPolicies enforce least-privilege; no plain-text secrets committed |
| VII. Kubernetes-Native Deployment | ✅ PASS | This feature directly implements Principle VII — all services containerized, Helm charts in `helm/`, ArgoCD GitOps |

**No violations. Gate passed.**

*Post-Phase-1 re-check*: The data-model.md confirms all Kubernetes resource relationships are consistent with the constitution. Sealed Secrets, NetworkPolicies, and ArgoCD Application CR are all defined. No new violations introduced.

## Project Structure

### Documentation (this feature)

```text
specs/003-k8s-infrastructure/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 — technology decisions and rationale
├── data-model.md        # Phase 1 — K8s resource model
├── quickstart.md        # Phase 1 — deploy and verify guide
├── contracts/
│   └── helm-values-schema.md   # Phase 1 — full values.yaml interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
helm/estategap/
├── Chart.yaml                    # Chart metadata + dependency list
├── values.yaml                   # Production defaults
├── values-staging.yaml           # Staging overrides
├── values-production.yaml        # Production overrides
└── templates/
    ├── _helpers.tpl              # Named template helpers (already exists)
    ├── namespaces.yaml           # 6 application namespaces
    ├── configmap.yaml            # estategap-config (DB/Redis/NATS/MinIO endpoints)
    ├── sealed-secrets.yaml       # SealedSecret CRs (generated via kubeseal)
    ├── network-policies.yaml     # Namespace egress/ingress rules
    ├── ingress.yaml              # Traefik IngressRoute CRs
    ├── certificates.yaml         # cert-manager Certificate CR
    ├── nats-streams-job.yaml     # Job: post-install NATS stream creation
    ├── postgresql-cluster.yaml   # CloudNativePG Cluster CR
    ├── postgresql-backup.yaml    # ScheduledBackup CR
    ├── minio.yaml                # MinIO StatefulSet + Service
    ├── minio-setup-job.yaml      # Job: post-install bucket creation
    ├── argocd-application.yaml   # ArgoCD Application CR
    ├── keda-scaledobject.yaml    # ScaledObject for spider-workers
    └── services/
        ├── api-gateway.yaml      # Deployment + Service + HPA
        ├── websocket-server.yaml
        ├── alert-engine.yaml
        ├── scrape-orchestrator.yaml
        ├── spider-workers.yaml
        ├── pipeline.yaml
        ├── ml-scorer.yaml
        ├── ai-chat.yaml
        └── frontend.yaml
```

**Structure Decision**: Umbrella chart with sub-chart dependencies for infrastructure components. Application service templates are inline in `templates/services/` to share the chart's values context. This avoids the complexity of separate per-service charts while keeping all services parameterized.

## Complexity Tracking

> No constitution violations. This section is empty.

---

## Phase 0 Output

See [research.md](./research.md) — all NEEDS CLARIFICATION items resolved. Key decisions:
- NATS streams created via post-install Helm Job (not init container)
- MinIO in standalone mode (not operator)
- ArgoCD Application CR inline template (not AppProject)
- KEDA added as dependency for spider-worker NATS-based autoscaling
- `prune: false` in ArgoCD sync policy for staging safety

---

## Phase 1 Output

See:
- [data-model.md](./data-model.md) — complete Kubernetes resource topology
- [contracts/helm-values-schema.md](./contracts/helm-values-schema.md) — full values.yaml interface
- [quickstart.md](./quickstart.md) — step-by-step deploy and verify guide

---

## Implementation Phases (for /speckit.tasks)

The following phases describe the sequencing for `tasks.md` generation:

### Phase A — Chart Skeleton & Namespaces
1. Update `Chart.yaml` with full dependency list (NATS, cnpg, Redis, kube-prometheus-stack, loki-stack, Tempo, KEDA)
2. Expand `values.yaml` with the complete schema from [contracts/helm-values-schema.md](./contracts/helm-values-schema.md)
3. Create `values-staging.yaml` and `values-production.yaml`
4. Write `templates/namespaces.yaml` — 6 namespaces with labels
5. Write `templates/configmap.yaml` — estategap-config ConfigMap
6. Write `templates/_helpers.tpl` additions (namespace helper, service image helper)

### Phase B — Security Layer
7. Document `templates/sealed-secrets.yaml` template structure (actual values sealed separately)
8. Write `templates/network-policies.yaml` — per-namespace egress rules

### Phase C — Infrastructure Services
9. Configure NATS sub-chart values in `values.yaml`
10. Write `templates/nats-streams-job.yaml` — post-install Job
11. Configure CloudNativePG sub-chart + write `templates/postgresql-cluster.yaml`
12. Write `templates/postgresql-backup.yaml` — ScheduledBackup CR
13. Configure Bitnami Redis sub-chart values
14. Write `templates/minio.yaml` — MinIO StatefulSet + Services
15. Write `templates/minio-setup-job.yaml` — bucket creation Job

### Phase D — Observability
16. Configure kube-prometheus-stack sub-chart values (custom scrape configs, Grafana ingress)
17. Configure loki-stack sub-chart values (Promtail DaemonSet)
18. Configure Tempo sub-chart values
19. Write Grafana datasource ConfigMap for Loki + Tempo

### Phase E — Ingress & TLS
20. Write `templates/certificates.yaml` — cert-manager Certificate CR
21. Write `templates/ingress.yaml` — Traefik IngressRoutes (app, api, ws, grafana)

### Phase F — Application Service Templates
22. Write `templates/services/api-gateway.yaml` — Deployment + Service + HPA
23. Write `templates/services/websocket-server.yaml`
24. Write `templates/services/alert-engine.yaml`
25. Write `templates/services/scrape-orchestrator.yaml`
26. Write `templates/services/spider-workers.yaml`
27. Write `templates/services/pipeline.yaml`
28. Write `templates/services/ml-scorer.yaml` + HPA
29. Write `templates/services/ai-chat.yaml` + HPA
30. Write `templates/services/frontend.yaml`
31. Write `templates/keda-scaledobject.yaml` — spider-workers NATS scaler

### Phase G — GitOps
32. Write `templates/argocd-application.yaml` — Application CR

### Phase H — Validation & CI
33. Add `helm lint` + `helm template --validate` to CI pipeline
34. Write smoke test script (`scripts/smoke-test.sh`) for post-deploy verification
35. Run `helm dependency update` and commit `Chart.lock`
