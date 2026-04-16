# Data Model: Kubernetes Infrastructure

**Feature**: 003-k8s-infrastructure
**Phase**: 1 — Design
**Date**: 2026-04-16

This document describes the Kubernetes resource model (the "data model" for infrastructure-as-code). It captures the entities, their relationships, and the key configuration fields that govern system behaviour.

---

## Namespace Hierarchy

```
cluster
└── namespaces
    ├── estategap-system         # Infrastructure: NATS, PostgreSQL, Redis, MinIO, Observability
    ├── estategap-gateway        # API Gateway, WebSocket Server — external-facing
    ├── estategap-scraping       # Scrape Orchestrator, Spider Workers
    ├── estategap-pipeline       # Data Pipeline, Enrichment Workers
    ├── estategap-intelligence   # ML Scorer, ML Trainer, AI Search
    └── estategap-notifications  # Alert Engine, Notification Dispatcher
```

**Label schema** (applied to all namespaces):
```yaml
labels:
  app.kubernetes.io/managed-by: helm
  estategap.io/tier: <system|gateway|scraping|pipeline|intelligence|notifications>
```

---

## NATS JetStream Resources

```
StatefulSet: nats (3 replicas)
  └── PersistentVolumeClaim: nats-{0,1,2} — 10Gi each
  └── Service: nats-headless (ClusterIP None)
  └── Service: nats (ClusterIP, ports: 4222 client, 8222 monitor)
  └── ConfigMap: nats-config (nats.conf)

Job: nats-stream-setup (post-install)
  └── Uses: nats-box image
  └── Creates: 8 JetStream streams (idempotent)
  └── ServiceAccount: nats-setup-sa (RBAC: get/watch StatefulSet)
```

**JetStream stream fields**:
| Field | Description |
|-------|-------------|
| `name` | Unique stream identifier |
| `subjects` | Subject filter patterns (e.g., `listings.raw.>`) |
| `retention` | `limits` (size/age) or `workqueue` (consumer acks delete) |
| `maxAge` | Message TTL |
| `replicas` | Always 3 (matches NATS cluster size) |
| `storage` | `file` (disk-backed) |

---

## PostgreSQL (CloudNativePG) Resources

```
Cluster CR: estategap-postgres
  ├── Pod: estategap-postgres-1 (primary, ReadWrite)
  ├── Pod: estategap-postgres-2 (standby, ReadOnly)
  ├── PVC: estategap-postgres-1 — 200Gi
  ├── PVC: estategap-postgres-2 — 200Gi
  ├── Service: estategap-postgres-rw (primary, port 5432)
  ├── Service: estategap-postgres-r (any replica, port 5432)
  ├── Service: estategap-postgres-ro (read-only replicas, port 5432)
  └── Secret: estategap-postgres-superuser (managed by CNPG)

ScheduledBackup CR: estategap-postgres-daily
  └── Target: Cluster/estategap-postgres
  └── Schedule: "0 2 * * *"
  └── Destination: s3://backups/postgresql (MinIO)

Secret: postgresql-backup-credentials
  ├── ACCESS_KEY_ID (MinIO access key)
  └── SECRET_ACCESS_KEY (MinIO secret key)
```

**Key Cluster CR fields**:
| Field | Value | Notes |
|-------|-------|-------|
| `instances` | 2 | 1 primary + 1 standby |
| `storage.size` | 200Gi | Per-instance PVC |
| `postgresql.parameters.max_connections` | 200 | Tune per workload |
| `bootstrap.initdb.postInitSQL` | PostGIS extensions | Runs once on init |
| `backup.retentionPolicy` | 30d | Backup retention |

---

## Redis Resources

```
StatefulSet: redis-master (1 replica)
  └── PVC: redis-master-data — 8Gi
  └── Service: redis-master (port 6379)

StatefulSet: redis-replicas (1 replica)
  └── PVC: redis-replica-data — 8Gi
  └── Service: redis-replicas (port 6379)

StatefulSet: redis-sentinel (3 replicas, no PVC)
  └── Service: redis (port 26379 Sentinel, 6379 proxy)

Secret: redis-credentials
  └── redis-password
```

**Redis configuration matrix**:
| Parameter | Value | Reason |
|-----------|-------|--------|
| `maxmemory` | 1gb | As specified |
| `maxmemory-policy` | allkeys-lru | Evict LRU keys on full |
| `appendonly` | yes | AOF persistence |
| `appendfsync` | everysec | Balance between safety and performance |
| `save` | "" (disabled) | Use AOF only, not RDB snapshots |

---

## MinIO Resources

```
StatefulSet: minio (1 replica)
  └── PVC: minio-data — 50Gi
  └── Service: minio (ClusterIP, port 9000 API, 9001 Console)

Job: minio-bucket-setup (post-install)
  └── Creates buckets: ml-models, training-data, listing-photos, exports, backups
  └── ServiceAccount: minio-setup-sa

Secret: minio-credentials
  ├── root-user
  └── root-password
```

**Bucket access policy**:
| Bucket | Policy | Consumer |
|--------|--------|----------|
| ml-models | private | ml-scorer, ml-trainer |
| training-data | private | ml-trainer, pipeline |
| listing-photos | private (pre-signed URLs for frontend) | scraping spiders |
| exports | private | api-gateway (download) |
| backups | private | CloudNativePG barman |

---

## Observability Resources

