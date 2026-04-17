# Feature Specification: OpenAPI Documentation, gRPC Client Connections, and Alert Rules

**Feature Branch**: `009-openapi-grpc-alerts`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Add OpenAPI documentation and gRPC client connections to the API Gateway."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Interactive API Documentation (Priority: P1)

A developer integrating with the EstateGap API opens a browser, navigates to `/api/docs`, and sees a full interactive Swagger UI listing every endpoint. They click "Authorize", enter their JWT token, then use "Try it out" to call `GET /api/v1/listings` and see a real response—without leaving the browser.

**Why this priority**: Reduces integration friction for frontend developers and third-party API consumers. Without accurate, runnable documentation, every endpoint requires trial-and-error against a live environment.

**Independent Test**: Deploy the API Gateway, navigate to `/api/docs` in a browser, authorize with a valid JWT, and successfully execute at least one authenticated endpoint from the UI.

**Acceptance Scenarios**:

1. **Given** the API Gateway is running, **When** a browser requests `GET /api/docs`, **Then** the Swagger UI page loads with all documented endpoints visible and grouped.
2. **Given** the Swagger UI is open, **When** a user clicks "Authorize" and enters a valid JWT, **Then** subsequent "Try it out" calls include the `Authorization: Bearer <token>` header and return real responses.
3. **Given** the Swagger UI is open, **When** a user requests `GET /api/openapi.json`, **Then** the raw OpenAPI 3.1 specification is returned as parseable JSON.
4. **Given** an endpoint has documented request/response schemas, **When** a user clicks "Try it out" and submits the example body, **Then** the form is pre-populated with example values.

---

### User Story 2 - On-Demand Property Valuation (Priority: P1)

A subscribed user requests an instant valuation for a specific listing. The API Gateway forwards the request to the ML scorer service via gRPC, waits up to 5 seconds for a response, and returns the estimated value with a confidence score. If the ML scorer is unavailable, the user receives a clear error rather than an indefinitely hung request.

**Why this priority**: ML-powered valuation is a core paid feature differentiator. Users on Pro and above tiers expect reliable, fast estimates.

**Independent Test**: Call `GET /api/v1/model/estimate?listing_id=<id>` with a valid JWT. Verify the response includes an estimated value. Then bring the ml-scorer service down and verify a 503 response is returned within 5 seconds.

**Acceptance Scenarios**:

1. **Given** a valid JWT and an existing listing ID, **When** the user calls `GET /api/v1/model/estimate?listing_id=<id>`, **Then** the response includes `estimated_value`, `currency`, `confidence`, and `shap_values` within 5 seconds.
2. **Given** the ml-scorer service is unreachable, **When** a user requests an estimate, **Then** the API returns `503 Service Unavailable` within 5 seconds with a user-readable error message.
3. **Given** the ml-scorer service has failed 5 consecutive times, **When** a subsequent estimate request arrives, **Then** the system immediately returns `503` without attempting to contact the ml-scorer (circuit breaker is open).
4. **Given** the circuit breaker is open and 30 seconds have elapsed, **When** the next estimate request arrives, **Then** the system allows one probe attempt to the ml-scorer and recovers to normal operation if successful.

---

### User Story 3 - Alert Rules Management with Tier Limits (Priority: P1)

A Pro-tier subscriber navigates to alert settings and creates a new price-drop alert for apartments in Berlin under €500,000 with at least 3 bedrooms. The system saves the rule. A free-tier user attempts the same action and receives a clear message explaining their tier does not include alert rules.

**Why this priority**: Alert rules are a monetisation boundary—tier enforcement is a business-critical constraint. Without it, free users bypass subscription paywalls.

**Independent Test**: Create alert rules as a Pro user up to the tier limit; attempt one more and verify rejection. Attempt creation as a free user and verify immediate rejection.

**Acceptance Scenarios**:

1. **Given** a Pro-tier user has fewer than their tier's maximum active rules, **When** they call `POST /api/v1/alerts/rules` with a valid rule body, **Then** the rule is saved and returned with a 201 status.
2. **Given** a free-tier user, **When** they call `POST /api/v1/alerts/rules`, **Then** the system returns `403 Forbidden` with a message indicating their tier does not allow alert rules.
3. **Given** a Basic-tier user already has 3 active rules, **When** they attempt to create a 4th, **Then** the system returns `422 Unprocessable Entity` with a message stating the tier limit has been reached.
4. **Given** a valid alert rule ID belonging to the authenticated user, **When** they call `DELETE /api/v1/alerts/rules/{id}`, **Then** the rule is soft-deleted and no longer counted against their active limit.
5. **Given** a rule body with a zone ID that does not exist or is inactive, **When** the user calls `POST /api/v1/alerts/rules`, **Then** the system returns `422` identifying the invalid zone.
6. **Given** a rule body with a filter field not permitted for the specified property category, **When** the user calls `POST /api/v1/alerts/rules`, **Then** the system returns `422` identifying the disallowed field.

---

### User Story 4 - Alert Delivery History (Priority: P2)

A subscribed user wants to review which listings triggered their alerts last week and whether the notifications were successfully delivered. They call `GET /api/v1/alerts/history` and see a paginated list of past alert firings with delivery status (delivered, failed, pending).

**Why this priority**: Delivery history is a support and debugging tool. Users report missed notifications; history lets them self-serve the investigation.

**Independent Test**: Trigger an alert rule, call `GET /api/v1/alerts/history`, and verify the triggered event appears with a delivery status.

**Acceptance Scenarios**:

1. **Given** an authenticated user with past alert firings, **When** they call `GET /api/v1/alerts/history`, **Then** a paginated list is returned with each entry showing rule name, listing ID, trigger timestamp, and delivery status.
2. **Given** a `page` and `page_size` query parameter, **When** calling `GET /api/v1/alerts/history`, **Then** the response honours pagination and includes total count metadata.
3. **Given** a `rule_id` filter query parameter, **When** calling `GET /api/v1/alerts/history`, **Then** only history entries for that specific rule are returned.

---

### Edge Cases

- What happens when the ml-scorer gRPC service is temporarily slow but not down? (5s timeout applies; request fails with 503 if exceeded)
- What happens when a user's subscription downgrades mid-session and their existing rules exceed the new tier's limit? (Existing rules are preserved; creation of new rules is blocked until count falls below new limit)
- What happens when the OpenAPI spec file is missing or unreadable at startup? (Gateway fails to start with a clear configuration error)
- What happens when a circuit breaker is in half-open state and the probe call also fails? (Breaker returns to open state; cooldown resets)
- What happens when the zones table is unreachable during alert rule creation? (Return 503; do not create the rule)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST serve an interactive API documentation UI at `GET /api/docs` accessible without authentication.
- **FR-002**: System MUST serve the raw OpenAPI 3.1 specification at `GET /api/openapi.json` accessible without authentication.
- **FR-003**: The OpenAPI specification MUST document all REST endpoints including request bodies, response schemas, authentication requirements, and example values.
- **FR-004**: The OpenAPI specification MUST define a `BearerAuth` security scheme compatible with the existing JWT access token format.
- **FR-005**: The interactive documentation MUST allow users to authorize with a JWT and execute live API calls from within the UI.
- **FR-006**: The system MUST maintain a gRPC connection to the ml-scorer service with a 5-second per-call timeout (configurable via environment variable).
- **FR-007**: The system MUST maintain a gRPC connection to the ai-chat service with a 5-second per-call timeout (configurable via environment variable).
- **FR-008**: gRPC calls MUST be retried up to 3 times on transient `UNAVAILABLE` status before returning an error to the caller.
- **FR-009**: System MUST implement a circuit breaker for the ml-scorer gRPC connection with: closed state (normal operation), open state (immediate 503 after 5 consecutive failures within a 30-second window), and half-open state (one probe call after 30-second cooldown).
- **FR-010**: System MUST expose `GET /api/v1/model/estimate` requiring authentication, which proxies to the ml-scorer gRPC service and returns a property valuation with confidence score and SHAP values.
- **FR-011**: System MUST expose `GET /api/v1/alerts/rules` returning the authenticated user's active alert rules with pagination.
- **FR-012**: System MUST expose `POST /api/v1/alerts/rules` to create a new alert rule, enforcing tier limits before saving.
- **FR-013**: System MUST expose `PUT /api/v1/alerts/rules/{id}` to update an alert rule owned by the authenticated user.
- **FR-014**: System MUST expose `DELETE /api/v1/alerts/rules/{id}` to soft-delete an alert rule owned by the authenticated user.
- **FR-015**: System MUST expose `GET /api/v1/alerts/history` returning a paginated, filterable log of past alert firings with delivery status for the authenticated user.
- **FR-016**: System MUST enforce maximum active alert rule counts per subscription tier: free = 0, basic = 3, pro/global/api = unlimited.
- **FR-017**: System MUST validate alert rule filter payloads server-side, rejecting fields not permitted for the specified property category.
- **FR-018**: System MUST validate that all zone IDs in an alert rule exist and are active before saving the rule.

