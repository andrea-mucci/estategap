# Research: Kind Cluster & Helm Validation

**Feature**: 029-kind-helm-validation  
**Phase**: 0 — Research & Decision Log  
**Date**: 2026-04-17

---

## 1. Kind Version & Kubernetes Compatibility

**Decision**: kind 0.24+ with Kubernetes 1.30  
**Rationale**: kind 0.24 ships k8s 1.30 node images (`kindest/node:v1.30.x`). K8s 1.30 is the LTS-aligned release matching the target in spec. The control-plane `ingress-ready=true` label is required for Nginx/Traefik ingress controllers that use node selectors.  
**Alternatives considered**:
- K8s 1.29: Stable but older; no benefit for this use case.
- K8s 1.31: Not widely tested with all chart dependencies as of April 2026.

---

## 2. Local Image Registry Strategy

**Decision**: Use a local Docker registry sidecar on `localhost:5001` alongside kind, loaded into the cluster via registry ConfigMap (standard kind local registry pattern).  
**Rationale**: `kind load docker-image` works for single-worker clusters but becomes slow for 2+ workers (each requires a separate `docker exec` copy). A local registry (the official kind + local registry script) pushes once and is pulled by all nodes via the cluster's registry ConfigMap. This satisfies the `DOCKER_REGISTRY=localhost:5001` variable in the spec.  
**Alternatives considered**:
- `kind load docker-image --name estategap` for each image: Works but duplicates image data per node; too slow for 10+ images.
- Remote registry (ghcr.io): Requires auth and internet access; not suitable for offline dev.

---

## 3. Parallel Image Builds: docker buildx bake

**Decision**: `docker-bake.hcl` with BuildKit `--cache-from type=local,src=.buildx-cache` inline cache. Targets defined for all 10 services + frontend.  
**Rationale**: `docker buildx bake` parallelizes all builds in a single invocation. Local cache avoids redundant layer rebuilds across `make kind-build` runs. The `--cache-to type=local,dest=.buildx-cache,mode=max` pattern is well-established and avoids registry dependency.  
**Alternatives considered**:
- Plain `docker build` in a loop: Sequential; too slow for 11 images.
- BuildKit with registry cache (`--cache-from type=registry`): Requires a writable registry; overkill for local dev.

---

## 4. Image Change Detection

**Decision**: Hash `Dockerfile` + `services/<svc>/` (or `frontend/`) directory content using `sha256sum` (or `find ... | sha256sum`), store per-image digest in `.make-cache/<svc>.digest`. On `make kind-load`, compare current hash to cached; skip `kind load` if unchanged.  
**Rationale**: `kind load docker-image` copies the entire image tar to each node — slow for multi-GB Python images. Skipping unchanged images makes incremental rebuilds fast.  
**Alternatives considered**:
- Docker image ID comparison: Not stable across multi-stage builds when intermediate layers change.
- Always re-load: Correct but defeats the purpose of incremental workflow.

---

## 5. Makefile Structure

**Decision**: Root `Makefile` includes `mk/kind.mk` for all kind targets. Shared variables (`CLUSTER_NAME`, `DOCKER_REGISTRY`, `TAG`) defined at the top of `mk/kind.mk` and re-exported.  
**Rationale**: Separating kind targets into `mk/kind.mk` keeps the root Makefile focused on build/test/lint. The `include` directive is idiomatic for GNU Make. Existing Makefile already defines `REGISTRY`, `TAG`, `GO_SERVICES`, `PYTHON_SERVICES` — `mk/kind.mk` will import these.  
**Alternatives considered**:
- All targets in root Makefile: Works but clutters the file as the project grows.
- Separate `Makefile.kind`: Non-standard naming; `make -f Makefile.kind` is less ergonomic than `include`.

---

## 6. Helm values-test.yaml Profile

**Decision**: `values-test.yaml` overrides:
- All service `replicaCount: 1`
- All HPA `enabled: false`
- NATS: 1 replica, 1Gi storage
- PostgreSQL: 1 instance, 5Gi storage
- MinIO: 1Gi storage
- Observability: disabled (prometheus, loki, tempo all `enabled: false`)
- `global.testMode: true` — picked up by ConfigMap template
- All image tags: `dev` (from `make kind-build`)
- IngressClass: `nginx` (nginx ingress deployed separately via kind extraPortMappings)

**Rationale**: Minimal footprint for kind (3 nodes, ~12GB RAM total). Disabling observability saves ~4GB RAM. Single replicas are fine for local dev.  
**Alternatives considered**:
- Keep observability enabled: Useful for debugging but too resource-hungry for dev machines.
- Use hostPath PVCs: Simpler but `local-path-provisioner` (standard for kind) is more realistic to production.

---

## 7. values.schema.json Coverage

**Decision**: Hand-written JSON Schema (not generated from Go structs). Covers all top-level keys: `global`, `cluster`, `postgresql`, `redis`, `nats`, `minio`, `cnpg`, `keda`, `prometheus`, `loki`, `tempo`, `ingress`, `observability`, `mlScorer`, `mlTrainer`, `aiChat`, `alertEngine`, `alertDispatcher`, `spiderWorkers`, `pipeline`, `scrapingOrchestrator`, `proxyManager`, `frontend`, `apiGateway`, `wsServer`, `services`, `gdpr`, `loadTests`, `argocd`.  
**Rationale**: `go-jsonschema` requires Go struct definitions which don't exist for Helm values (they're YAML, not Go code). Hand-written schema is simpler and more maintainable for YAML-first configuration. Helm 3's built-in schema validation runs `values.schema.json` automatically on install/upgrade.  
**Alternatives considered**:
- `helm-schema` CLI tool: Generates schema from values.yaml automatically; less precise than hand-written (types inferred, not declared).
- Skip schema: Loses validation benefit on install; not acceptable given conformance requirements.

