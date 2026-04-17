# Feature Specification: Alert Engine

**Feature Branch**: `016-alert-engine`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Build the Go alert engine that evaluates user rules against scored listings and routes to notification channels."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instant Alert on Matching Listing (Priority: P1)

A subscribed user has set up an alert rule for properties in a specific area, matching their criteria (price range, size, property type, deal quality). When a new listing is scored and matches their rule, they receive an immediate notification on their preferred channel — without having to check the platform manually.

**Why this priority**: This is the core value proposition of the alert engine. Users subscribed to instant alerts expect real-time notifications; any delay or missed match directly impacts user trust and retention.

**Independent Test**: Publish a scored listing that matches a single active instant rule. Verify that exactly one notification event is published within 500ms.

**Acceptance Scenarios**:

1. **Given** a user has one active instant alert rule, **When** a scored listing matching all rule criteria (country, zone, property type, price range, deal tier) is published, **Then** exactly one notification event is dispatched with the correct user ID, rule ID, and listing summary.
2. **Given** a user has one active instant alert rule, **When** a scored listing fails any single filter criterion, **Then** no notification is dispatched.
3. **Given** three users each have one active instant rule matching a single listing, **When** the listing is scored, **Then** three separate notification events are dispatched — one per matching rule.

---

### User Story 2 - Digest of Ranked Deals (Priority: P2)

A user prefers not to be interrupted by every individual match. Instead, they configure their alert rule for hourly or daily digest delivery. The system collects all matching deals over the interval, ranks them by deal quality, groups them by country, and delivers a single curated digest notification.

**Why this priority**: Digest delivery prevents notification fatigue for users monitoring broad searches. It is the preferred mode for users tracking large markets or multiple countries.

**Independent Test**: Configure one daily digest rule, buffer 5 matching listings over the interval, trigger digest compilation. Verify a single notification event is published containing all 5 listings ranked by deal score, grouped by country.

**Acceptance Scenarios**:

1. **Given** a user has an active daily digest rule and 5 matching listings are buffered, **When** the daily digest compilation runs, **Then** one notification event is published containing all 5 listings ranked by deal score descending, grouped by country.
2. **Given** more than 20 matching listings are buffered, **When** digest compiles, **Then** only the top 20 by deal score are included.
3. **Given** no listings are buffered for a user's digest rule, **When** the scheduled compilation runs, **Then** no notification event is published.

---

### User Story 3 - No Duplicate Notifications (Priority: P3)

A user should not receive repeated notifications for the same listing they have already been alerted about. If a listing is re-scored without a price change, the system silently skips it. Only a material change — specifically a price drop — re-triggers notification.

**Why this priority**: Duplicate alerts erode user trust and clutter notification channels. Once established, deduplication must be robust and persistent across restarts.

**Independent Test**: Send the same scored listing twice for the same user rule. Verify that only one notification is dispatched. Then simulate a price drop on the same listing and verify a second notification is correctly dispatched.

**Acceptance Scenarios**:

1. **Given** a listing has already triggered a notification for a user, **When** the same listing is re-scored at the same price, **Then** no notification is dispatched.
2. **Given** a listing has already triggered a notification for a user, **When** a price drop event is received for the same listing, **Then** a new notification is dispatched.
3. **Given** a listing has not previously triggered a notification for a user, **When** the listing matches the user's rule, **Then** a notification is dispatched and the pair is recorded.

---

### User Story 4 - Scale Across Thousands of Rules (Priority: P4)

The platform supports many active users, each potentially with multiple alert rules. The system must evaluate each incoming scored listing against all active rules without introducing unacceptable processing delays, even at peak load with 10,000 active rules.

**Why this priority**: Performance at scale is a prerequisite for the system to be commercially viable. Delays in evaluation directly delay user notifications.

**Independent Test**: Load 10,000 active rules into the cache. Publish a scored listing. Verify that all matching rules are evaluated and results dispatched within 500ms total.

**Acceptance Scenarios**:

1. **Given** 10,000 active rules are loaded, **When** a scored listing is published, **Then** all rules are evaluated and matching notifications dispatched within 500ms.
2. **Given** rules are indexed by country, **When** a listing for country "ES" is evaluated, **Then** only rules for country "ES" are evaluated — not rules for other countries.

---

### Edge Cases

