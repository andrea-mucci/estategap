# Feature: Comprehensive Helm Values Documentation

## /plan prompt

```
Implement the documentation with these technical decisions:

## values.yaml Comment Convention

Every value follows this pattern:

```yaml
# -- Description of what this value controls.
# Type: string | int | bool | object | list
# Required: yes | no
# Default: "value" (or: none — must be provided)
# Example: "kafka-bootstrap.kafka.svc.cluster.local:9092"
kafka:
  brokers: "kafka-bootstrap.kafka.svc.cluster.local:9092"
```

For nested objects:
```yaml
# -- PostgreSQL external connection configuration.
# Only used when components.postgresql.deploy is false.
postgresql:
  external:
    # -- PostgreSQL server hostname or ClusterIP service address.
    # Type: string | Required: yes
    # Example: "postgresql.databases.svc.cluster.local"
    host: ""
    
    # -- PostgreSQL server port.
    # Type: int | Required: no | Default: 5432
    port: 5432
```

## HELM_VALUES.md Structure

```markdown
# EstateGap Helm Chart — Values Reference

## Table of Contents
1. [Quick Start](#quick-start)
2. [External Services](#external-services)
   - [Kafka](#kafka)
   - [PostgreSQL](#postgresql)
   - [S3 Object Storage](#s3-object-storage)
   - [Prometheus](#prometheus)
   - [Grafana](#grafana)
3. [Application Services](#application-services)
4. [Security](#security)
5. [Observability](#observability)
6. [Feature Flags](#feature-flags)
7. [Scaling Guide](#scaling-guide)
8. [Migration Guide (v2 → v3)](#migration-guide)
9. [Troubleshooting](#troubleshooting)
```

## Quick Start Section Content

```markdown
## Quick Start

### Prerequisites
- Kubernetes 1.28+
- Helm 3.14+
- Existing cluster services: Kafka, PostgreSQL (with PostGIS), Prometheus, Grafana
- Hetzner S3 account with buckets created

### 1. Create Required Secrets

\```bash
# Database credentials
kubectl create secret generic estategap-db-credentials \
  --namespace estategap-system \
  --from-literal=PGUSER=estategap \
  --from-literal=PGPASSWORD='<your-password>'

# S3 credentials
kubectl create secret generic estategap-s3-credentials \
  --namespace estategap-system \
  --from-literal=AWS_ACCESS_KEY_ID='<your-key>' \
  --from-literal=AWS_SECRET_ACCESS_KEY='<your-secret>'

# Kafka credentials (if SASL enabled)
kubectl create secret generic estategap-kafka-credentials \
  --namespace estategap-system \
  --from-literal=KAFKA_SASL_USERNAME=estategap \
  --from-literal=KAFKA_SASL_PASSWORD='<your-password>'
\```

### 2. Create values-override.yaml

\```yaml
postgresql:
  external:
    host: "postgresql.databases.svc.cluster.local"
    database: "estategap"
    credentialsSecret: "estategap-db-credentials"

kafka:
  brokers: "kafka-bootstrap.kafka.svc.cluster.local:9092"

s3:
  endpoint: "https://fsn1.your-objectstorage.com"
  region: "fsn1"
  credentialsSecret: "estategap-s3-credentials"

prometheus:
  serviceMonitor:
    labels:
      release: "prometheus"    # ← Must match YOUR Prometheus operator selector
\```

### 3. Install

\```bash
helm install estategap ./helm/estategap -f values-override.yaml
\```
```

## Required Secrets Reference Table

| Secret Name | Namespace | Required Keys | Used By |
|---|---|---|---|
| `estategap-db-credentials` | estategap-system | `PGUSER`, `PGPASSWORD` | All services, migrations Job |
| `estategap-s3-credentials` | estategap-system | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | ml-trainer, ml-scorer, api-gateway, pipeline |
| `estategap-kafka-credentials` | estategap-system | `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD` | All services (only if kafka.sasl.enabled) |
| `estategap-stripe-credentials` | estategap-gateway | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | api-gateway |
| `estategap-jwt-secret` | estategap-gateway | `JWT_SECRET` | api-gateway, ws-server |
| `estategap-llm-credentials` | estategap-intelligence | `LLM_API_KEY` | ai-chat |

## Scaling Guide Profiles

| Profile | Listings | Countries | api-gateway | spider-workers | ml-scorer | pipeline | Redis |
|---|---|---|---|---|---|---|---|
| Small | < 10k | 1-2 | 1 replica, 256Mi | 1 replica, 512Mi | 1 replica, 512Mi | 1 replica, 512Mi | 256Mi |
| Medium | 10k-100k | 3-5 | 2 replicas, 512Mi | 3 replicas, 1Gi | 2 replicas, 1Gi | 2 replicas, 1Gi | 1Gi |
| Large | 100k+ | 10+ | 3+ replicas, 1Gi, HPA | 5+ replicas, 2Gi, HPA | 3+ replicas, 2Gi, HPA | 3+ replicas, 2Gi | 2Gi |

## values.schema.json

Generate using `helm-schema-gen` plugin or write manually. Key validations:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["kafka", "postgresql", "s3"],
  "properties": {
    "kafka": {
      "type": "object",
      "required": ["brokers"],
      "properties": {
        "brokers": {
          "type": "string",
          "description": "Kafka bootstrap server address",
          "pattern": "^[a-z0-9.-]+(:[0-9]+)?(,[a-z0-9.-]+(:[0-9]+)?)*$"
        },
        "topicPrefix": {
          "type": "string",
          "default": "estategap.",
          "pattern": "^[a-z0-9.-]+$"
        },
        "sasl": {
          "type": "object",
          "properties": {
            "mechanism": {
              "type": "string",
              "enum": ["PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"]
            }
          }
        }
      }
    },
    "postgresql": {
      "type": "object",
      "properties": {
        "external": {
          "type": "object",
          "required": ["host", "database", "credentialsSecret"],
          "properties": {
            "sslmode": {
              "type": "string",
              "enum": ["disable", "require", "verify-ca", "verify-full"],
              "default": "require"
            }
          }
        }
      }
    }
  }
}
```

## Troubleshooting Section — Top 10

1. **Pod CrashLoopBackOff** → `kubectl logs <pod> --previous` → check DB/Kafka/S3 connectivity
2. **Database connection refused** → verify credentialsSecret exists, check NetworkPolicy, test with psql from debug pod
3. **Kafka consumer not receiving** → verify topic exists (`kafka-topics.sh --list`), check consumer group, verify SASL if enabled
4. **S3 AccessDenied** → verify credentials in Secret, check bucket exists, verify endpoint URL and forcePathStyle
5. **Metrics not in Prometheus** → verify ServiceMonitor labels match Prometheus selector, check target namespace
6. **Dashboards not in Grafana** → verify ConfigMap labels, check Grafana sidecar namespace config
7. **Migration Job failed** → `kubectl logs job/estategap-migrations-*`, check DB permissions, verify PostGIS extension
8. **Helm install timeout** → increase `--timeout`, check migration Job, check image pull
9. **HPA not scaling** → verify metrics-server installed, check CPU/memory targets, verify resource requests set
10. **WebSocket 502** → check Ingress timeout annotations, verify ws-server running, check JWT secret consistency

## File List
- `helm/estategap/values.yaml` — fully commented
- `helm/estategap/values.schema.json` — JSON Schema
- `helm/estategap/HELM_VALUES.md` — comprehensive reference
- `helm/estategap/README.md` — short intro
```
