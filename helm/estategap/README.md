# EstateGap Helm Chart

EstateGap packages the platform workloads, shared config, monitoring hooks, and GitOps resources for a Kubernetes cluster that already provides Kafka, PostgreSQL, Prometheus, Grafana, and cert-manager.

## Requirements

- Helm 3.14+
- Kubernetes 1.28+
- cert-manager with a working issuer
- Prometheus Operator 0.63+
- KEDA 2.x
- External Kafka, PostgreSQL, and S3-compatible object storage

## Quick Install

```bash
helm dependency update helm/estategap
helm install estategap helm/estategap   --namespace estategap-system --create-namespace -f helm/estategap/values.yaml -f values-override.yaml
```

Use [HELM_VALUES.md](./HELM_VALUES.md) for the full operator reference, including:

- [Quick Start](./HELM_VALUES.md#1-quick-start)
- [External Services](./HELM_VALUES.md#2-external-services)
- [Application Services](./HELM_VALUES.md#3-application-services)
- [Security](./HELM_VALUES.md#4-security)
- [Observability](./HELM_VALUES.md#5-observability)
- [Feature Flags](./HELM_VALUES.md#6-feature-flags)
- [Scaling Guide](./HELM_VALUES.md#7-scaling-guide)
- [Migration Guide](./HELM_VALUES.md#8-migration-guide-v2-to-v3)
- [Troubleshooting](./HELM_VALUES.md#9-troubleshooting)
