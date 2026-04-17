# Feature Specification: API Gateway

**Feature Branch**: `006-api-gateway`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Build the Go API Gateway service with authentication, rate limiting, and core middleware."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Secure Account Registration and Login (Priority: P1)

A new visitor wants to create an account and start using EstateGap. They register with an email and password, receive tokens, and can access protected resources immediately.

**Why this priority**: Authentication is the foundation for all user-specific features. Without it, no personalized functionality (alerts, saved searches, subscription management) is accessible.

**Independent Test**: Can be fully tested by registering a new user, logging in, accessing a protected endpoint with the returned token, and verifying the token refresh/logout flow delivers working session management.

**Acceptance Scenarios**:

1. **Given** a valid email and password, **When** the user POSTs to `/v1/auth/register`, **Then** the system creates an account and returns access + refresh tokens.
2. **Given** registered credentials, **When** the user POSTs to `/v1/auth/login`, **Then** the system returns new access + refresh tokens.
3. **Given** a valid access token, **When** the user calls a protected endpoint, **Then** the system returns the expected resource (200).
4. **Given** an expired or invalid access token, **When** the user calls a protected endpoint, **Then** the system returns 401 with a descriptive error.
5. **Given** a valid refresh token, **When** the user POSTs to `/v1/auth/refresh`, **Then** the system issues a new access token and rotates the refresh token.
6. **Given** a logged-in session, **When** the user POSTs to `/v1/auth/logout`, **Then** the refresh token is invalidated and the access token is blacklisted.

---

### User Story 2 - Google OAuth2 Social Login (Priority: P2)

A user prefers to sign in with their Google account rather than creating a password-based account. The system creates or links their EstateGap account automatically.

**Why this priority**: Social login reduces friction for new user acquisition. It is self-contained and does not depend on any other gateway feature to deliver value.

**Independent Test**: Can be fully tested by initiating the OAuth2 flow at `/v1/auth/google`, completing the Google consent screen, and verifying a valid session is established with tokens returned.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user, **When** they visit `/v1/auth/google`, **Then** they are redirected to Google's authorization page with a CSRF-safe state parameter.
2. **Given** a valid Google callback with code and state, **When** Google redirects to `/v1/auth/google/callback`, **Then** the system creates or links a user account and returns tokens.
3. **Given** an invalid or expired state parameter, **When** the callback is received, **Then** the system returns 400 to prevent CSRF attacks.

---

### User Story 3 - Rate Limiting by Subscription Tier (Priority: P3)

An API consumer sends requests at high frequency. The system enforces per-user rate limits based on their subscription tier and communicates the limit clearly when exceeded.

**Why this priority**: Rate limiting protects the platform from abuse and ensures fair resource allocation. It can be tested independently on any authenticated endpoint.

**Independent Test**: Can be fully tested by sending requests exceeding the tier limit and verifying 429 responses with the correct `Retry-After` header are returned, while requests under the limit succeed normally.

**Acceptance Scenarios**:

1. **Given** a Free-tier user, **When** they send more than 30 requests within a 60-second window, **Then** the 31st request returns 429 with a `Retry-After` header.
2. **Given** a Pro-tier user, **When** they send up to 300 requests per minute, **Then** all requests succeed.
3. **Given** a rate-limited user who waits for the window to reset, **When** they send a new request, **Then** it succeeds normally.

---

### User Story 4 - Health and Readiness Probes (Priority: P1)

A Kubernetes operator needs to verify that the API Gateway is alive and ready to handle traffic. The service exposes liveness and readiness endpoints for cluster orchestration.

**Why this priority**: Without these probes, Kubernetes cannot perform rolling deploys, detect crashes, or remove unhealthy pods from the load balancer.

**Independent Test**: Can be fully tested by calling `/healthz` and `/readyz` and verifying responses reflect the actual state of all dependencies.

**Acceptance Scenarios**:

1. **Given** the service is running, **When** `/healthz` is called, **Then** 200 is returned immediately (no dependency checks).
2. **Given** all dependencies (PostgreSQL, Redis, NATS) are reachable, **When** `/readyz` is called, **Then** 200 is returned with a JSON status object.
3. **Given** PostgreSQL is unreachable, **When** `/readyz` is called, **Then** 503 is returned indicating which dependency failed.

---

### User Story 5 - Structured Request Logging and Metrics (Priority: P3)

An operations engineer wants to trace a specific user's request through the logs and monitor overall API performance through Prometheus metrics.

**Why this priority**: Observability is independently testable and orthogonal to business logic. It enables incident response and SLA monitoring.

**Independent Test**: Can be fully tested by making any request and verifying a structured JSON log line is emitted with all required fields, and that `/metrics` exposes the expected counters and histograms.

**Acceptance Scenarios**:

