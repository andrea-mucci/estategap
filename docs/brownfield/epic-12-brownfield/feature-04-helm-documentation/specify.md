# Feature: Comprehensive Helm Values Documentation

## /specify prompt

```
Create exhaustive documentation for all Helm chart values so that any operator can deploy EstateGap on their cluster without reading the source code. Documentation exists in two places: inline comments in values.yaml and a standalone HELM_VALUES.md reference document.

## What

1. **values.yaml inline documentation** — Every single value must have a YAML comment with:
   - One-line description of what it controls
   - Type (string, int, bool, object, list)
   - Whether it's required or optional
   - Default value explanation
   - Example value for non-obvious settings

2. **HELM_VALUES.md** — Standalone reference document at `helm/estategap/HELM_VALUES.md` with:

   **Section 1: Quick Start** — Minimum configuration to deploy on an existing cluster (copy-paste ready):
   - Required secrets to create beforehand
   - Minimal values-override.yaml with external service configs
   - `helm install` command

   **Section 2: External Services Reference** — For each external service (Kafka, PostgreSQL, S3, Prometheus, Grafana):
   - All configurable values with description, type, default, required flag
   - Authentication options (Secret reference, inline, SASL, TLS)
   - Connection verification commands (`kubectl exec ... -- kafka-topics.sh --list`)
   - Troubleshooting: common errors and fixes

   **Section 3: Application Services Reference** — For each EstateGap service:
   - Environment variables it reads (auto-generated from ConfigMap)
   - Resource requests/limits recommendations per scale tier (small/medium/large)
   - HPA configuration (min/max replicas, CPU/memory thresholds)
   - Health endpoints (liveness, readiness paths and ports)
   - Feature flags that affect this service

   **Section 4: Security Configuration** — Secrets management:
   - List of all required K8s Secrets with their expected keys
   - How to create each Secret (kubectl commands)
   - Sealed Secrets integration
   - TLS configuration for ingress
   - Network policies

   **Section 5: Observability Configuration** — Prometheus, Grafana, logging:
   - ServiceMonitor label selector (must match your Prometheus)
   - How to verify metrics are being scraped
   - Dashboard import verification
   - Alert rules reference with thresholds and descriptions
   - Log format and structured fields

   **Section 6: Feature Flags** — All toggleable components:
   - `components.*.deploy` flags with implications of each
   - Conditional template rendering explanation
   - Dependency matrix (which services need which infrastructure)

   **Section 7: Scaling Guide** — Recommendations per deployment size:
   - Small (< 10k listings, 1 country): resource profiles, replica counts
   - Medium (10k-100k listings, 5 countries): adjustments
   - Large (100k+ listings, 15+ countries): full HA configuration

   **Section 8: Migration Guide v2 → v3** — Step-by-step:
   - Pre-migration checklist (cluster prerequisites, secrets, buckets)
   - values.yaml diff between v2 and v3
   - Data migration steps (if any)
   - Rollback procedure

   **Section 9: Troubleshooting** — Common issues:
   - Pod CrashLoopBackOff: check logs, common causes per service
   - Database connection refused: credentials, network policies, SSL
   - Kafka consumer not receiving: topic existence, consumer group, SASL
   - S3 access denied: credentials, bucket policy, endpoint URL
   - Metrics not appearing: ServiceMonitor labels, namespace, port name

3. **values.schema.json** — JSON Schema for Helm values validation:
   - Every required field marked
   - Enum constraints for known values (sslmode, sasl.mechanism, etc.)
   - Pattern constraints for URLs, hostnames
   - Helm install auto-validates against schema

4. **README.md** in chart root — Short intro pointing to HELM_VALUES.md for details.

## Acceptance Criteria

- Every value in values.yaml has an inline comment with description, type, and default
- HELM_VALUES.md covers all 9 sections with real examples
- A new operator can deploy EstateGap from scratch following Quick Start (tested by someone unfamiliar with the project)
- values.schema.json validates all values profiles without errors
- `helm install` with missing required values produces a clear error message from schema validation
- Troubleshooting section covers the top 10 most common deployment errors
- All K8s Secret requirements documented with exact key names and creation commands
```
