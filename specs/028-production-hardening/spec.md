# Feature Specification: Production Hardening

**Feature Branch**: `028-production-hardening`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Harden the platform for production: performance optimization, security audit, GDPR compliance, load testing, and operational documentation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fast Listing Search (Priority: P1)

A property buyer searches for listings in a specific zone. Results appear quickly even under high concurrent load, with the system serving cached responses where appropriate.

**Why this priority**: Listing search is the core user journey — slow searches directly harm conversion and user retention.

**Independent Test**: Can be fully tested by performing listing search requests under load and verifying p95 response time stays below 300ms.

**Acceptance Scenarios**:

1. **Given** a logged-in user, **When** they search listings with any filter combination, **Then** results are returned in under 300ms at p95
2. **Given** cached zone stats, **When** the same query is repeated within 5 minutes, **Then** the response is served from cache without hitting the database
3. **Given** 1000 concurrent users searching simultaneously, **When** the load test runs for 5 minutes, **Then** error rate stays below 1% and HPA scales to meet demand

---

### User Story 2 - Secure Platform Access (Priority: P1)

A user accesses the platform knowing their data is protected by strong security controls: rate-limited authentication, CORS restrictions, and content security policies that prevent XSS.

**Why this priority**: Security vulnerabilities can expose all user data and destroy trust — must be resolved before production launch.

**Independent Test**: Can be fully tested by running OWASP ZAP scan and verifying no high/critical findings, plus attempting >5 auth attempts in 60s and confirming blocking.

**Acceptance Scenarios**:

1. **Given** an attacker trying brute-force login, **When** they exceed 5 attempts per minute from the same IP, **Then** further attempts are rejected for 60 seconds
2. **Given** a request from an unlisted origin, **When** it attempts a cross-origin request, **Then** it is rejected by CORS policy
3. **Given** an OWASP ZAP automated scan, **When** run against the production-equivalent environment, **Then** no high or critical findings are reported
4. **Given** all sensitive configuration values, **When** deployed to Kubernetes, **Then** they are stored as Sealed Secrets and never appear in plaintext in the repository

---

### User Story 3 - GDPR Rights Fulfilment (Priority: P2)

A registered user exercises their GDPR rights: they can export all personal data as a JSON file, request account deletion, and control cookie consent. A non-EU visitor still sees the cookie consent banner on first visit.

**Why this priority**: Legal compliance is mandatory before serving EU users. Violations carry significant penalties.

**Independent Test**: Can be fully tested by triggering data export and verifying completeness, then deleting an account and confirming cascade anonymisation within 24 hours.

**Acceptance Scenarios**:

1. **Given** a logged-in user, **When** they request a data export, **Then** they receive a JSON file containing all their profile data, conversations, alert rules, portfolio properties, and alert history
2. **Given** a user who requests account deletion, **When** the request is confirmed, **Then** their PII is anonymised immediately and all records are hard-deleted within 30 days
3. **Given** a first-time visitor, **When** they load any page, **Then** a cookie consent banner is shown before any analytics are activated
4. **Given** a user who refuses cookies, **When** they browse the platform, **Then** no analytics or tracking scripts are loaded

---

### User Story 4 - Operational Confidence (Priority: P3)

An on-call engineer responding to a production incident uses the runbook to diagnose the issue, apply a resolution playbook, and restore service. The runbook covers all common failure modes.

**Why this priority**: Operational documentation reduces mean time to recovery (MTTR) and enables team scalability.

**Independent Test**: Can be fully tested by conducting a tabletop exercise for each incident type in the runbook and verifying each playbook leads to resolution.

**Acceptance Scenarios**:

1. **Given** a scraper blocking incident, **When** an engineer consults the runbook, **Then** they find a step-by-step resolution playbook with diagnostic commands
2. **Given** a database full alert, **When** an engineer follows the backup/restore section, **Then** they can restore from the latest backup with documented commands
3. **Given** a complete cluster failure, **When** an engineer follows the disaster recovery section, **Then** they can rebuild from Helm charts and the latest backup

---

### Edge Cases

- What happens when a user requests data export while account deletion is in progress?
- How does the system behave when Redis is unavailable — does it fall back to DB queries gracefully?
- What happens when the K6 load test saturates NATS — does backpressure propagate correctly?
- How does cookie consent interact with server-side analytics (not just client-side)?
- What if a hard-delete CronJob fails — is there a retry mechanism and alerting?

## Requirements *(mandatory)*

### Functional Requirements

**Performance**

