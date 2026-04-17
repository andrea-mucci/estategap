# Feature Specification: Test Coverage Infrastructure

**Feature Branch**: `030-test-coverage-infrastructure`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Set up the testing frameworks and test coverage infrastructure for all services in the monorepo: Go, Python, and TypeScript frontend. Include integration tests with testcontainers and contract tests for service boundaries."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run All Unit Tests with a Single Command (Priority: P1)

A developer working on any service in the monorepo wants to run all unit tests across Go, Python, and TypeScript with a single command and see a unified pass/fail result with coverage percentages.

**Why this priority**: Unit tests are the foundation of all testing. Without a fast, reliable unit test suite, developers cannot iterate confidently. This is the prerequisite for all other testing layers.

**Independent Test**: Can be fully tested by running `make test-unit` from the repository root and verifying that tests execute across all three language ecosystems, returning coverage reports and a clear pass/fail status.

**Acceptance Scenarios**:

1. **Given** a developer at the repository root, **When** they run `make test-unit`, **Then** unit tests execute for all Go services, all Python services, and the frontend, completing in under 3 minutes with per-service coverage reports.
2. **Given** a developer introduces a failing test in any service, **When** they run `make test-unit`, **Then** the command exits with a non-zero status and clearly identifies the failing test location.
3. **Given** a service with coverage below the configured threshold, **When** the test command runs, **Then** it reports the coverage shortfall and exits with a non-zero status.

---

### User Story 2 - Integration Tests with Real Dependencies (Priority: P1)

A developer modifying a service that interacts with PostgreSQL, Redis, NATS, or MinIO wants to verify that the service works correctly with real instances of these dependencies, not mocks.

**Why this priority**: Integration tests catch the most dangerous class of bugs -- those that only appear when real infrastructure is involved. Without them, database query bugs, message serialization issues, and connection handling errors slip through to production.

**Independent Test**: Can be tested by running `make test-integration` and verifying that testcontainers spin up real PostgreSQL, Redis, NATS, and MinIO instances, execute tests against them, and tear them down cleanly.

**Acceptance Scenarios**:

1. **Given** a Go service with database interactions, **When** integration tests run, **Then** a real PostgreSQL 16 + PostGIS container starts, the service connects and executes queries, and results are verified against expected data.
2. **Given** a Python service that consumes NATS messages, **When** integration tests run, **Then** a real NATS server with JetStream starts, test messages are published, and the consumer processes them with verifiable side effects.
3. **Given** integration tests running in parallel across services, **When** each test suite starts, **Then** each gets its own isolated container instances, preventing cross-contamination between test suites.
4. **Given** integration tests complete (pass or fail), **When** cleanup runs, **Then** all containers are removed and no orphaned containers remain.

---

### User Story 3 - CI Coverage Enforcement (Priority: P1)

A team lead wants the CI pipeline to automatically reject pull requests that reduce test coverage below configured thresholds, ensuring coverage never regresses.

**Why this priority**: Coverage thresholds without enforcement are aspirational, not protective. CI enforcement is what actually prevents coverage regression across the team.

**Independent Test**: Can be tested by submitting a PR with a change that drops coverage below the threshold and verifying that CI fails with a clear message about the coverage shortfall.

**Acceptance Scenarios**:

1. **Given** a Go service with 82% coverage, **When** a PR removes tests dropping coverage to 78%, **Then** CI fails and reports that coverage (78%) is below the 80% threshold.
2. **Given** a Python service at exactly 80% coverage, **When** a PR adds new code with full test coverage, **Then** CI passes and Codecov comments on the PR showing the coverage diff.
3. **Given** the frontend at 72% coverage, **When** a PR adds untested components dropping coverage to 68%, **Then** CI fails citing the 70% threshold.

---

### User Story 4 - Database Migration Verification (Priority: P2)

A developer adding or modifying an Alembic migration wants automated verification that the migration applies cleanly, rolls back cleanly, and does not lose data.

**Why this priority**: Migration failures are among the most disruptive production incidents. Catching them in tests prevents downtime and data loss.

**Independent Test**: Can be tested by running the migration test suite against an empty database and verifying that all migrations apply in sequence, each rolls back individually, and re-running from head produces no schema diff.

**Acceptance Scenarios**:

1. **Given** an empty PostgreSQL database, **When** all Alembic migrations run in sequence, **Then** every migration applies successfully and the final schema matches expectations.
2. **Given** a database at the latest migration, **When** each migration is rolled back one at a time, **Then** each downgrade succeeds without errors.
3. **Given** a database with fixture data at the latest migration, **When** a new migration is applied and rolled back, **Then** the fixture data remains intact.

---

### User Story 5 - gRPC Contract Verification (Priority: P2)