- What happens when a listing matches the country filter but no active zone geometry is loaded for the rule's zones? Skip zone match; treat as country-only match.
- How does the system handle a malformed or incomplete scored listing event? Log and discard; do not crash the consumer.
- What if Redis is temporarily unavailable during dedup check? Fail open: allow the alert through and log the error.
- What if a rule's zone IDs reference zones that no longer exist? Skip zone intersection; treat rule as unmatched for that listing.
- What happens if the digest compilation goroutine falls behind schedule? Run the compilation immediately on the next tick; do not skip.
- What if a user's rule is deactivated between buffering and digest compilation? Skip the rule during compilation; discard its buffered entries.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST consume scored listing events and price change events from the event stream as they arrive.
- **FR-002**: System MUST evaluate each event against all active alert rules for the matching country.
- **FR-003**: System MUST apply rule filters in order: country match → zone intersection → property attribute filters → deal tier threshold. Evaluation MUST short-circuit on first non-match.
- **FR-004**: System MUST maintain an in-memory cache of all active alert rules, refreshed at regular intervals, indexed by country for fast lookup.
- **FR-005**: System MUST pre-load zone geometries for all rules that specify zone filters and use spatial intersection to verify a listing's location falls within the rule's zones.
- **FR-006**: System MUST track which listings have been notified per user. Within a 7-day window, a listing MUST NOT trigger a second notification for the same user unless a price drop has occurred.
- **FR-007**: System MUST route matches from instant-frequency rules to the immediate notification pipeline.
- **FR-008**: System MUST buffer matches from digest-frequency rules (hourly or daily) in a ranked structure, scored by deal quality.
- **FR-009**: System MUST compile and dispatch digest notifications on schedule: hourly digests every 60 minutes, daily digests every 24 hours.
- **FR-010**: Each digest MUST contain at most 20 listings, selected by highest deal score, grouped by country.
- **FR-011**: System MUST record each dispatched notification (rule, listing, channel, timestamp) in the notification history.
- **FR-012**: System MUST expose a health endpoint indicating readiness and liveness.
- **FR-013**: System MUST expose operational metrics: rules evaluated per second, match rate, notification dispatch rate, dedup hit rate, digest buffer depth.

### Key Entities

- **AlertRule**: A user-defined rule specifying search criteria (country, zones, property attributes, deal tier threshold), notification channels, and delivery frequency (instant, hourly, daily).
- **ScoredListing**: A property listing evaluated by the ML pipeline with a deal score and deal tier assigned.
- **PriceChangeEvent**: A signal that a listing's price has decreased materially, triggering re-evaluation for dedup bypass.
- **NotificationEvent**: A routable message dispatched to the notification pipeline containing user ID, matched rule, listing summary, and delivery channel.
- **DigestEntry**: A scored listing buffered for inclusion in a future digest, ranked by deal score.
- **NotificationHistory**: A persistent record of every alert dispatched, used for audit and user-facing history views.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each scored listing is fully evaluated against all active rules and results dispatched within 500 milliseconds.
- **SC-002**: The system operates without throughput degradation at 10,000 active rules.
- **SC-003**: A listing matching N rules for N distinct users generates exactly N notification events — no more, no fewer.
- **SC-004**: Zero duplicate notifications are dispatched for the same user/listing pair within a 7-day window, except following a price drop.
- **SC-005**: Digest notifications are compiled and dispatched within 60 seconds of their scheduled time.
- **SC-006**: Digest notifications contain the correct number of listings (up to 20), in descending deal score order, grouped by country.
- **SC-007**: False positive rate for rule matching is zero — every dispatched notification satisfies all filter criteria of the matched rule.

## Assumptions

- Alert rules are created, updated, and deactivated via the API Gateway; the alert engine is a read consumer of the `alert_rules` table.
- The ML scoring service publishes scored listing events to a known NATS subject; the alert engine consumes this without modification.
- Notification delivery (email, push, webhook) is handled by a separate downstream dispatcher service; the alert engine only publishes notification events to NATS.
- Zone geometries are stored in the database and available for pre-loading at startup.
- A `frequency` field (instant/hourly/daily) is available on each alert rule — this requires a schema migration if not already present.
- The deal tier filter specifies a maximum tier threshold; lower tier numbers represent better deals (tier 1 = great deal, tier 4 = overpriced).
- Price history is tracked by the pipeline; the alert engine receives explicit price change events rather than computing price deltas itself.
- The 7-day deduplication window is appropriate for the expected market dynamics.
