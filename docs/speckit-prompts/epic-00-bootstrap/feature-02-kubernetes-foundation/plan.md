# Feature: Kubernetes Foundation

## /plan prompt

```
Implement the Kubernetes infrastructure with these technical decisions:

## Helm Chart Structure
helm/estategap/
├── Chart.yaml (apiVersion: v2, appVersion: 0.1.0)
├── values.yaml (defaults)
├── values-staging.yaml
├── values-production.yaml
└── templates/
    ├── _helpers.tpl
    ├── namespaces.yaml (6 namespaces)
    ├── configmap.yaml (shared config: DB host, Redis host, NATS URL, MinIO endpoint)
    ├── sealed-secrets.yaml (DB password, Redis password, Stripe keys, LLM API keys)
    ├── ingress.yaml (Traefik IngressRoute for: app.estategap.com → frontend, api.estategap.com → api-gateway, ws.estategap.com → ws-server)
    └── per-service templates

## Infrastructure Components
- NATS: Use nats Helm chart (nats-io/nats). StatefulSet, 3 replicas, JetStream enabled, 10Gi PVC per replica. Create streams via nats-box init container.
- PostgreSQL: CloudNativePG operator. Cluster CR with 1 primary + 1 replica. PostGIS enabled via custom initdb. Backup to MinIO via barman.
- Redis: Bitnami Redis Helm chart. Standalone mode + Sentinel. maxmemory 1gb, maxmemory-policy allkeys-lru.
- MinIO: MinIO operator or standalone deployment. 50Gi PVC. Create buckets via mc init container.
- Prometheus: kube-prometheus-stack Helm chart with custom scrape configs for application services.
- Loki: grafana/loki-stack Helm chart with Promtail DaemonSet.
- ArgoCD: Application CR pointing to helm/ directory, auto-sync for staging namespace.

## Resource Profiles (values.yaml)
Define per-service resource requests/limits as documented in architecture. HPA for api-gateway (CPU 60%), spider-workers (NATS queue depth), ml-scorer (CPU 70%), ai-chat (CPU 60%).

## Networking
- Traefik Ingress Controller (assumed pre-installed on cluster)
- cert-manager with Let's Encrypt ClusterIssuer for TLS
- Internal service communication via K8s ClusterIP services
- NetworkPolicies: gateway namespace can reach all; scraping/pipeline/intelligence namespaces can only reach system namespace (DB/NATS/Redis)
```