A developer modifying a Protobuf service definition wants immediate feedback if their change breaks backward compatibility with existing clients.

**Why this priority**: In a polyglot architecture with multiple gRPC services, breaking a Protobuf contract silently can cause cascading failures across services that are difficult to diagnose.

**Independent Test**: Can be tested by modifying a proto file in a breaking way (e.g., removing a field or changing a type) and verifying that `buf breaking` detects the change and CI blocks the PR.

**Acceptance Scenarios**:

1. **Given** a Protobuf service definition, **When** a developer removes a field from a message, **Then** `buf breaking` detects the breaking change and CI fails with a clear explanation.
2. **Given** a gRPC service (ai-chat, ml-scorer, proxy-manager), **When** integration tests run, **Then** a real gRPC server starts in-process, a client connects via generated stubs, and requests/responses are verified against the Protobuf definitions.
3. **Given** a streaming RPC (bidirectional chat, batch scoring), **When** integration tests run, **Then** messages stream correctly in both directions and error conditions (cancellation, deadlines, invalid arguments) are handled gracefully.

---

### User Story 6 - Cross-Service Integration Verification (Priority: P2)

A developer modifying a service boundary (e.g., how the API gateway calls the ML scorer) wants to verify that the interaction works end-to-end before merging.

**Why this priority**: Cross-service integration tests are the only way to catch incompatibilities between services that individually pass their own tests.

**Independent Test**: Can be tested by running cross-service integration tests that exercise key interaction paths (API gateway to ML scorer, alert engine to alert dispatcher, etc.) with real service instances.

**Acceptance Scenarios**:

1. **Given** the API gateway and ML scorer services, **When** a cross-service integration test runs, **Then** the gateway sends a gRPC valuation request and receives a valid scored response.
2. **Given** the alert engine and alert dispatcher, **When** a matching listing triggers an alert rule, **Then** the alert engine publishes to NATS and the dispatcher processes and routes the notification.
3. **Given** the scrape orchestrator and spider workers, **When** a scrape job is scheduled via NATS, **Then** a worker picks up the job and processes it.

---

### User Story 7 - OpenAPI Contract Enforcement (Priority: P3)

A frontend developer wants assurance that the API responses they consume match the documented OpenAPI spec, and that any backend changes that break the contract are caught before merge.

**Why this priority**: OpenAPI contracts bridge the frontend-backend boundary. When the API drifts from its spec, the frontend breaks in subtle ways that are hard to trace.

**Independent Test**: Can be tested by running API response validation tests that compare actual responses against the OpenAPI schema, and by verifying that frontend TypeScript types are generated from the spec.

**Acceptance Scenarios**:

1. **Given** an API endpoint with a documented OpenAPI schema, **When** an E2E test calls the endpoint, **Then** the response is validated against the schema and any deviation fails the test.
2. **Given** the OpenAPI spec changes, **When** TypeScript types are regenerated, **Then** the frontend compiles without errors if the change is additive, or compilation fails if the change removes required fields.
3. **Given** consumer-driven contract fixtures in `tests/contracts/frontend/`, **When** the API runs in test mode, **Then** it returns deterministic responses matching the fixtures.

---

### User Story 8 - Data Pipeline End-to-End Verification (Priority: P3)

A developer modifying a pipeline component (normalizer, deduplicator, enricher, or scorer) wants to verify that a listing flows correctly through the entire pipeline from raw input to scored database record.

**Why this priority**: The data pipeline is the core value-creation path. End-to-end testing ensures that changes to one stage do not break downstream processing.

**Independent Test**: Can be tested by injecting a raw listing JSON into the pipeline entry point and verifying the final database state includes correctly normalized, deduplicated, enriched, and scored data.

**Acceptance Scenarios**:

1. **Given** a raw listing JSON, **When** it is injected into the pipeline, **Then** it flows through normalization, deduplication, enrichment, and scoring, and the final database record contains all expected fields within 30 seconds.
2. **Given** a batch of 100 listings, **When** injected into the pipeline, **Then** all 100 are processed correctly with no data loss or corruption.
3. **Given** a pipeline component fails mid-processing, **When** the component restarts, **Then** the unprocessed message is redelivered and processing completes without data loss.

---

### Edge Cases

