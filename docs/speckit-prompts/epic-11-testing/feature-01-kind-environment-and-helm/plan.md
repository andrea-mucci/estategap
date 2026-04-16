# Feature: Kind Environment & Helm Chart Validation

## /plan prompt

```
Implement with these technical decisions:

## Kind Cluster
- kind version 0.24+ (K8s 1.30)
- Config file `tests/kind/cluster.yaml`:
  ```yaml
  kind: Cluster
  apiVersion: kind.x-k8s.io/v1alpha4
  name: estategap
  nodes:
    - role: control-plane
      kubeadmConfigPatches:
        - |
          kind: InitConfiguration
          nodeRegistration:
            kubeletExtraArgs:
              node-labels: "ingress-ready=true"
      extraPortMappings:
        - containerPort: 80
          hostPort: 80
        - containerPort: 443
          hostPort: 443
        - containerPort: 30080  # api-gateway NodePort
          hostPort: 8080
        - containerPort: 30081  # ws-server NodePort
          hostPort: 8081
        - containerPort: 30090  # Prometheus
          hostPort: 9090
        - containerPort: 30300  # Grafana
          hostPort: 3001
    - role: worker
    - role: worker
  ```

## Makefile Structure
- Root `Makefile` includes `mk/kind.mk` for kind-related targets
- Shared variables: CLUSTER_NAME=estategap, DOCKER_REGISTRY=localhost:5001
- Parallel image builds via `docker buildx bake` with `docker-bake.hcl` defining all service images
- Image loading via `kind load docker-image <image> --name estategap`
- Image change detection: compare Dockerfile + service source dir hashes with cached digests in `.make-cache/`

## Helm Chart Structure
- `helm/estategap/Chart.yaml` (apiVersion: v2, version: 0.1.0, appVersion: 0.1.0)
- `helm/estategap/values.yaml` — defaults
- `helm/estategap/values-test.yaml` — local kind testing (test mode enabled, minimal replicas, no autoscaling)
- `helm/estategap/values-staging.yaml` — staging environment
- `helm/estategap/values-production.yaml` — production (HA, autoscaling, monitoring)
- `helm/estategap/values.schema.json` — JSON Schema for values validation
- Templates organized by service in `helm/estategap/templates/<service>/{deployment,service,hpa,configmap,networkpolicy}.yaml`

## values.schema.json
- Generated from Go structs using `go-jsonschema` or hand-written
- Covers all top-level keys: global, postgresql, redis, nats, minio, apiGateway, wsServer, scrapingOrchestrator, spiderWorkers, pipeline, mlScorer, mlTrainer, aiChat, alertEngine, alertDispatcher, proxyManager, frontend, ingress, observability
- Each leaf value has: type, description, default, optional enum/pattern/minimum/maximum
- `helm install` automatically validates against schema (built-in feature since Helm 3)

## helm-unittest Suite
- Install helm-unittest plugin: `helm plugin install https://github.com/helm-unittest/helm-unittest`
- Tests at `helm/estategap/tests/` as YAML files
- Test scenarios:
  - `api-gateway_test.yaml` — deployment renders with correct image, replicas, env vars for each values profile
  - `autoscaling_test.yaml` — HPA resources created only when enabled; thresholds from values
  - `ingress_test.yaml` — Traefik IngressRoute paths correct for each host
  - `network-policies_test.yaml` — cross-namespace egress rules match architecture
  - `secrets_test.yaml` — SealedSecret references match expected keys
  - `postgres_test.yaml` — CloudNativePG Cluster spec correct
  - `nats_test.yaml` — StatefulSet + JetStream config
  - `feature-flags_test.yaml` — optional components (MLflow, frontend) conditionally rendered

## Installation Test
- Bash script `tests/helm/install-test.sh`:
  ```bash
  helm install estategap ./helm/estategap -f ./helm/estategap/values-test.yaml
  kubectl wait --for=condition=available deployment --all -n estategap-gateway --timeout=3m
  kubectl wait --for=condition=available deployment --all -n estategap-scraping --timeout=3m
  # ... repeat for all namespaces
  # Verify readiness
  for svc in api-gateway ws-server ai-chat; do
    kubectl port-forward svc/$svc 8080:8080 &
    curl -f http://localhost:8080/readyz
  done
  ```
