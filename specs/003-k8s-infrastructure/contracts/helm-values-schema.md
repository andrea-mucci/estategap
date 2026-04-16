# Helm Values Contract

**Feature**: 003-k8s-infrastructure
**Contract Type**: Configuration interface (Helm values)
**Date**: 2026-04-16

This document defines the Helm values interface — what consumers of the chart must provide, what has defaults, and what is required per environment.

---

## Top-Level Values Structure

```yaml
# ─────────────────────────────────────────────────────────────────────────────
# Global overrides applied to all sub-charts
# ─────────────────────────────────────────────────────────────────────────────
global:
  storageClass: ""         # Override default StorageClass
  imageRegistry: ""        # Override image registry (air-gapped)
  imagePullSecrets: []

# ─────────────────────────────────────────────────────────────────────────────
# Cluster identity
# ─────────────────────────────────────────────────────────────────────────────
cluster:
  environment: staging     # "staging" | "production"
  domain: estategap.com    # Base domain for ingress hostnames
  certIssuer: letsencrypt-staging  # cert-manager ClusterIssuer name

# ─────────────────────────────────────────────────────────────────────────────
# NATS JetStream
# ─────────────────────────────────────────────────────────────────────────────
nats:
  enabled: true
  replicas: 3
  storage:
    size: 10Gi
  jetstream:
    enabled: true
    maxMemory: 1Gi
    maxStorage: 10Gi
  streams:
    # Each entry maps to a nats stream add call in the setup Job
    - name: raw-listings
      subjects: ["listings.raw.>"]
      retention: limits
      maxAge: 7d
      replicas: 3
    - name: normalized-listings
      subjects: ["listings.normalized.>"]
      retention: limits
      maxAge: 7d
      replicas: 3
    - name: enriched-listings
      subjects: ["listings.enriched.>"]
      retention: limits
      maxAge: 30d
      replicas: 3
    - name: scored-listings
      subjects: ["listings.scored.>"]
      retention: limits
      maxAge: 30d
      replicas: 3
    - name: alerts-triggers
      subjects: ["alerts.triggers.>"]
      retention: workqueue
      maxAge: 24h
      replicas: 3
    - name: alerts-notifications
      subjects: ["alerts.notifications.>"]
      retention: limits
      maxAge: 7d
      replicas: 3
    - name: scraper-commands
      subjects: ["scraper.commands.>"]
      retention: workqueue
      maxAge: 1h
      replicas: 3
    - name: price-changes
      subjects: ["listings.price-change.>"]
      retention: limits
      maxAge: 90d
      replicas: 3

# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL (CloudNativePG Cluster CR)
# ─────────────────────────────────────────────────────────────────────────────
postgresql:
  enabled: true
  instances: 2             # 1 primary + 1 replica
  storage:
    size: 200Gi
  backup:
    enabled: true
    schedule: "0 2 * * *"  # 02:00 UTC daily
    retentionPolicy: "30d"
    minioEndpoint: ""      # Required: http://minio.estategap-system.svc:9000

# ─────────────────────────────────────────────────────────────────────────────
# Redis
# ─────────────────────────────────────────────────────────────────────────────
redis:
  enabled: true
  architecture: replication
  sentinel:
    enabled: true
    quorum: 2
  master:
    persistence:
      size: 8Gi
    resources:
      limits:
        memory: 1Gi
  replica:
    replicaCount: 1

# ─────────────────────────────────────────────────────────────────────────────
# MinIO
# ─────────────────────────────────────────────────────────────────────────────
minio:
  enabled: true
  storage:
    size: 50Gi
  resources:
    requests:
      memory: 512Mi
    limits:
      memory: 2Gi
  buckets:
    - ml-models
    - training-data
    - listing-photos
    - exports
    - backups

# ─────────────────────────────────────────────────────────────────────────────
# Observability
# ─────────────────────────────────────────────────────────────────────────────
observability:
  prometheus:
    enabled: true
    retention: 15d
    storage:
      size: 50Gi
  grafana:
    enabled: true
    storage:
      size: 10Gi
    adminPasswordSecret: grafana-credentials
  loki:
    enabled: true
    storage:
      size: 20Gi
  tempo:
    enabled: true
    storage:
      size: 10Gi

# ─────────────────────────────────────────────────────────────────────────────
# ArgoCD Application CR
# ─────────────────────────────────────────────────────────────────────────────
argocd:
  enabled: true
  repoURL: ""              # Required: https://github.com/org/estategap
  targetRevision: main
  syncPolicy:
    prune: false
    selfHeal: true

# ─────────────────────────────────────────────────────────────────────────────
# Application Services
# Each key corresponds to a service deployment template
# ─────────────────────────────────────────────────────────────────────────────
services:
  api-gateway:
    enabled: true
    namespace: estategap-gateway
    image:
      repository: ghcr.io/org/estategap/api-gateway
      tag: latest
    resources:
      requests: { cpu: 250m, memory: 256Mi }
      limits: { cpu: 1000m, memory: 1Gi }
    hpa:
      enabled: true
      minReplicas: 2
      maxReplicas: 20
      cpuTarget: 60

  websocket-server:
    enabled: true
    namespace: estategap-gateway
    image:
      repository: ghcr.io/org/estategap/websocket-server
      tag: latest
    resources:
      requests: { cpu: 250m, memory: 256Mi }
      limits: { cpu: 1000m, memory: 1Gi }

  alert-engine:
    enabled: true
    namespace: estategap-notifications
    image:
      repository: ghcr.io/org/estategap/alert-engine
      tag: latest
    resources:
      requests: { cpu: 100m, memory: 128Mi }
      limits: { cpu: 500m, memory: 512Mi }

  scrape-orchestrator:
    enabled: true
    namespace: estategap-scraping
    image:
      repository: ghcr.io/org/estategap/scrape-orchestrator
      tag: latest
    resources:
      requests: { cpu: 100m, memory: 128Mi }
      limits: { cpu: 500m, memory: 512Mi }

  spider-workers:
    enabled: true
    namespace: estategap-scraping
    image:
      repository: ghcr.io/org/estategap/spider-workers
      tag: latest
    resources:
      requests: { cpu: 200m, memory: 256Mi }
      limits: { cpu: 800m, memory: 1Gi }
    keda:
      enabled: true
      minReplicas: 1
      maxReplicas: 50
      stream: scraper-commands
      consumer: spider-worker-group
      lagThreshold: "100"

  pipeline:
    enabled: true
    namespace: estategap-pipeline
    image:
      repository: ghcr.io/org/estategap/pipeline
      tag: latest
    resources:
      requests: { cpu: 250m, memory: 256Mi }
      limits: { cpu: 1000m, memory: 1Gi }

  ml-scorer:
    enabled: true
    namespace: estategap-intelligence
    image:
      repository: ghcr.io/org/estategap/ml-scorer
      tag: latest
    resources:
      requests: { cpu: 500m, memory: 512Mi }
      limits: { cpu: 2000m, memory: 4Gi }
    hpa:
      enabled: true
      minReplicas: 1
      maxReplicas: 10
      cpuTarget: 70

  ai-chat:
    enabled: true
    namespace: estategap-intelligence
    image:
      repository: ghcr.io/org/estategap/ai-chat
      tag: latest
    resources:
      requests: { cpu: 500m, memory: 512Mi }
      limits: { cpu: 2000m, memory: 4Gi }
    hpa:
      enabled: true
      minReplicas: 1
      maxReplicas: 8
      cpuTarget: 60

  frontend:
    enabled: true
    namespace: estategap-gateway
    image:
      repository: ghcr.io/org/estategap/frontend
      tag: latest
    resources:
      requests: { cpu: 100m, memory: 128Mi }
      limits: { cpu: 500m, memory: 512Mi }
```

