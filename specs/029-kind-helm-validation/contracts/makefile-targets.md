# Contract: Makefile Targets (Kind Development Workflow)

**Feature**: 029-kind-helm-validation  
**Phase**: 1 — Contracts  
**Date**: 2026-04-17

---

## Overview

The kind development workflow is exposed as GNU Make targets. All targets are defined in `mk/kind.mk` and included by the root `Makefile`. This document is the contract for what each target must do, what inputs it accepts, and what exit codes it returns.

---

## Variables (Inputs)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLUSTER_NAME` | `estategap` | kind cluster name |
| `DOCKER_REGISTRY` | `localhost:5001` | Local registry for image push/pull |
| `TAG` | `dev` | Docker image tag for kind images |
| `SERVICE` | _(none)_ | Used by `kind-shell` and `kind-logs` to target a specific service |
| `NAMESPACE` | `estategap-system` | Default namespace for kubectl operations |

---

## Target Contracts

### `kind-up`

**Purpose**: Create the kind cluster and local registry, install nginx ingress, install local-path-provisioner.

**Inputs**: `tests/kind/cluster.yaml`  
**Outputs**: Cluster `estategap` exists and is reachable via `kubectl`  
**Exit code**: 0 on success, non-zero if cluster already exists or creation fails  
**Idempotent**: No — fails if cluster already exists (use `kind-reset` to force)

**Steps**:
1. Start local registry container on `localhost:5001` if not running
2. `kind create cluster --config tests/kind/cluster.yaml`
3. Connect local registry to kind network
4. Apply registry ConfigMap (`tests/kind/registry-configmap.yaml`)
5. Install nginx ingress controller: `kubectl apply -f <nginx-ingress-kind-manifest>`
6. Wait for ingress-nginx to be Ready

---

### `kind-down`

**Purpose**: Destroy the kind cluster and kill all port forwards.

**Inputs**: `.kind-pids` (if exists)  
**Outputs**: Cluster `estategap` deleted  
**Exit code**: 0 always (idempotent — no error if cluster doesn't exist)  
**Idempotent**: Yes

**Steps**:
1. Read PIDs from `.kind-pids`, kill each with `kill -9`
2. Remove `.kind-pids`
3. `kind delete cluster --name estategap`

---

### `kind-build`

**Purpose**: Build all service Docker images with tag `:dev`, using hash-based change detection to skip unchanged images.

**Inputs**: `docker-bake.hcl`, `services/*/Dockerfile`, `frontend/Dockerfile`, `.make-cache/*.digest`  
**Outputs**: Docker images tagged `localhost:5001/<service>:dev` in local Docker daemon  
**Exit code**: 0 on success, non-zero on build failure  
**Idempotent**: Yes — skips unchanged images

**Steps**:
1. For each service, compute `sha256sum` of `Dockerfile` + source directory
2. Compare to `.make-cache/<service>.digest`
3. If changed: `docker buildx bake <target> --load`, update digest file
4. If unchanged: skip

---

### `kind-load`

**Purpose**: Push built images to the local registry so kind nodes can pull them.

**Inputs**: Docker images in local daemon  
**Outputs**: Images available at `localhost:5001/<service>:dev`  
**Exit code**: 0 on success  
**Idempotent**: Yes — `docker push` is idempotent for same digest

**Steps**:
1. For each service image: `docker push localhost:5001/<service>:dev`
2. (Registry is accessible to kind nodes via containerd mirror config)

---

### `kind-deploy`

**Purpose**: Install or upgrade the Helm chart with `values-test.yaml`, then start port forwards.

**Inputs**: `helm/estategap/`, `helm/estategap/values.yaml`, `helm/estategap/values-test.yaml`  
**Outputs**: All Helm-managed resources deployed; port forwards active  
**Exit code**: 0 on success, non-zero on Helm failure  
**Idempotent**: Yes (`helm upgrade --install`)

**Steps**:
1. `helm dependency update helm/estategap`
2. `helm upgrade --install estategap helm/estategap -f helm/estategap/values.yaml -f helm/estategap/values-test.yaml --namespace estategap-system --create-namespace --wait --timeout 5m`
3. Start port forwards: `bash tests/kind/port-forward.sh`

---

### `kind-seed`

**Purpose**: Load fixture data into PostgreSQL, Redis, and MinIO.

**Inputs**: `tests/fixtures/` directory  
**Outputs**: DB rows, Redis keys, MinIO objects populated  
**Exit code**: 0 on success, non-zero if DB/Redis/MinIO unreachable  
**Idempotent**: Yes — uses `INSERT ... ON CONFLICT DO NOTHING` / `boto3.put_object`

**Steps**:
1. Wait for PostgreSQL ready
2. `uv run python tests/fixtures/load.py`

---

### `kind-test`

**Purpose**: Run the full E2E test suite against the deployed cluster.

**Inputs**: Running kind cluster with deployed chart  
**Outputs**: Test report  
**Exit code**: 0 if all tests pass, non-zero on failure

**Steps**:
1. `bash tests/helm/install-test.sh`

---

### `kind-logs`

**Purpose**: Tail logs from all pods (or a specific service if `SERVICE` is set).

**Inputs**: `SERVICE` (optional)  
**Behavior**:
- If `stern` is available: `stern -n estategap-system .` (or `stern -n estategap-system <SERVICE>`)
- Otherwise: `kubectl logs -f -n estategap-system -l app.kubernetes.io/name=<SERVICE>` (or all pods via label selector)

---

### `kind-shell`

**Purpose**: Open an interactive shell in a running service pod.

**Inputs**: `SERVICE=<name>` (required)  
**Exit code**: exits with shell exit code  

**Steps**:
1. `kubectl exec -it -n estategap-system deploy/<SERVICE> -- /bin/sh`

---

### `kind-reset`

**Purpose**: Full teardown and rebuild. Guaranteed clean state.

**Inputs**: None  
**Outputs**: Cluster running with fresh seed data  
**Exit code**: 0 on success  

**Sequence**: `kind-down` → `kind-up` → `kind-build` → `kind-load` → `kind-deploy` → `kind-seed`

---

### `helm-lint` (bonus target)

**Purpose**: Lint all four values profiles.

**Exit code**: 0 if all pass, non-zero on first failure

---

### `helm-test` (bonus target)

**Purpose**: Run helm-unittest suite.

**Steps**: `helm unittest helm/estategap`

---

### `helm-conformance` (bonus target)

**Purpose**: Run conformance.py against rendered templates.

**Steps**: `uv run python tests/helm/conformance.py`

---

### `helm-upgrade-test` (bonus target)

**Purpose**: Run upgrade/rollback test.

**Steps**: `bash tests/helm/upgrade-test.sh`
