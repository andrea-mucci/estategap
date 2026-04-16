# Research: Kubernetes Infrastructure

**Feature**: 003-k8s-infrastructure
**Phase**: 0 — Outline & Research
**Date**: 2026-04-16

---

## 1. Helm Chart Architecture

**Decision**: Single umbrella chart (`helm/estategap/`) with sub-charts as Helm dependencies for infrastructure components; application service templates rendered inline.

**Rationale**: Infrastructure components (NATS, PostgreSQL, Redis, MinIO, observability) have established, maintained Helm charts. Pulling them in as `dependencies` in `Chart.yaml` avoids re-implementing already-solved packaging. Application service templates (Deployments, Services, HPAs) are rendered inline in the umbrella chart since they share the same values context.

**Alternatives considered**:
- Separate chart per service: rejected — too much duplication for a monorepo with 9+ services; upgrade coordination becomes complex.
- Kustomize instead of Helm: rejected — the team has chosen Helm per the constitution and existing `helm/` directory.
- Helmfile overlay: valid future enhancement; not required for initial bootstrap.

**Chart.yaml dependencies block** (final list):
```yaml
dependencies:
  - name: nats
    repository: https://nats-io.github.io/k8s/helm/charts
    version: "1.x.x"
    alias: nats
  - name: cloudnative-pg  # operator CRDs + controller
    repository: https://cloudnative-pg.github.io/charts
    version: "0.x.x"
    alias: cnpg
  - name: redis
    repository: https://charts.bitnami.com/bitnami
    version: "19.x.x"
    alias: redis
  - name: kube-prometheus-stack
    repository: https://prometheus-community.github.io/helm-charts
    version: "58.x.x"
    alias: prometheus
  - name: loki-stack
    repository: https://grafana.github.io/helm-charts
    version: "2.x.x"
    alias: loki
  - name: tempo
    repository: https://grafana.github.io/helm-charts
    version: "1.x.x"
    alias: tempo
```

MinIO and ArgoCD Application CR are deployed as inline templates (not chart dependencies) — MinIO because the operator vs standalone decision favors standalone for simplicity; ArgoCD Application because ArgoCD must already be running to apply the CR.

---

## 2. NATS JetStream Configuration

**Decision**: `nats-io/nats` Helm chart, StatefulSet with 3 replicas, JetStream enabled, 10Gi PVC per replica. Streams created by a Kubernetes Job (not an init container) that runs after the StatefulSet is Ready.

**Rationale**: The NATS chart renders a StatefulSet. A separate post-install Job using the `nats-box` image ensures idempotent stream creation (`nats stream add --config`) without coupling stream setup to pod startup. Init containers on StatefulSet pods are unsuitable here because each pod would race to create streams.

**Stream configuration** (all streams):
| Stream | Subjects | Retention | MaxAge | Replicas |
|--------|----------|-----------|--------|----------|
| raw-listings | listings.raw.> | Limits | 7d | 3 |
| normalized-listings | listings.normalized.> | Limits | 7d | 3 |
| enriched-listings | listings.enriched.> | Limits | 30d | 3 |
| scored-listings | listings.scored.> | Limits | 30d | 3 |
| alerts-triggers | alerts.triggers.> | WorkQueue | 24h | 3 |
| alerts-notifications | alerts.notifications.> | Limits | 7d | 3 |
| scraper-commands | scraper.commands.> | WorkQueue | 1h | 3 |
| price-changes | listings.price-change.> | Limits | 90d | 3 |

**Alternatives considered**:
- Init container on each pod: rejected — race condition on stream creation; NATS only needs stream creation once per cluster lifecycle.
- Helm hooks (`post-install` Job): selected — ensures Job runs after NATS StatefulSet is ready.

---

## 3. PostgreSQL / CloudNativePG

**Decision**: CloudNativePG operator deployed as Helm chart dependency; Cluster CR defined as an inline Helm template. PostGIS enabled via `initdb.postInitSQL`. Backup via barman to MinIO S3-compatible endpoint.

**Cluster CR topology**:
```yaml
spec:
  instances: 2          # 1 primary + 1 standby replica
  primaryUpdateStrategy: unsupervised
  storage:
    size: 200Gi
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "256MB"
  bootstrap:
    initdb:
      postInitSQL:
        - CREATE EXTENSION IF NOT EXISTS postgis;
        - CREATE EXTENSION IF NOT EXISTS postgis_topology;
  backup:
    barmanObjectStore:
      destinationPath: s3://backups/postgresql
      endpointURL: http://minio.estategap-system.svc:9000
      s3Credentials:
        accessKeyId:
          name: postgresql-backup-credentials
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: postgresql-backup-credentials
          key: SECRET_ACCESS_KEY
    retentionPolicy: "30d"
  scheduledBackup:
    - name: daily-backup
      schedule: "0 2 * * *"   # 02:00 UTC daily
```

**Rationale**: CloudNativePG is the de facto standard K8s-native PostgreSQL operator. Barman integration provides production-grade point-in-time recovery (PITR). MinIO as the backup target avoids cloud vendor lock-in.

**Alternatives considered**:
- Zalando Postgres Operator: rejected — CloudNativePG has stronger community momentum and better CNPG-specific tooling.
- Manual WAL archiving: rejected — barman integration is first-class in CloudNativePG.

---

## 4. Redis — Standalone + Sentinel