---

## Required Sealed Secrets (must be pre-created before helm install)

| Secret Name | Namespace | Keys |
|-------------|-----------|------|
| `estategap-app-secrets` | estategap-system | `POSTGRES_PASSWORD`, `POSTGRES_REPLICATION_PASSWORD`, `REDIS_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `LLM_API_KEY_ANTHROPIC`, `LLM_API_KEY_OPENAI`, `JWT_SECRET` |
| `postgresql-backup-credentials` | estategap-system | `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY` |
| `grafana-credentials` | monitoring | `admin-password` |
| `redis-credentials` | estategap-system | `redis-password` |

---

## Environment Overrides Contract

### `values-staging.yaml` (inherits all defaults, overrides below)
```yaml
cluster:
  environment: staging
  certIssuer: letsencrypt-staging

nats:
  replicas: 1       # Single replica for staging cost savings
  storage:
    size: 2Gi

postgresql:
  instances: 1      # No replica in staging
  storage:
    size: 20Gi

minio:
  storage:
    size: 10Gi

observability:
  prometheus:
    retention: 3d
    storage:
      size: 10Gi
```

### `values-production.yaml` (inherits all defaults, overrides below)
```yaml
cluster:
  environment: production
  certIssuer: letsencrypt-prod

services:
  api-gateway:
    hpa:
      minReplicas: 3
      maxReplicas: 50
```

---

## Validation Rules

1. `argocd.repoURL` MUST be set in environment values files — it is empty in defaults.
2. `postgresql.backup.minioEndpoint` MUST match the MinIO ClusterIP service DNS name.
3. `cluster.certIssuer` MUST reference a ClusterIssuer that exists in the cluster.
4. All `services.*.image.tag` values should be pinned to a specific digest or semver tag in production (not `latest`).