- What happens when a testcontainer fails to start (e.g., Docker not available)? Tests should skip gracefully with a clear message rather than failing with cryptic errors.
- What happens when coverage thresholds differ per service? The system must support per-service configuration overrides.
- What happens when a migration test discovers a migration without a down-migration? The test should fail and identify the specific migration.
- What happens when parallel integration tests compete for the same port? Each test must use dynamically assigned ports.
- What happens when a NATS consumer test times out waiting for message processing? The test should fail with a descriptive timeout message including the expected vs. actual state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `make test-unit` command that runs all unit tests across Go, Python, and TypeScript services from the repository root.
- **FR-002**: System MUST provide a `make test-integration` command that runs all integration tests, including testcontainer-based tests, from the repository root.
- **FR-003**: System MUST generate per-service coverage reports in both terminal-readable and machine-parseable (XML/JSON) formats.
- **FR-004**: System MUST enforce coverage thresholds: 80% statement coverage for Go services, 80% statement + branch coverage for Python services, 70% statement coverage for the frontend.
- **FR-005**: System MUST support per-service coverage threshold overrides for services that require stricter or more lenient thresholds.
- **FR-006**: System MUST provide shared test helper libraries for Go (`libs/testhelpers/`) and Python (`libs/common/testing/`) that encapsulate testcontainer setup for PostgreSQL 16 + PostGIS, Redis 7, NATS with JetStream, and MinIO.
- **FR-007**: System MUST run integration tests with fresh container instances per test suite to ensure parallel safety and isolation.
- **FR-008**: System MUST verify that all Alembic migrations apply and rollback successfully on an empty database.
- **FR-009**: System MUST verify that migrations do not cause data loss when applied to a database containing fixture data.
- **FR-010**: System MUST run `buf breaking` on every PR to detect backward-incompatible Protobuf changes.
- **FR-011**: System MUST provide gRPC integration tests for each gRPC service that start a real in-process server, connect a real client, and verify request/response schemas.
- **FR-012**: System MUST provide NATS integration tests for each consumer that publish test messages, wait for processing, and verify side effects.
- **FR-013**: System MUST provide cross-service integration tests for key interaction paths (API gateway to ML scorer, alert engine to dispatcher, scrape orchestrator to spider workers).
- **FR-014**: System MUST validate API responses against the OpenAPI schema in E2E tests.
- **FR-015**: System MUST provide a data pipeline end-to-end test that traces a listing from raw JSON through all pipeline stages to final database state.
- **FR-016**: System MUST integrate with Codecov to post coverage diffs as PR comments.
- **FR-017**: System MUST use Mock Service Worker (MSW) for frontend API mocking in component tests.
- **FR-018**: System MUST ensure all test commands exit with non-zero status on any test failure or coverage threshold violation.

### Key Entities

- **Test Suite**: A collection of tests for a specific service, categorized as unit, integration, or contract. Each suite has a language runtime, coverage threshold, and execution time budget.
- **Coverage Report**: A per-service metric showing statement coverage (and branch coverage for Python), produced in terminal and XML formats, compared against configurable thresholds.
- **Test Container**: An ephemeral infrastructure instance (database, cache, message broker, object store) provisioned per test suite via the testcontainers library, automatically cleaned up after tests complete.
- **Contract**: A formal agreement between two services about message format and behavior, enforced via Protobuf breaking change detection (gRPC services) or OpenAPI schema validation (REST API to frontend).
- **Migration Test**: A verification that a database migration applies cleanly, rolls back cleanly, is idempotent, and preserves existing data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All unit tests across all services execute in under 3 minutes from a single command.
- **SC-002**: All integration tests across all services execute in under 10 minutes from a single command.
- **SC-003**: Go and Python services maintain at least 80% test coverage; frontend maintains at least 70%.
- **SC-004**: Any pull request that reduces coverage below the configured threshold is automatically rejected by CI.
- **SC-005**: Every database migration has a corresponding rollback, and all migrations pass automated apply/rollback/idempotency tests.
- **SC-006**: Every Protobuf service definition change is checked for backward compatibility; breaking changes are blocked unless explicitly versioned.
- **SC-007**: Every service with external dependencies has at least one integration test that exercises the happy path with real infrastructure.
- **SC-008**: A single listing processed through the data pipeline end-to-end test completes in under 30 seconds.
- **SC-009**: Coverage reports are posted as PR comments on every pull request, showing per-service coverage diffs.
- **SC-010**: All cross-service interaction paths have dedicated integration tests verifying end-to-end communication.

## Assumptions

- Docker is available in all development and CI environments (required for testcontainers).
- The CI environment has sufficient resources to run multiple containers simultaneously (PostgreSQL, Redis, NATS, MinIO) during integration tests.
- Existing unit tests across all services are passing and will not need modification to work with the new test infrastructure (though they will be incorporated into the unified commands).
- The `buf` CLI is already installed and configured in CI (the existing `ci-proto.yml` workflow uses it).
- Codecov is available as a CI integration and a repository token will be configured as a CI secret.
- The existing Makefile structure will be extended rather than replaced.
- Frontend tests use `vitest` (already configured) and do not require migration to a different test runner.
- Test helper libraries will be new additions under `libs/testhelpers/` (Go) and `libs/common/testing/` (Python); no existing code at these paths needs to be preserved.
