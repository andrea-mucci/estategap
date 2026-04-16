# Feature: Kind Environment & Helm Chart Validation

## /specify prompt

```
Set up the local Kubernetes development environment using kind and build comprehensive Helm chart validation tests.

## What

1. **Kind cluster configuration** at `tests/kind/cluster.yaml`:
   - Kubernetes version 1.30+
   - 3 nodes: 1 control-plane + 2 workers
   - Port mappings: 80, 443, 8080, 8081, 3000, 3001, 9090
   - Local-path-provisioner for PVCs
   - Extra mounts for fixture data

2. **Makefile targets** at repository root:
   - `make kind-up` — creates cluster from config
   - `make kind-down` — destroys cluster
   - `make kind-build` — builds all service Docker images with `:dev` tag
   - `make kind-load` — loads images into kind (incremental: only changed images)
   - `make kind-deploy` — installs Helm chart with `values-test.yaml`
   - `make kind-seed` — runs fixture loader to populate DB, Redis, MinIO
   - `make kind-test` — runs E2E test suite against deployed cluster
   - `make kind-logs` — tails logs from all pods (stern or kubectl)
   - `make kind-shell SERVICE=<name>` — opens shell in a service pod
   - `make kind-reset` — full teardown + rebuild + redeploy + seed
   - Cluster provisioning (kind-up through kind-seed) must complete in under 5 minutes

3. **Seed data fixtures** at `tests/fixtures/`:
   - `users.json` — 5 test users (one per subscription tier: free, basic, pro, global, api)
   - `listings/` — 1,000 synthetic listings across ES, IT, FR, PT, GB (realistic data)
   - `zones/` — zone polygons for major cities in each country (Madrid, Barcelona, Rome, Milan, Paris, Lisbon, London)
   - `ml-models/` — minimal pre-trained ONNX models per country for testing
   - `alerts.json` — 10 active alert rules
   - `conversations/` — sample AI chat conversations
   - `html-samples/<portal>/` — captured HTML fixtures for spider tests

4. **Test mode flag** (`ESTATEGAP_TEST_MODE=true`) that:
   - Disables real scraping (uses fixture data via a test spider)
   - Mocks Stripe webhooks (fake endpoint returns success)
   - Uses `FakeLLMProvider` with deterministic responses
   - Accelerates cron schedules (scraping every 30s, model retrain disabled)
   - Allows `NOW_OVERRIDE` env var to fix the current time

5. **Helm chart validation:**
   - `helm lint` passes with zero errors/warnings on all values profiles
   - `helm template` renders successfully for: `values.yaml`, `values-staging.yaml`, `values-production.yaml`, `values-test.yaml`
   - `values.schema.json` at chart root validates every top-level value (type, description, defaults)
   - helm-unittest suite at `helm/estategap/tests/` testing template logic (conditionals, feature toggles, env var substitution)

6. **Installation test on kind:**
   - After `helm install`: all Deployments reach ReadyReplicas within 3 minutes
   - No CrashLoopBackOff or ImagePullBackOff
   - All `/readyz` endpoints respond within 60s
   - Liveness probes don't cause restarts in first 10 minutes

7. **Upgrade/rollback tests:**
   - Install v0.1.0 → upgrade to v0.2.0 → verify no data loss → rollback → verify state restored
   - Must succeed without downtime (rolling update)

8. **Chart conformance tests:**
   - All resources have: namespace, standard K8s labels, resource requests + limits, securityContext, liveness + readiness probes
   - No `:latest` image tags
   - NetworkPolicies enforce namespace isolation
   - All secrets deployed as SealedSecrets (no plain-text credentials)

9. **Port forwarding** automatic on deploy:
   - localhost:8080 → api-gateway
   - localhost:8081 → ws-server
   - localhost:3000 → frontend
   - localhost:3001 → Grafana
   - localhost:9090 → Prometheus
   - localhost:5432 → PostgreSQL (read-only for debugging)

## Why

Every developer must be able to run the full platform locally in under 5 minutes to develop and debug without touching staging or production. The Helm chart is the deployment contract — if it's broken, nothing ships.

## Acceptance Criteria

- `make kind-reset` completes successfully on a clean machine (with Docker installed)
- From `make kind-up` to all pods Running: < 5 minutes (excluding first-time image build)
- `helm lint` returns 0 errors on all values profiles
- `helm template` renders valid YAML for all values profiles
- helm-unittest suite has at least 20 test cases covering template logic
- Installation test on kind passes: all pods Ready within 3 minutes
- Upgrade from v0.1.0 to v0.2.0 and rollback both succeed
- All chart conformance checks pass
- Seed data loads correctly: queries return expected fixture data
- Port forwarding works: `curl localhost:8080/healthz` returns 200 after `make kind-deploy`
```