```
Namespace: monitoring (kube-prometheus-stack default)
├── Prometheus (StatefulSet, 1 replica, 50Gi PVC)
├── Grafana (Deployment, 1 replica, 10Gi PVC)
│   └── Ingress: grafana.estategap.com
├── AlertManager (StatefulSet, 1 replica)
├── node-exporter (DaemonSet)
└── kube-state-metrics (Deployment)

Loki (StatefulSet, 1 replica, 20Gi PVC)
  └── Promtail (DaemonSet — all nodes)

Tempo (Deployment, 1 replica, 10Gi PVC)

ConfigMap: grafana-datasources (auto-provisioned)
  ├── Prometheus datasource
  ├── Loki datasource
  └── Tempo datasource

PodMonitor CRs (one per application namespace)
  └── Targets: pods with label app.kubernetes.io/scrape=true
```

---

## Networking Resources

```
NetworkPolicy: allow-gateway-egress (namespace: estategap-gateway)
  └── Allows egress to: all namespaces

NetworkPolicy: restrict-scraping-egress (namespace: estategap-scraping)
  └── Allows egress to: estategap-system only

NetworkPolicy: restrict-pipeline-egress (namespace: estategap-pipeline)
  └── Allows egress to: estategap-system only

NetworkPolicy: restrict-intelligence-egress (namespace: estategap-intelligence)
  └── Allows egress to: estategap-system only

NetworkPolicy: restrict-notifications-egress (namespace: estategap-notifications)
  └── Allows egress to: estategap-system, estategap-gateway

Certificate: estategap-tls (cert-manager)
  └── Domains: app.estategap.com, api.estategap.com, ws.estategap.com, grafana.estategap.com
  └── IssuerRef: letsencrypt-prod (ClusterIssuer)
```

---

## IngressRoute Resources (Traefik CRDs)

```
IngressRoute: estategap-http-routes
  ├── app.estategap.com → Service/frontend:3000
  ├── api.estategap.com → Service/api-gateway:8080
  └── ws.estategap.com → Service/websocket-server:8081 (WebSocket upgrade)

IngressRoute: grafana-route
  └── grafana.estategap.com → Service/grafana:80

Middleware: https-redirect (HTTP→HTTPS)
Middleware: rate-limit-api (100 req/s per IP on api.estategap.com)
```

---

## Sealed Secrets Schema

```
SealedSecret: estategap-app-secrets (namespace: estategap-system)
  Decrypts to Secret with keys:
  ├── POSTGRES_PASSWORD
  ├── POSTGRES_REPLICATION_PASSWORD
  ├── REDIS_PASSWORD
  ├── MINIO_ROOT_USER
  ├── MINIO_ROOT_PASSWORD
  ├── STRIPE_SECRET_KEY
  ├── STRIPE_WEBHOOK_SECRET
  ├── LLM_API_KEY_ANTHROPIC
  ├── LLM_API_KEY_OPENAI
  └── JWT_SECRET

SealedSecret: postgresql-backup-credentials (namespace: estategap-system)
  Decrypts to Secret with keys:
  ├── ACCESS_KEY_ID
  └── SECRET_ACCESS_KEY
```

---

## ConfigMap Schema

```
ConfigMap: estategap-config (namespace: estategap-system, mounted by all services)
  Keys:
  ├── DATABASE_HOST: estategap-postgres-rw.estategap-system.svc.cluster.local
  ├── DATABASE_RO_HOST: estategap-postgres-r.estategap-system.svc.cluster.local
  ├── DATABASE_PORT: "5432"
  ├── DATABASE_NAME: estategap
  ├── REDIS_HOST: redis.estategap-system.svc.cluster.local
  ├── REDIS_PORT: "6379"
  ├── REDIS_SENTINEL_HOST: redis.estategap-system.svc.cluster.local
  ├── REDIS_SENTINEL_PORT: "26379"
  ├── NATS_URL: nats://nats.estategap-system.svc.cluster.local:4222
  ├── MINIO_ENDPOINT: http://minio.estategap-system.svc.cluster.local:9000
  ├── MINIO_BUCKET_ML_MODELS: ml-models
  ├── MINIO_BUCKET_TRAINING_DATA: training-data
  ├── MINIO_BUCKET_LISTING_PHOTOS: listing-photos
  ├── MINIO_BUCKET_EXPORTS: exports
  └── MINIO_BUCKET_BACKUPS: backups
```

---

## HPA / KEDA ScaledObject Schema

```
HorizontalPodAutoscaler: api-gateway-hpa
  ├── scaleTargetRef: Deployment/api-gateway
  ├── minReplicas: 2, maxReplicas: 20
  └── metrics: CPU targetAverageUtilization: 60

HorizontalPodAutoscaler: ml-scorer-hpa
  ├── scaleTargetRef: Deployment/ml-scorer
  ├── minReplicas: 1, maxReplicas: 10
  └── metrics: CPU targetAverageUtilization: 70

HorizontalPodAutoscaler: ai-chat-hpa
  ├── scaleTargetRef: Deployment/ai-chat
  ├── minReplicas: 1, maxReplicas: 8
  └── metrics: CPU targetAverageUtilization: 60

ScaledObject: spider-workers-scaler (KEDA)
  ├── scaleTargetRef: Deployment/spider-workers
  ├── minReplicaCount: 1, maxReplicaCount: 50
  └── triggers:
      └── type: nats-jetstream
          stream: scraper-commands
          consumer: spider-worker-group
          lagThreshold: "100"
```

---

## ArgoCD Application CR

```
Application: estategap-staging (namespace: argocd)
  ├── source.repoURL: <repo-url>
  ├── source.targetRevision: main
  ├── source.path: helm/estategap
  ├── source.helm.valueFiles: [values-staging.yaml]
  ├── destination.server: https://kubernetes.default.svc
  ├── destination.namespace: estategap-system
  └── syncPolicy:
      ├── automated.prune: false
      └── automated.selfHeal: true
```
