# Quickstart: E2E Test Suite (031-e2e-test-suite)

**Branch**: `031-e2e-test-suite` | **Date**: 2026-04-17

---

## Prerequisites

Ensure these tools are installed and the cluster is running:

```bash
make kind-prereqs        # validates kind, kubectl, helm, docker buildx
kind get clusters        # should show "estategap"
kubectl get pods -A      # all pods should be Running/Completed
```

If the cluster is not running:

```bash
make kind-reset          # full teardown + rebuild + seed (~10 min)
# or incrementally:
make kind-up kind-build kind-load kind-deploy kind-seed
```

---

## Python API + WebSocket Tests

### Setup (one-time)

```bash
cd tests/e2e
uv sync                   # install pytest, httpx, websockets, nats-py, pytest-asyncio, pytest-xdist
```

### Run API tests

```bash
# Single-threaded (for debugging):
cd tests/e2e/api && uv run pytest -v

# Parallel (CI mode, 4 workers):
cd tests/e2e/api && uv run pytest -v -n 4 --junitxml=../../../reports/e2e/api.xml

# Single test file:
cd tests/e2e/api && uv run pytest test_auth.py -v

# Single test:
cd tests/e2e/api && uv run pytest test_rate_limiting.py::test_free_tier_rate_limit -v
```

### Run WebSocket tests

```bash
cd tests/e2e/websocket && uv run pytest -v --junitxml=../../../reports/e2e/ws.xml
```

### Run concurrency tests

```bash
cd tests/e2e/concurrency && uv run pytest -v --junitxml=../../../reports/e2e/concurrency.xml
```

### Run all Python E2E tests

```bash
make kind-test-api        # API + rate limiting
make kind-test-ws         # WebSocket + concurrency
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8080` | API Gateway URL |
| `WS_BASE_URL` | `ws://localhost:8081` | WebSocket server URL |
| `TEST_RUN_ID` | auto-generated UUID | Prefix for test resources (set by conftest) |

---

## Playwright Browser Tests

### Setup (one-time)

```bash
cd frontend
pnpm install                          # installs @playwright/test, axe-playwright
pnpm playwright install chromium firefox webkit   # install browser binaries
```

### Run all browser tests (Chromium only, fast)

```bash
cd frontend
pnpm playwright test --project=chromium
```

### Run full suite (all 3 browsers)

```bash
cd frontend
pnpm playwright test
```

### Run a single spec

```bash
cd frontend
pnpm playwright test specs/auth.spec.ts --project=chromium
```

### Run with UI (interactive debugging)

```bash
cd frontend
pnpm playwright test --ui
```

### Run visual regression tests

```bash
# First run — generate baselines (do this once, then commit):
cd frontend
pnpm playwright test visual/ --update-snapshots

# Subsequent runs — compare against baselines:
cd frontend
pnpm playwright test visual/
```

### Run accessibility tests only

```bash
cd frontend
pnpm playwright test --grep "@a11y"
```

### View HTML report

```bash
cd frontend
pnpm playwright show-report
```

---

## Full E2E Suite via Makefile

```bash
# Full suite (API + WS + browser) against the live cluster:
make kind-test

# Individual sub-suites:
make kind-test-api
make kind-test-ws
make kind-test-browser
make kind-test-visual
make kind-test-a11y
```

---

## Artifact Collection on Failure

When any `make kind-test-*` target fails, `tests/e2e/collect-artifacts.sh` is automatically invoked and outputs to `reports/e2e/artifacts/`:

```bash
# Manual invocation for debugging:
bash tests/e2e/collect-artifacts.sh reports/e2e/artifacts/

# Contents:
reports/e2e/artifacts/
├── logs/           # kubectl logs per pod
├── describe/       # kubectl describe for failed pods
├── db/dump.sql     # PostgreSQL snapshot
├── nats/           # NATS stream state
└── playwright/     # screenshots, videos, traces (Playwright-managed)
```

---

## Test Data Reference

Seeded users (password for all: `secret`):

| Email | Tier | Countries |
|-------|------|-----------|
| `free@test.estategap.com` | free | ES |
| `basic@test.estategap.com` | basic | ES, PT |
| `pro@test.estategap.com` | pro | ES, IT, PT |
| `global@test.estategap.com` | global | ES, IT, FR, PT, GB |
| `api@test.estategap.com` | api | ES, IT, FR, PT, GB |

Admin user: created separately; see `tests/fixtures/users.json`.

Seeded listings: `tests/fixtures/listings/{es,fr,gb,it,pt}.json`  
Seeded zones: `tests/fixtures/zones/{es,fr,gb,it,pt}.json`

---

## Sharding for CI

The suite supports 4-way sharding via pytest-xdist and Playwright's `--shard` option:

```yaml
# GitHub Actions matrix example:
strategy:
  matrix:
    shard: [1, 2, 3, 4]
steps:
  - run: |
      # Python tests (pytest-xdist auto-distributes within one runner)
      uv run pytest tests/e2e/api/ -n auto --dist=loadscope

  - run: |
      # Playwright browser tests
      pnpm playwright test --shard=${{ matrix.shard }}/4
```

---

## Common Issues

**Port-forward not running**: Run `bash tests/kind/port-forward.sh` to restart. Check `.kind-pids` for stale PIDs.

**Login fails in test setup**: The cluster may not be fully seeded. Run `make kind-seed` and retry.

**Visual regression failures on first run**: Baselines don't exist yet. Run `pnpm playwright test visual/ --update-snapshots` once, then commit the PNG files in `frontend/tests/e2e/visual/baselines/`.

**NATS injection fails**: Check that NATS port-forward on `localhost:4222` is active. Inspect `tests/kind/port-forward.sh` logs in `/tmp/estategap-port-forward-*.log`.

**`WS_IDLE_TIMEOUT_SECS` not applied**: Verify `helm/estategap/values-test.yaml` has `wsServer.env.WS_IDLE_TIMEOUT_SECS: "30"` and that `make kind-deploy` was run after the change.
