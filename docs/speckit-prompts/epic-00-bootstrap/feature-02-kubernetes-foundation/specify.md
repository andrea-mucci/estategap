# Feature: Kubernetes Foundation

## /specify prompt

```
Set up the complete Kubernetes infrastructure for the EstateGap platform.

## What
Deploy all required infrastructure services and create the Helm chart skeleton for the application:

1. NATS JetStream cluster (3 replicas) with 8 pre-configured streams: raw-listings, normalized-listings, enriched-listings, scored-listings, alerts-triggers, alerts-notifications, scraper-commands, price-changes
2. PostgreSQL 16 + PostGIS 3.4 (primary + 1 read replica) via CloudNativePG operator. 200Gi persistent storage. Daily backup CronJob to MinIO.
3. Redis 7 (single instance + Sentinel) with 1Gi memory limit and AOF persistence.
4. MinIO object storage with buckets: ml-models, training-data, listing-photos, exports, backups.
5. Observability stack: kube-prometheus-stack (Prometheus + Grafana + AlertManager), Loki + Promtail (logging), Tempo (tracing).
6. ArgoCD application manifest for GitOps deployment.
7. Helm chart skeleton for all application services with: namespaces (estategap-system, estategap-gateway, estategap-scraping, estategap-pipeline, estategap-intelligence, estategap-notifications), ConfigMaps, Sealed Secrets, Traefik IngressRoutes.

## Why
All infrastructure must be declared as code and deployable via Helm/ArgoCD to the existing Kubernetes cluster. Services need reliable messaging (NATS), persistent storage (PostgreSQL), caching (Redis), and object storage (MinIO).

## Acceptance Criteria
- `helm install` deploys all infrastructure successfully
- NATS: `nats stream ls` shows 8 streams. Pub/sub test succeeds.
- PostgreSQL: `psql` connects. PostGIS version 3.4+. Replication lag < 1s. Backup CronJob succeeds.
- Redis: `redis-cli ping` → PONG. Data survives pod restart.
- MinIO: 5 buckets created. Upload/download test works.
- Grafana: accessible via Ingress, shows K8s node metrics and logs.
- ArgoCD: auto-syncs staging changes from repo.
```