1. **Given** any inbound request, **When** it completes, **Then** a JSON log line is written containing `request_id`, `user_id` (if authenticated), `method`, `path`, `status`, and `duration_ms`.
2. **Given** the service is running, **When** `/metrics` is called, **Then** `http_requests_total`, `http_request_duration_seconds`, and `active_connections` are present.

---

### Edge Cases

- What happens when a registration request uses an already-registered email? → 409 Conflict.
- What happens if the Redis connection drops mid-request? → Rate limit check fails open (request passes through) but is logged as an error; health check returns 503.
- What happens if the JWT secret is rotated? → All outstanding access tokens become invalid; users must re-authenticate; refresh tokens in Redis are unaffected until their TTL expires.
- What happens when a Google OAuth callback arrives after the 10-minute state TTL? → 400 Bad Request; user must restart the OAuth flow.
- What happens if the database primary is unavailable during a write? → 503 with a descriptive error; the write is not attempted against the replica.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a single HTTP entry point on port 8080 for all external REST API traffic.
- **FR-002**: System MUST provide `/healthz` (liveness) and `/readyz` (readiness with dependency checks) endpoints.
- **FR-003**: System MUST allow users to register with email and password; passwords MUST be hashed with a strong one-way algorithm.
- **FR-004**: System MUST issue short-lived access tokens (15 minutes) and long-lived refresh tokens (7 days) upon successful authentication.
- **FR-005**: System MUST validate and reject expired or malformed access tokens with 401.
- **FR-006**: System MUST support token refresh: exchanging a valid refresh token for a new access token + rotated refresh token.
- **FR-007**: System MUST invalidate sessions on logout by revoking the refresh token and blacklisting the outstanding access token.
- **FR-008**: System MUST support Google OAuth2 login; state parameters MUST be validated to prevent CSRF attacks.
- **FR-009**: System MUST link Google accounts to existing email accounts when the email matches.
- **FR-010**: System MUST enforce per-user rate limits based on subscription tier; exceeded limits MUST return 429 with `Retry-After`.
- **FR-011**: Rate limits by tier: Free=30/min, Basic=120/min, Pro=300/min, Global=600/min, API=1200/min.
- **FR-012**: System MUST apply CORS headers with a configurable list of allowed origins.
- **FR-013**: System MUST emit a structured JSON log line for every request containing correlation ID, user ID, method, path, status, and duration.
- **FR-014**: System MUST expose Prometheus metrics at `/metrics`: `http_requests_total`, `http_request_duration_seconds`, `active_connections`.
- **FR-015**: System MUST use read replicas for read queries and the primary for write queries.
- **FR-016**: System MUST shut down gracefully, draining in-flight requests before exiting.
- **FR-017**: System MUST support NATS connectivity check in `/readyz`.
- **FR-018**: System MUST be deployable as a Kubernetes workload via Helm with a Dockerfile producing an image under 20 MB.

### Key Entities

- **User**: Represents an EstateGap account. Has identity (email, OAuth), subscription tier, alert limits, and soft-delete support.
- **Session**: A pair of (access token, refresh token). Access token is a signed JWT. Refresh token is a random UUID stored in Redis with TTL.
- **RateLimit Counter**: Per-user sliding window counter stored in Redis, keyed by `ratelimit:{user_id}`, with 60s TTL.
- **OAuthState**: A CSRF-prevention nonce stored in Redis with 10-minute TTL, keyed by `oauth:state:{state_value}`.
- **TokenBlacklist**: Set of revoked-but-not-yet-expired access tokens in Redis, with TTL matching the token's remaining lifetime.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Health and readiness probes respond within 500ms under normal operating conditions.
- **SC-002**: Authentication flows (register, login, refresh) complete successfully in under 300ms at p95.
- **SC-003**: Rate limit enforcement is accurate: no request above the per-tier threshold succeeds within the enforcement window.
- **SC-004**: 100% of inbound requests produce a structured log entry with all required correlation fields.
- **SC-005**: The built container image is under 20 MB.
- **SC-006**: The service starts and is ready to accept traffic within 5 seconds of container start.
- **SC-007**: Zero requests are dropped during a graceful shutdown initiated while requests are in flight.

## Assumptions

- Users have a stable network connection; offline-mode is out of scope.
- The PostgreSQL primary and at least one read replica are always provisioned by the infrastructure layer.
- Redis is deployed as a single-node instance for v1; Redis Cluster or Sentinel is out of scope.
- Stripe integration (subscription billing webhooks) is scaffolded but not fully implemented in this feature; it is deferred to a dedicated billing feature.
- Email verification flow (sending verification emails) is out of scope for this feature; the `email_verified` flag is persisted but the email-sending pipeline is separate.
- NATS connectivity is required for `/readyz` but no NATS publishing occurs in the gateway for v1.
- All secrets (JWT secret, DB credentials, Redis URL, Google OAuth credentials) are injected via environment variables and never hard-coded.
- The gateway does not implement service-mesh mTLS; that is handled at the Kubernetes infrastructure layer.
