# Quickstart: Local Kind Development Environment

**Feature**: 029-kind-helm-validation  
**Date**: 2026-04-17

---

## Prerequisites

Install the following tools before using the local dev environment:

| Tool | Version | Install |
|------|---------|---------|
| Docker | 24+ | https://docs.docker.com/engine/install/ |
| kind | 0.24+ | `brew install kind` or `go install sigs.k8s.io/kind@latest` |
| kubectl | 1.30+ | `brew install kubectl` |
| helm | 3.14+ | `brew install helm` |
| helm-unittest | latest | `helm plugin install https://github.com/helm-unittest/helm-unittest` |

**Minimum Docker resources**: 4 CPU, 8 GB RAM, 40 GB disk

---

## Full Reset (First Time or Clean Slate)

```bash
make kind-reset
```

This runs the full sequence: `kind-down` → `kind-up` → `kind-build` → `kind-load` → `kind-deploy` → `kind-seed`. Expect ~5 minutes (excluding first-time image build).

---

## Day-to-Day Workflow

### Start cluster

```bash
make kind-up
```

### Build and load images (after code changes)

```bash
make kind-build   # builds only changed images (hash-checked)
make kind-load    # loads only changed images into kind
```

### Deploy/upgrade Helm chart

```bash
make kind-deploy  # helm upgrade --install + starts port forwards
```

### Reload seed data

```bash
make kind-seed
```

### Watch logs

```bash
make kind-logs                    # all pods (requires stern)
make kind-logs SERVICE=api-gateway  # specific service
```

### Open a shell in a service pod

```bash
make kind-shell SERVICE=api-gateway
```

### Destroy cluster

```bash
make kind-down
```

---

## Port Mappings

After `make kind-deploy`:

| Endpoint | URL |
|----------|-----|
| API Gateway | http://localhost:8080 |
| WebSocket Server | ws://localhost:8081 |
| Frontend | http://localhost:3000 |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |
| PostgreSQL (debug) | localhost:5432 |

Health check: `curl localhost:8080/healthz`

---

## Helm Validation

```bash
# Lint all profiles
helm lint helm/estategap -f helm/estategap/values.yaml
helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-staging.yaml
helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-production.yaml
helm lint helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-test.yaml

# Or via make
make helm-lint

# Run helm-unittest suite
make helm-test

# Run conformance checks
make helm-conformance

# Template render check
make helm-template
```

---

## Test Mode Flags

`ESTATEGAP_TEST_MODE=true` is enabled by default in `values-test.yaml`. To freeze time:

```bash
# Set NOW_OVERRIDE in values-test.yaml:
# testMode:
#   nowOverride: "1745000000"   # Unix timestamp
make kind-deploy
```

---

## Running E2E Tests

```bash
make kind-test
```

Runs `tests/helm/install-test.sh` against the deployed cluster.

---

## Upgrade/Rollback Test

```bash
make helm-upgrade-test
```

Runs the full install v0.1.0 → seed → upgrade v0.2.0 → diff → rollback cycle.

---

## Troubleshooting

**Pods not starting**: `kubectl get pods -A` to see status; `kubectl describe pod <name> -n <ns>` for events.

**Port already in use**: Stop conflicting process before `make kind-up`. Ports needed: 80, 443, 3000, 3001, 5432, 8080, 8081, 9090.

**Image pull errors**: Run `make kind-load` to ensure images are loaded into the cluster.

**Seed data fails**: Check that PostgreSQL is ready (`kubectl wait --for=condition=ready pod -l cnpg.io/cluster=estategap-postgresql -n estategap-system --timeout=2m`).