- Exit 0 on success, capture logs on failure

## Upgrade/Rollback Test
- Bash script `tests/helm/upgrade-test.sh`:
  ```bash
  # Install v0.1.0
  helm install estategap ./helm/estategap --version 0.1.0 -f values-test.yaml
  # Seed data
  ./tests/fixtures/load.sh
  # Snapshot DB state
  kubectl exec postgres-primary-0 -- pg_dump estategap > /tmp/before.sql
  # Upgrade
  helm upgrade estategap ./helm/estategap --version 0.2.0 -f values-test.yaml
  kubectl wait ... --timeout=5m
  # Verify no data loss
  kubectl exec postgres-primary-0 -- pg_dump estategap > /tmp/after.sql
  diff /tmp/before.sql /tmp/after.sql  # should be identical
  # Rollback
  helm rollback estategap 1
  kubectl wait ...
  # Verify service still works
  curl http://localhost:8080/healthz
  ```

## Conformance Tests
- Python script `tests/helm/conformance.py`:
  - Parse `helm template ...` output with pyyaml
  - For each resource, assert:
    - `metadata.namespace` in expected list
    - `metadata.labels` contains: app.kubernetes.io/name, app.kubernetes.io/instance, app.kubernetes.io/component, app.kubernetes.io/part-of
    - For Deployments/StatefulSets: all containers have resources.requests + resources.limits, securityContext.runAsNonRoot=true, livenessProbe + readinessProbe defined
    - Image references don't use `:latest`
  - Exit non-zero on any failure

## Seed Data Loader
- Python script `tests/fixtures/load.py`:
  - Reads JSON fixtures from `tests/fixtures/`
  - Connects to PostgreSQL (via port-forward)
  - Bulk inserts users, zones, listings, alerts
  - Uploads ML model artifacts to MinIO
  - Sets Redis keys for active conversations
  - Runs in < 30s for 1k listings

## Port Forwarding
- Managed by a background script `tests/kind/port-forward.sh` that:
  - Starts kubectl port-forward for each service
  - Writes PIDs to `.kind-pids` file
  - `kind-down` kills all PIDs

## Test Mode Implementation
- Environment variable `ESTATEGAP_TEST_MODE=true` set in values-test.yaml via ConfigMap
- Each service reads it in config module
- Conditional behavior in services:
  - spider-workers: use `FixtureSpider` that reads from MinIO fixture bucket
  - api-gateway: Stripe webhook endpoint accepts test signatures
  - ai-chat: selects FakeLLMProvider
  - scrape-orchestrator: uses `TEST_SCHEDULE_OVERRIDE=*/30 * * * * *` (every 30s)
  - All services: accept `NOW_OVERRIDE` env var as Unix timestamp (frozen time)

## Image Build Optimization
- `docker-bake.hcl` defines all service images as targets
- BuildKit with inline cache (`--cache-from type=registry`)
- Local registry on kind for image distribution (faster than kind load for multi-worker)
- Parallel builds: `docker buildx bake --parallel`

## Directory Structure
tests/
├── kind/
│   ├── cluster.yaml
│   ├── port-forward.sh
│   └── cleanup.sh
├── fixtures/
│   ├── load.py
│   ├── users.json
│   ├── listings/
│   ├── zones/
│   ├── ml-models/
│   ├── alerts.json
│   └── html-samples/
├── helm/
│   ├── install-test.sh
│   ├── upgrade-test.sh
│   ├── conformance.py
│   └── schema-test.sh
helm/estategap/
├── Chart.yaml
├── values.yaml
├── values-test.yaml
├── values-staging.yaml
├── values-production.yaml
├── values.schema.json
├── templates/
└── tests/
    ├── api-gateway_test.yaml
    ├── autoscaling_test.yaml
    ├── ingress_test.yaml
    └── ...
```