---

## 8. helm-unittest Test Coverage Strategy

**Decision**: 8 test files covering: `api-gateway_test.yaml`, `autoscaling_test.yaml`, `ingress_test.yaml`, `network-policies_test.yaml`, `secrets_test.yaml`, `postgres_test.yaml`, `nats_test.yaml`, `feature-flags_test.yaml`. Target ≥25 test cases total (exceeds 20 minimum).  
**Rationale**: Each file maps to a distinct template concern, making failures easy to locate. `helm-unittest` YAML syntax supports `set` overrides per test, enabling multi-profile testing without separate values files.  
**Alternatives considered**:
- Conftest (OPA): More powerful policy enforcement but higher learning curve; overkill for template structure validation.
- Terratest with Go: Runs full install/uninstall cycles; too slow for template-unit testing.

---

## 9. Conformance Test Implementation

**Decision**: Python script `tests/helm/conformance.py` using `pyyaml` to parse `helm template` output. Uses `sys.exit(1)` on any failure with a human-readable report. Run as `make helm-conformance`.  
**Rationale**: Python is already in the stack; `pyyaml` handles multi-document YAML streams (helm template output). The script can be run without cluster access (pure template analysis).  
**Alternatives considered**:
- `kubeconform`: Good for schema validation but doesn't check custom fields (labels, resource limits, security contexts).
- `polaris`: Cloud-native conformance tool but adds a dependency and is harder to customize.

---

## 10. Seed Data Strategy

**Decision**: `tests/fixtures/load.py` uses `asyncpg` (already in requirements for pipeline/ml services), `boto3` for MinIO uploads, and `redis-py` for Redis keys. Runs with `uv run` from repo root using a dedicated `pyproject.toml` in `tests/fixtures/`.  
**Rationale**: Consistent with existing Python tooling. `asyncpg` bulk copy is the fastest PostgreSQL insertion method. Connection details passed via environment variables matching the port-forwarded endpoints.  
**Alternatives considered**:
- `psycopg2` with CSV COPY: Slightly faster but requires file staging; `asyncpg.copy_records_to_table` is cleaner.
- Alembic seeds: Seeds are coupled to migrations; fixture data is environment-specific and should not be in migrations.

---

## 11. Test Mode Implementation Approach

**Decision**: `ESTATEGAP_TEST_MODE=true` injected via `values-test.yaml` into the shared ConfigMap at `helm/estategap/templates/configmap.yaml`. Each service already reads a shared ConfigMap for env vars; adding `ESTATEGAP_TEST_MODE` requires no service code changes — only the ConfigMap template needs the conditional.  
**Rationale**: Single injection point (ConfigMap) propagates to all services without per-service Deployment changes. Services must implement the conditional logic for their test doubles (FixtureSpider, FakeLLMProvider, etc.) as part of this feature.  
**Alternatives considered**:
- Per-service ConfigMap overrides: More granular but requires 10 separate changes.
- Kubernetes ConfigMap with `envFrom`: Already the pattern used; no change needed.

---

## 12. Port Forward Management

**Decision**: `tests/kind/port-forward.sh` starts `kubectl port-forward` in background with `&`, stores all PIDs in `.kind-pids` file, traps `SIGTERM`/`SIGINT` to kill them. `make kind-down` runs `tests/kind/cleanup.sh` which reads `.kind-pids` and kills all PIDs, then runs `kind delete cluster`.  
**Rationale**: Background port-forward processes are the standard kubectl pattern for local development. PID file avoids orphan processes across terminal sessions.  
**Alternatives considered**:
- `telepresence`: Full traffic interception; too heavy for this use case.
- `ktunnel`: Similar to port-forward but with keep-alive; adds dependency without significant benefit.

---

## 13. Upgrade/Rollback Test Design

**Decision**: `tests/helm/upgrade-test.sh` uses two local chart versions:
- v0.1.0: Current `helm/estategap/` (packaged as `dist/estategap-0.1.0.tgz`)
- v0.2.0: Same chart with `version: 0.2.0` in Chart.yaml (packaged as `dist/estategap-0.2.0.tgz`)
- Data verification: row count comparison (not full pg_dump diff) using `kubectl exec psql` queries

**Rationale**: Full `pg_dump` diff is fragile (sequence values change). Row count + spot queries for fixture data are sufficient to verify no data loss. Packaging locally avoids OCI registry dependency.  
**Alternatives considered**:
- Helm OCI registry: Requires pushing packages; adds complexity for a local test.
- Fake version bump via `--set chart.version`: Not how Helm versioning works; must modify Chart.yaml.

---

## Resolved Unknowns

| Unknown | Resolution |
|---------|------------|
| Which ingress controller for kind? | Nginx ingress (standard kind quickstart); Traefik kept for production via ingress.yaml |
| PVC provisioner for kind? | `local-path-provisioner` (rancher/local-path-provisioner) — standard for kind |
| Frontend port in kind? | 30003 NodePort → localhost:3000; added to cluster.yaml extraPortMappings |
| Frontend port mapping | Added containerPort: 30003 / hostPort: 3000 to cluster.yaml |
| helm-unittest install method | `helm plugin install` as part of `make kind-prereqs` |
