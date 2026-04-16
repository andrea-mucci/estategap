# Feature: Unit, Integration & Contract Tests

## /plan prompt

```
Implement with these technical decisions:

## Go Test Infrastructure
- Test file naming: `*_test.go` colocated with source
- Use `testify/assert` and `testify/require` (require for setup, assert for assertions)
- Table-driven tests with map[string]struct pattern:
  ```go
  tests := map[string]struct {
      input    string
      expected int
      wantErr  bool
  }{
      "valid": {input: "a", expected: 1, wantErr: false},
      ...
  }
  for name, tt := range tests {
      t.Run(name, func(t *testing.T) { ... })
  }
  ```
- Coverage: `go test -race -coverprofile=coverage.out -covermode=atomic ./...`
- golangci-lint config at `.golangci.yml` with enabled linters: errcheck, gofmt, gosec, govet, revive, staticcheck, unused, ineffassign, typecheck

## Python Test Infrastructure
- pytest config in each service's `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  asyncio_mode = "auto"
  addopts = "--strict-markers --cov-branch --cov-report=xml --cov-report=term-missing"
  markers = [
      "unit: Unit tests (fast, isolated)",
      "integration: Integration tests (require containers)",
      "slow: Slow tests"
  ]
  ```
- Test structure: `tests/unit/` (no external deps), `tests/integration/` (with testcontainers)
- Fixtures via `conftest.py` with session-scoped containers
- Use `respx` for HTTPX mocking, `pytest-mock` for general mocks

## Frontend Test Infrastructure
- Vitest config at `frontend/vitest.config.ts`
- Test setup file: `frontend/src/test/setup.ts` imports `@testing-library/jest-dom`
- MSW server setup in `frontend/src/test/msw.ts` with handlers auto-generated from OpenAPI spec
- Component test pattern:
  ```ts
  describe('ListingCard', () => {
    it('renders price with correct currency', () => {
      render(<ListingCard listing={mockListing} />)
      expect(screen.getByText('€450.000')).toBeInTheDocument()
    })
  })
  ```

## Coverage Configuration
- Go: `.codecov.yml` sets 80% threshold with `target: 80%` and `threshold: 2%` (allow 2% drop)
- Python: pytest.ini_options.addopts includes `--cov-fail-under=80`
- Frontend: vitest config `coverage.thresholds = { lines: 70, functions: 70, branches: 70 }`
- CI uploads coverage to Codecov. PR comments show diff.

## Testcontainers — Go
- Library: `github.com/testcontainers/testcontainers-go`
- Shared helpers in `libs/testhelpers/`:
  ```go
  func StartPostgres(t *testing.T) *pgxpool.Pool {
      ctx := context.Background()
      pgContainer, err := postgres.RunContainer(ctx,
          testcontainers.WithImage("postgis/postgis:16-3.4"),
          postgres.WithDatabase("estategap_test"),
          postgres.WithUsername("test"),
          postgres.WithPassword("test"),
      )
      require.NoError(t, err)
      t.Cleanup(func() { pgContainer.Terminate(ctx) })
      // Run migrations
      // Return pool
  }
  ```
- Similar helpers: StartRedis, StartNATS, StartMinIO

## Testcontainers — Python
- Library: `testcontainers` (Python)
- Fixtures in `libs/common/testing/fixtures.py`:
  ```python
  @pytest.fixture(scope="session")
  async def postgres_container():
      container = PostgresContainer("postgis/postgis:16-3.4")
      container.start()
      yield container
      container.stop()

  @pytest.fixture
  async def db_pool(postgres_container):
      pool = await asyncpg.create_pool(container.get_connection_url())
      # Run migrations
      yield pool
      await pool.close()
      # Truncate all tables
  ```

## Migration Tests
- File: `services/pipeline/tests/integration/test_migrations.py`
- Test cases:
  - `test_upgrade_from_scratch`: create empty DB → `alembic upgrade head` → verify all tables exist
  - `test_downgrade_each_migration`: upgrade to head → for each migration: downgrade → verify schema → upgrade again
  - `test_idempotency`: upgrade to head → upgrade again → verify no diff
  - `test_no_data_loss`: seed data → upgrade → verify data intact
- Use Alembic's programmatic API via `alembic.config.Config`

## gRPC Integration Tests
- Pattern: start server on `127.0.0.1:0` (random port), create client, test
- Go example:
  ```go
  func TestScoringService(t *testing.T) {
      lis, err := net.Listen("tcp", "127.0.0.1:0")
      server := grpc.NewServer()
      ml.RegisterMLScoringServiceServer(server, &scorerImpl{...})
      go server.Serve(lis)
      defer server.Stop()

      conn, _ := grpc.Dial(lis.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
      client := ml.NewMLScoringServiceClient(conn)
      resp, err := client.ScoreListing(ctx, &ml.ScoreListingRequest{...})
      require.NoError(t, err)
      assert.InDelta(t, expected, resp.EstimatedPrice, 1000)
  }
  ```
- Python equivalent using `grpc.aio` server
- Test streaming RPCs: verify multiple responses arrive, cancellation mid-stream works

## NATS Integration Tests
- Test pattern:
  ```go
  // Publish message
  nc.Publish("enriched.listings", msgJSON)
  // Wait for DB state change
  eventually(t, func() bool {
      row := db.QueryRow("SELECT deal_score FROM listings WHERE id = $1", id)
      return row.deal_score != nil
  }, 5*time.Second)
  ```
- Use NATS JetStream test helper from testhelpers
- Test redelivery: consumer returns error → verify retried up to max_deliver

## Pipeline Integration Test
- File: `tests/integration/test_pipeline_e2e.py`
- Flow:
  1. Start all pipeline services + dependencies via testcontainers
  2. Publish raw listing to `raw.listings.es`
  3. Poll DB every 500ms for up to 30s
  4. Assert: listing exists with deal_score, tier, model_version set
  5. Assert: SHAP features present for Tier 1-2 deals
- Repeat with batch of 100 listings, assert throughput

## Cross-Service Tests
- `tests/integration/cross_service/` directory
- Each test file covers one interaction path
- Uses docker-compose-like pattern: spin up multiple services + dependencies
- Assertions cover: response correctness, timing, observability (logs/metrics present)

## Protobuf Contract Tests
- Use `buf test` (if available) or custom Go test that:
  - Loads all .proto files
  - For each RPC: construct sample request, verify Marshal/Unmarshal round-trip
  - Verify wire format stability (binary comparison with frozen fixtures)
- `buf breaking` configuration in `buf.yaml`:
  ```yaml
  breaking:
    use:
      - FILE
  ```

## OpenAPI Contract Tests
- Generation step in Makefile:
  ```make
  frontend/src/lib/api-types.ts: services/api-gateway/openapi.yaml
      npx openapi-typescript $< -o $@
  ```
- Validation in E2E tests: wrap fetch with `openapi-backend` validator
- Contract fixtures at `tests/contracts/frontend/`:
  ```json
  {
    "GET /api/v1/listings/{id}": {
      "response": { "id": "...", "price": 450000, ... }
    }
  }
  ```

## CI Workflows
- `.github/workflows/ci-unit.yml`:
  ```yaml
  jobs:
    go:
      runs-on: ubuntu-latest
      strategy:
        matrix:
          service: [api-gateway, ws-server, alert-engine, ...]
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-go@v5
        - run: cd services/${{ matrix.service }} && go test -race -cover ./...
    python:
      strategy:
        matrix:
          service: [spider-workers, pipeline, ml, ai-chat]
      steps:
        - run: cd services/${{ matrix.service }} && uv run pytest
    frontend:
      steps:
        - run: cd frontend && pnpm test
  ```
- `.github/workflows/ci-integration.yml` uses `services:` for PostgreSQL/Redis or Docker-in-Docker for testcontainers

## Directory Structure
libs/testhelpers/          # Go shared test helpers
├── postgres.go
├── redis.go
├── nats.go
└── minio.go

libs/common/testing/       # Python shared test helpers
├── fixtures.py
├── factories.py
└── assertions.py

tests/
├── contracts/
│   ├── frontend/
│   └── api/
└── integration/
    ├── cross_service/
    └── test_pipeline_e2e.py
```
