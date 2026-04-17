# EstateGap Runbook

## Architecture Overview

```mermaid
flowchart LR
  FE[Next.js Frontend] --> API[API Gateway]
  API --> PG[(PostgreSQL)]
  API --> REDIS[(Redis)]
  API --> NATS[(NATS JetStream)]
  API --> WS[WebSocket Server]
  NATS --> PIPE[Pipeline]
  NATS --> ALERTS[Alert Engine]
  ALERTS --> DISPATCH[Alert Dispatcher]
  PIPE --> ML[ML Scorer]
  ML --> MINIO[(MinIO)]
  PROM[Prometheus] --> GRAFANA[Grafana]
  API --> PROM
  PIPE --> PROM
  ALERTS --> PROM
```

## Service Dependency Map And Startup Order

1. Kubernetes foundation: ingress, cert-manager, metrics-server, sealed-secrets controller, KEDA.
2. Data plane: PostgreSQL, Redis, NATS, MinIO.
3. Observability: Prometheus, Loki, Tempo, Grafana.
4. Core platform: API Gateway, WebSocket Server, scrape-orchestrator, spider-workers, pipeline, ML services.
5. Notification services: alert-engine and alert-dispatcher.
6. Validate readiness in that order before opening traffic.

## Incident Playbooks

### Scraper Blocked

1. Inspect `spider-workers` and `scrape-orchestrator` logs for 403, 429, CAPTCHA, or proxy failures.
2. Rotate proxy credentials or reduce portal concurrency.
3. Pause the failing portal until the backoff window expires.
4. Confirm `listings.raw.*` traffic resumes and freshness recovers.

### Model Degraded

1. Compare the active MinIO artefact with the last known good model version.
2. Restore the previous ONNX artefact into the active path.
3. Restart `ml-scorer` so it reloads the model.
4. Re-run a smoke inference before restoring normal traffic.

### DB Full

1. Inspect the largest relations with:
   `SELECT relname, pg_total_relation_size(relid) FROM pg_catalog.pg_statio_user_tables ORDER BY 2 DESC LIMIT 20;`
2. Offload or archive cold data with `pg_dump`.
3. Resize the PostgreSQL PVC if needed.
4. Review retention for alerts, logs, and exports after the incident.

### NATS Lag

1. Check consumer lag with `nats consumer report --server nats://nats.estategap-system.svc.cluster.local:4222`.
2. Restart or scale the stalled worker group.
3. Replay from the required stream cursor only after validating idempotency.
4. Avoid purging the stream during recovery.

### High Error Rate

1. Inspect Grafana Tempo traces and identify the first failing service.
2. Check the API Gateway, pipeline, and alert dashboards for latency spikes.
3. Roll back the latest release if the issue correlates with a deployment.
4. Scale only after confirming the fault is capacity-related.

### HPA Not Scaling

1. Check the HPA or ScaledObject status and verify metrics-server health.
2. Confirm the relevant Prometheus or KEDA metric still updates.
3. Apply a manual scale override if needed:
   `kubectl scale deployment api-gateway -n estategap-gateway --replicas=6`
4. Fix the missing metric or threshold after the incident.

## Scaling Procedures

### Manual HPA Override

1. Disable the HPA temporarily or raise `minReplicas`.
2. Scale the target deployment with `kubectl scale`.
3. Re-enable autoscaling after the incident and reconcile the baseline values.

### Node Addition

1. Add worker nodes through the cluster provider.
2. Confirm the nodes are `Ready` and correctly labelled.
3. Rebalance pinned workloads and validate PVC attachment capacity.

## Backup And Restore

### PostgreSQL

```bash
pg_dump "postgresql://app:${PGPASSWORD}@estategap-postgres-rw.estategap-system.svc.cluster.local:5432/estategap" \
  --format=custom \
  --file=/backups/estategap.dump

pg_restore --clean --if-exists \
  --dbname="postgresql://app:${PGPASSWORD}@estategap-postgres-rw.estategap-system.svc.cluster.local:5432/estategap" \
  /backups/estategap.dump
```

### MinIO

```bash
mc alias set estategap http://minio.estategap-system.svc.cluster.local:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"
mc mirror estategap/ml-models /backups/minio/ml-models
mc mirror /backups/minio/ml-models estategap/ml-models
```

### NATS

```bash
nats stream report --server nats://nats.estategap-system.svc.cluster.local:4222
nats stream backup raw-listings /backups/nats/raw-listings --server nats://nats.estategap-system.svc.cluster.local:4222
nats stream restore raw-listings /backups/nats/raw-listings --server nats://nats.estategap-system.svc.cluster.local:4222
```

## Disaster Recovery

1. Recreate the cluster foundation and shared controllers.
2. Refresh Helm dependencies for `helm/estategap`.
3. Reapply SealedSecrets and shared ConfigMaps.
4. Restore PostgreSQL from the latest verified backup.
5. Restore MinIO buckets for models and exports.
6. Restore NATS streams if message durability is required.
7. Deploy services in startup order and verify readiness.
8. Run smoke checks for auth, search, alerts, chat, and exports before reopening traffic.

## Escalation Contacts

| Role | Method | Owner |
|------|--------|-------|
| Incident Commander | PagerDuty / phone bridge | Fill in during onboarding |
| Platform Engineer | Slack `#platform-oncall` | Fill in during onboarding |
| Database Owner | Slack `#data-platform` | Fill in during onboarding |
| Security Lead | Slack `#security` | Fill in during onboarding |
| Product Stakeholder | Email / phone | Fill in during onboarding |