- **FR-001**: The system MUST cache zone statistics responses in Redis with a 5-minute TTL
- **FR-002**: The system MUST cache top deals responses in Redis with a 1-minute TTL
- **FR-003**: The system MUST cache alert rules in Redis with a 60-second TTL
- **FR-004**: The system MUST identify the 10 slowest database queries via pg_stat_statements and add appropriate indexes
- **FR-005**: The frontend MUST use dynamic imports for Map and Chart components
- **FR-006**: The frontend MUST use optimised image delivery via the platform image service
- **FR-007**: The frontend JavaScript bundle MUST be under 200KB gzipped for the initial load

**Security**

- **FR-008**: The API MUST restrict cross-origin requests to an allowlist configured via environment variable
- **FR-009**: The API MUST serve Content-Security-Policy headers, initially in report-only mode then enforced
- **FR-010**: All sensitive configuration (database password, JWT secret, Stripe keys, LLM API key, proxy credentials, SES credentials, Redis password) MUST be stored as Sealed Secrets in Kubernetes
- **FR-011**: Authentication endpoints MUST enforce a rate limit of 5 attempts per minute per IP address
- **FR-012**: The CI pipeline MUST scan Python dependencies with pip-audit, Go dependencies with govulncheck, and Node.js dependencies with npm audit, failing on high-severity findings

**GDPR**

- **FR-013**: The platform MUST display a cookie consent banner on first visit and block analytics until consent is given
- **FR-014**: The platform MUST provide a privacy policy page in all supported languages
- **FR-015**: The API MUST expose a data export endpoint returning all user data as a downloadable JSON file
- **FR-016**: The API MUST expose an account deletion endpoint that immediately anonymises PII and schedules hard deletion within 30 days
- **FR-017**: The platform MUST provide a form for agents/third parties to submit data removal requests

**Load Testing**

- **FR-018**: K6 load test scripts MUST cover listing search (1000 VUs, 5 minutes), AI chat (100 VUs, 10 minutes), alert dispatch burst (10k messages), and scraping pipeline throughput (50k NATS messages)
- **FR-019**: Load tests MUST be executable as in-cluster Kubernetes Jobs for accurate latency measurement
- **FR-020**: Load test results MUST capture p50, p95, p99 latency, error rate, and HPA scaling events via Grafana

**Documentation**

- **FR-021**: A runbook MUST be published covering: architecture overview, service dependency map, incident playbooks (scraper blocked, model degraded, DB full, NATS lag), scaling procedures, backup/restore, disaster recovery, and escalation contacts

### Key Entities

- **CacheEntry**: Redis key (query hash), value (serialised response), TTL — ephemeral, no DB persistence
- **SealedSecret**: Encrypted Kubernetes secret manifest, tied to a specific cluster's sealing key
- **CookieConsent**: User preference (accept/reject), stored as a cookie with expiry, no server-side persistence required
- **DataExport**: Snapshot of all user-owned records at export time, delivered as a one-time JSON download
- **AccountDeletionJob**: Soft-delete timestamp, anonymised PII fields, hard-delete scheduled date
- **LoadTestResult**: K6 summary (p50/p95/p99, error rate, VU count, duration), linked to Grafana snapshot

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Listing search p95 response time is under 300ms under 1000 concurrent users
- **SC-002**: Dashboard page fully loads in under 2 seconds on a standard broadband connection
- **SC-003**: OWASP ZAP automated scan produces zero high or critical findings
- **SC-004**: All CI dependency scans complete with zero high-severity findings
- **SC-005**: Data export returns a complete JSON file containing all user-owned records within 30 seconds
- **SC-006**: Account deletion anonymises PII within 1 minute of confirmation and completes hard deletion within 30 days
- **SC-007**: The system sustains all four load test scenarios without exceeding 1% error rate and with HPA scaling to the required replica count
- **SC-008**: The runbook enables an on-call engineer unfamiliar with the system to diagnose and resolve each documented incident type in under 30 minutes
- **SC-009**: Backup restore test completes successfully, recovering all data to a point-in-time within the last 24 hours

## Assumptions

- Existing user authentication and session management infrastructure is already in place and will be extended (not replaced) for rate limiting
- The platform already runs on Kubernetes with Helm; Sealed Secrets controller installation is additive
- All supported locales are already defined in the next-intl configuration; privacy policy content will be authored in those locales
- Analytics scripts are loaded client-side and can be conditionally blocked by the cookie consent mechanism
- The 30-day hard-delete window for account deletion satisfies applicable GDPR retention obligations (to be confirmed with legal)
- Load tests will be run in a staging environment that mirrors production resource limits (HPA min/max replicas, node sizes)
- pg_stat_statements extension is already enabled on the PostgreSQL instance
- The Grafana stack is already deployed and accessible for monitoring during load tests