**Decision**: Bitnami Redis chart, `architecture: replication` with Sentinel enabled. 1 master + 1 replica. `maxmemory 1gb`, `maxmemory-policy allkeys-lru`. AOF `appendonly yes`.

**Rationale**: Sentinel provides automatic failover without Redis Cluster complexity (which requires client-side sharding). 1 replica is sufficient for a platform at this stage — Sentinel needs only 1 master + 1 replica + Sentinel processes.

**Key `values.yaml` overrides**:
```yaml
redis:
  architecture: replication
  auth:
    existingSecret: redis-credentials
    existingSecretPasswordKey: redis-password
  master:
    persistence:
      enabled: true
      size: 8Gi
    resources:
      limits:
        memory: 1Gi
  replica:
    replicaCount: 1
  sentinel:
    enabled: true
    quorum: 2
  commonConfiguration: |
    maxmemory 1gb
    maxmemory-policy allkeys-lru
    appendonly yes
    appendfsync everysec
```

---

## 5. MinIO — Standalone

**Decision**: Standalone MinIO deployed as a Kubernetes StatefulSet (inline Helm template, not the MinIO Operator). 50Gi PVC. Buckets created by a post-install Kubernetes Job using the `mc` (MinIO Client) image.

**Rationale**: The MinIO Operator is designed for distributed, multi-tenant setups. Standalone is simpler, easier to debug, and sufficient for initial platform needs. Migration to operator-mode is a future concern.

**Bucket creation Job** (idempotent):
```bash
mc alias set minio http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD
for bucket in ml-models training-data listing-photos exports backups; do
  mc mb --ignore-existing minio/$bucket
done
```

---

## 6. Observability Stack

**Decision**: Three separate Helm releases via chart dependencies:
1. `kube-prometheus-stack` — Prometheus, Grafana, AlertManager, node-exporter, kube-state-metrics
2. `loki-stack` — Loki + Promtail DaemonSet
3. `grafana/tempo` — distributed tracing backend

**Grafana data sources** (provisioned via ConfigMap):
- Prometheus: `http://prometheus-operated:9090`
- Loki: `http://loki:3100`
- Tempo: `http://tempo:3100`

**Custom scrape configs** (PodMonitor CRs per service namespace):
```yaml
# PodMonitor per namespace — services must expose /metrics on port 9090
namespaces: [estategap-gateway, estategap-scraping, estategap-pipeline,
             estategap-intelligence, estategap-notifications]
```

**Grafana ingress**: Traefik IngressRoute at `grafana.estategap.com` with TLS.

---

## 7. ArgoCD GitOps

**Decision**: ArgoCD Application CR (not AppProject or ApplicationSet for v1). Source: `helm/estategap/` in the repo. Target namespace: `estategap-system`. Auto-sync enabled with `prune: false` (to avoid accidental resource deletion during iteration).

```yaml
spec:
  source:
    repoURL: https://github.com/org/estategap
    targetRevision: main
    path: helm/estategap
    helm:
      valueFiles:
        - values-staging.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: estategap-system
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
```

**Rationale**: `selfHeal: true` ensures that manual `kubectl` edits are reverted. `prune: false` for staging prevents accidental deletion during early development when the chart is actively changing.

---

## 8. Networking & TLS

**Decision**:
- Traefik IngressRoute CRDs (pre-installed on cluster) used for all external routing.
- cert-manager `Certificate` resources with `Let's Encrypt` ClusterIssuer for TLS.
- NetworkPolicies using label-based namespace selectors.

**NetworkPolicy matrix**:
| Source Namespace | Destinations |
|-----------------|--------------|
| estategap-gateway | All namespaces + external |
| estategap-scraping | estategap-system only (NATS, DB, Redis) |
| estategap-pipeline | estategap-system only |
| estategap-intelligence | estategap-system only |
| estategap-notifications | estategap-system + estategap-gateway |
| estategap-system | Internal only (ingress from labelled namespaces) |

**Rationale**: Least-privilege network design. Pipeline/intelligence services have no reason to call the gateway or each other — only the data tier. This limits blast radius if a service is compromised.

---

## 9. HPA Strategy

| Service | Metric | Target | Min | Max |
|---------|--------|--------|-----|-----|
| api-gateway | CPU utilization | 60% | 2 | 20 |
| spider-workers | NATS `scraper-commands` consumer pending | 100 msgs | 1 | 50 |
| ml-scorer | CPU utilization | 70% | 1 | 10 |
| ai-chat | CPU utilization | 60% | 1 | 8 |

Spider-workers use KEDA `NatsJetStreamScaler` to scale on NATS queue depth. All others use standard `HorizontalPodAutoscaler` v2 with CPU metrics.

**KEDA** is added as a chart dependency for NATS-based autoscaling.

---

## 10. Resource Profiles

Default resource requests/limits defined in `values.yaml` per service tier:

| Tier | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|------------|-----------|----------------|--------------|
| light (frontend, notification) | 100m | 500m | 128Mi | 512Mi |
| medium (api-gateway, pipeline) | 250m | 1000m | 256Mi | 1Gi |
| heavy (ml-scorer, ai-chat) | 500m | 2000m | 512Mi | 4Gi |
| worker (spider-workers) | 200m | 800m | 256Mi | 1Gi |

---

## Summary of NEEDS CLARIFICATION Resolved

All aspects of the feature were specified by the user with sufficient precision. No ambiguities required external resolution. The decisions above reflect the mapping from user requirements to concrete Helm/Kubernetes patterns, with documented rationale for each choice.