### Key Entities

- **AlertRule**: A user-configured trigger definition. Key attributes: ID, owner (user), name, target zones (list), property category, filter criteria (structured key-value conditions), notification channels, active status, creation and modification timestamps.
- **AlertHistory**: A record of a single alert rule firing. Key attributes: ID, parent rule, matched listing, trigger timestamp, delivery channel, delivery status (pending/delivered/failed), error detail (if failed).
- **CircuitBreakerState**: In-memory state tracking consecutive failures, last failure timestamp, and current state (closed/open/half-open) for each gRPC upstream connection.
- **MLEstimate**: A valuation response from the ml-scorer service. Attributes: estimated value, currency, confidence score (0–1), per-feature SHAP values, model version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers can explore and test any documented API endpoint from within the browser-based documentation UI without external tools.
- **SC-002**: On-demand property valuations are returned in under 5 seconds under normal ml-scorer availability.
- **SC-003**: When the ml-scorer is unavailable, clients receive an error response in under 5 seconds (no indefinitely hanging requests).
- **SC-004**: After 5 consecutive ml-scorer failures, subsequent requests fail immediately without making network calls, until a 30-second cooldown elapses.
- **SC-005**: Free-tier users are blocked from creating alert rules; Basic-tier users are limited to 3 active rules; enforcement is consistent across all creation attempts.
- **SC-006**: Alert rule filter validation rejects 100% of rule creation attempts containing disallowed fields or non-existent zone IDs.
- **SC-007**: Alert history responses are paginated and return within the standard API response time budget.
- **SC-008**: TypeScript types generated from the OpenAPI spec accurately reflect all documented request and response shapes, enabling type-safe frontend development.

## Assumptions

- The ml-scorer and ai-chat gRPC services expose Protobuf contracts already defined in `proto/` and generated into `libs/proto/`.
- Subscription tier information is available on the authenticated user context, populated by the existing JWT middleware using the `subscriptions` table.
- The `zones` table has an `is_active` boolean column that can be queried during alert rule validation.
- Alert rule filters use a well-defined set of allowed fields per property category; these allowed-field lists are maintained in the codebase (not dynamically configurable at runtime).
- The Swagger UI static assets are embedded into the binary at build time; no CDN dependency at runtime.
- The circuit breaker applies only to the ml-scorer; the ai-chat service uses the same retry policy but a simpler error pass-through for now.
- The `alert_rules` and `alert_history` tables do not yet exist and require a new database migration.
- TypeScript type generation is a build-time step for the frontend; the API Gateway itself does not serve or run TypeScript code.
