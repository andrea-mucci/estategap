# Research: Test Coverage Infrastructure

**Feature**: 030-test-coverage-infrastructure  
**Date**: 2026-04-17  
**Phase**: 0 — Research

---

## 1. Current Test Infrastructure Audit

### Go Services

| Service | Has Tests | Has testify | Has testcontainers-go | Build Tag for Integration |
|---------|-----------|-------------|----------------------|--------------------------|
| libs/pkg | Yes | No | No | No |
| api-gateway | Yes | No | No | No |
| ws-server | Yes | No | Yes (ws_test.go) | No |
| alert-engine | Yes | No | Yes | `integration` |
| alert-dispatcher | Yes | No | Yes | `integration` |
| scrape-orchestrator | Yes | No | No | No |
| proxy-manager | Yes | No | No | No |

**Decision**: Add `testify/assert` + `testify/require` to all Go module `go.mod` files. `testcontainers-go` already present in 3 services — standardize by moving shared helpers to `libs/testhelpers/`.

**Decision**: Build tag `//go:build integration` already used by `alert-dispatcher` and `alert-engine`. Adopt this as the monorepo standard for integration tests across all Go services.

### Python Services

| Service | pytest-asyncio | pytest-cov | pytest-mock | testcontainers | respx |
|---------|---------------|-----------|------------|---------------|-------|
| pipeline | Yes | No | No | `[postgres]` only | No |
| ml | Yes | No | No | No | No |
| ai-chat | Yes | No | No | `[postgres,redis]` | No |
| spider-workers | Yes | No | No | No | No |
| libs/common | Yes | No | No | No | No |

**Decision**: Add `pytest-cov`, `pytest-mock`, `respx` to all Python service dev dependencies. Expand `testcontainers` extras to `[postgres,redis,nats,minio]` as needed per service.

**Decision**: No service has `pytest.ini_options` configured with markers or coverage settings. Add standardized block to each service's `pyproject.toml`.

### Frontend

| Capability | Status |
|-----------|--------|
| vitest | Configured (`vitest.config.ts`) |
| jsdom environment | Yes |
| @testing-library/jest-dom | Yes (setup.ts) |
| @testing-library/react | Yes |
| @testing-library/user-event | Yes |
| MSW | Missing — not in package.json |
| Coverage thresholds | Missing — not in vitest.config.ts |
| @vitest/coverage-v8 | Missing |

**Decision**: Add `msw@2.x` and `@vitest/coverage-v8` to frontend devDependencies. Update `vitest.config.ts` with coverage configuration and thresholds.

### CI Workflows

| Workflow | Runs Tests | Coverage Upload | Integration Tests |
|---------|-----------|----------------|------------------|
| ci-go.yml | Yes (no flags) | No | No |
| ci-python.yml | Yes (no cov) | No | No |
| ci-frontend.yml | No test step | No | No |
| ci-proto.yml | buf lint/gen | No | N/A |

**Decision**: Extend existing workflows rather than replacing. Add `test-coverage` job to `ci-go.yml` and `ci-python.yml`. Add test step to `ci-frontend.yml`. Create new `ci-integration.yml` for Docker-in-Docker integration tests.

---

## 2. `libs/testhelpers` Go Module Design

**Decision**: Create `libs/testhelpers/` as a new Go module (`github.com/estategap/testhelpers`) added to `go.work`. This avoids adding `testcontainers-go` as a production dependency to individual service `go.mod` files — it's test-only infra.

**Rationale**: testcontainers-go is a large dependency. Centralizing it in `libs/testhelpers` means each service's `go.mod` only needs one import for all container helpers, and upgrades are made in one place.

**Alternative considered**: Vendoring testcontainers in each service individually — rejected because it creates version drift and duplication.

---

## 3. Coverage Threshold Strategy

**Decision**:
- Go: enforce via `go-coverage-report` action or shell script comparing `go tool cover` output against 80% minimum per module. No single shared tool available — use `go test -coverprofile` + `awk`/`python3` to parse and fail below threshold in CI.
- Python: `--cov-fail-under=80` flag in `addopts` of `pytest.ini_options`.
- Frontend: `coverage.thresholds` in `vitest.config.ts` with `lines: 70, functions: 70, branches: 70, statements: 70`.

**Decision**: Codecov is the aggregator. `.codecov.yml` sets the overall project target with per-flag overrides for Go, Python, and frontend.

**Alternative considered**: Coveralls — rejected, Codecov has better GitHub PR comment UX and is industry standard.

---

## 4. `libs/common/testing` Python Package Design

**Decision**: Create `libs/common/testing/` as a sub-package of `estategap-common` (not a separate package). Add it to the existing `libs/common/pyproject.toml` under `[dependency-groups]` dev with the required testcontainers extras.

**Rationale**: Services already depend on `estategap-common` via editable path install. Adding the testing helpers to the same package avoids an extra path dependency declaration in each service's `pyproject.toml`.

---

## 5. Migration Test Design

**Decision**: The existing `services/pipeline/tests/integration/test_migrations.py` file path is correct. Use Alembic's programmatic API (`alembic.config.Config`, `alembic.command.upgrade`/`downgrade`) to run migrations against a testcontainer-provisioned PostgreSQL database. No subprocess calls needed.

**Decision**: Migration tests need PostGIS. Use `postgis/postgis:16-3.4` image (same as production). The `testcontainers[postgres]` module supports custom images.

---

## 6. gRPC Test Server Pattern

**Decision**: Go integration tests use `net.Listen("tcp", "127.0.0.1:0")` for random port assignment. Python uses `grpc.aio.server()` with `add_insecure_port("[::]:0")` which returns the bound port.

**Decision**: gRPC tests are `//go:build integration` tagged and run via `make test-integration`. They do not require testcontainers (server starts in-process) but may use them for database dependencies.

---

## 7. NATS Test Pattern

**Decision**: Use the existing NATS testcontainer pattern from `alert-dispatcher` as the reference. The `nats:2.10-alpine` image with `-js` flag enables JetStream. Standardize this in `libs/testhelpers/nats.go`.

**Decision**: Test assertion pattern uses a polling helper `EventuallyWithT` (available in testify v1.9+) or a custom `waitForCondition` in `libs/testhelpers/wait.go`.

---

## 8. Pipeline E2E Test Architecture

**Decision**: `tests/integration/test_pipeline_e2e.py` spins up all pipeline Python services (normalizer, deduplicator, enricher, scorer) as subprocesses within the test, sharing testcontainer instances. This is simpler than Docker Compose within a test.

**Alternative considered**: Docker Compose file — rejected because it adds complexity for what is essentially a pytest fixture. In-process subprocess management allows better signal handling and teardown.

---

## 9. OpenAPI Contract Enforcement

**Decision**: The frontend already uses `openapi-fetch` (typed client generated from OpenAPI spec) and the `generate-api-types` npm script. Extend this with MSW handlers that mirror the OpenAPI spec for test mocking.

**Decision**: Runtime response validation in E2E tests uses the existing OpenAPI spec directly — no additional validator library needed. MSW intercepts in tests enforce the contract at the client level; `buf breaking` enforces the gRPC contract at the schema level.

---

## 10. `buf breaking` CI Integration

**Decision**: `buf.yaml` already has `breaking.use: [FILE]` configured. The missing piece is running `buf breaking --against '.git#branch=main'` in `ci-proto.yml`. Add this step.

**Rationale**: FILE-level breaking change detection catches the most common issues (field removal, type changes, method removal) while allowing additive changes.
