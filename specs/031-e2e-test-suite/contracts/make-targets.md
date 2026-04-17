# Contract: Makefile Targets for User Journey Tests

Targets to add to the root `Makefile`.

```makefile
##@ User Journey Tests (tests/usecase/)

.PHONY: test-usecase test-usecase-fast test-usecase-browser test-usecase-api

## test-usecase: Run all 15 user journey tests against kind cluster
test-usecase: kind-port-forward-bg
	cd tests/usecase && uv run pytest -v --tb=short -m usecase

## test-usecase-fast: Run journeys excluding slow (time-travel, K8s retrain)
test-usecase-fast: kind-port-forward-bg
	cd tests/usecase && uv run pytest -v --tb=short -m "usecase and not slow"

## test-usecase-browser: Run browser-based journeys only (requires Playwright)
test-usecase-browser: kind-port-forward-bg
	cd tests/usecase && uv run pytest -v --tb=short -m "usecase and browser"

## test-usecase-api: Run API-only journeys (no Playwright required)
test-usecase-api: kind-port-forward-bg
	cd tests/usecase && uv run pytest -v --tb=short -m "usecase and api"
```

## CI Trigger Rules

| Event | Target | Trigger Condition |
|-------|--------|-------------------|
| Nightly (staging) | `test-usecase` | Cron: 02:00 UTC daily |
| PR merge | `test-usecase-fast` | Files changed: `services/**`, `helm/**`, `tests/usecase/**` |
| Release RC | `test-usecase` + `test-usecase-browser` | Tag: `rc-*` |

## Environment Variables Required

```bash
GATEWAY_URL=http://localhost:8080
FRONTEND_URL=http://localhost:3000
NATS_URL=nats://localhost:4222
REDIS_URL=redis://localhost:6379
GATEWAY_DB_DSN=postgresql://estategap:estategap@localhost:5432/estategap
PLAYWRIGHT_HEADLESS=true  # set false for local debugging
STRIPE_TEST_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```
