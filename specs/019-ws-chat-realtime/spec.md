# Feature Specification: WebSocket Chat & Real-Time Notifications

**Feature Branch**: `019-ws-chat-realtime`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Build the Go WebSocket server that handles AI chat streaming and real-time deal notifications. WebSocket endpoint /ws/chat with JWT authentication, bidirectional JSON protocol supporting multiple message types (chat, streamed tokens, chips, image carousels, criteria summaries, search results, errors). Forwards to AI chat service via streaming. Real-time deal notifications via NATS subscription. Connection management with ping/pong keepalive, idle timeout, graceful shutdown, and per-pod connection limits."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authenticated Chat Session with Streamed AI Responses (Priority: P1)

A registered user opens the property search chat interface. The system establishes a persistent connection using their existing session credentials. The user types a natural-language query such as "Show me 3-bedroom apartments in Milan under €300k near a metro station." The AI assistant begins responding immediately with streamed text tokens appearing word-by-word in the chat bubble, giving a conversational feel. The assistant may follow up with quick-reply chips ("Refine budget?", "Add parking?"), an image carousel of matching properties, a criteria summary card, and finally a set of search results.

**Why this priority**: This is the core value proposition — real-time conversational property search is the primary reason users engage with the chat feature. Without streaming responses, the chat experience feels sluggish and unresponsive.

**Independent Test**: Can be fully tested by connecting with valid credentials, sending a chat message, and verifying that response tokens stream back incrementally. Delivers immediate value as a standalone conversational search experience.

**Acceptance Scenarios**:

1. **Given** a user with a valid session token, **When** they initiate a chat connection, **Then** the connection is established and the user receives a confirmation that the session is ready.
2. **Given** an established chat session, **When** the user sends a natural-language property query, **Then** streamed text tokens begin arriving within 500 milliseconds.
3. **Given** an established chat session, **When** the AI assistant generates quick-reply suggestions, **Then** the user sees tappable chip options inline in the conversation.
4. **Given** an established chat session, **When** the AI assistant references visual property data, **Then** the user sees an image carousel with property photos they can swipe through.
5. **Given** an established chat session, **When** the AI assistant finalises search criteria, **Then** the user sees a structured criteria summary card followed by matching property listings.

---

### User Story 2 - Real-Time Deal Alert Delivery (Priority: P2)

A user is browsing the app (with an active chat or on any screen with a live connection) when a new property matching their saved alert criteria is scored by the system. Within seconds, the user receives an in-app notification pushed directly to their session — no need to wait for an email or Telegram message. The notification contains enough detail (property summary, price, score) for the user to decide whether to investigate further.

**Why this priority**: Real-time deal alerts dramatically reduce time-to-action on high-value opportunities. Delivering alerts through the already-open connection avoids notification fatigue from external channels and keeps users engaged in the app.

**Independent Test**: Can be tested by establishing a connection for a user who has active alert rules, then triggering a matching notification event and verifying it arrives at the client within 5 seconds.

**Acceptance Scenarios**:

1. **Given** a user with active alert rules and an open connection, **When** a new property matching their criteria is scored, **Then** the user receives a deal alert notification within 5 seconds.
2. **Given** a user with an open connection, **When** a deal alert arrives, **Then** the notification includes property summary, price, location, and relevance score.
3. **Given** a user with no active alert rules, **When** they have an open connection, **Then** they receive no unsolicited deal notifications.

---

### User Story 3 - Rejected Connection for Unauthenticated Users (Priority: P2)

An unauthenticated user (or one with an expired/invalid token) attempts to open a chat connection. The system immediately rejects the connection with a clear error indicating the authentication failure, without exposing internal details.

**Why this priority**: Security is a hard requirement — no unauthenticated user should access chat or receive notifications. This must work before any other scenario is meaningful.

**Independent Test**: Can be tested by attempting a connection with no token, an expired token, and a malformed token, verifying each is rejected with an appropriate error.

**Acceptance Scenarios**:

1. **Given** a user with no authentication token, **When** they attempt to connect, **Then** the connection is rejected with an authentication error.
2. **Given** a user with an expired token, **When** they attempt to connect, **Then** the connection is rejected with an authentication error.
3. **Given** a user with a malformed token, **When** they attempt to connect, **Then** the connection is rejected with an authentication error and no session is created.

---

### User Story 4 - Stable Long-Lived Connection (Priority: P3)

A user opens the app and keeps it running in the background while doing other things. The connection stays alive through periodic keepalive pings, surviving network micro-interruptions. After 30 minutes of no user-initiated activity, the connection is cleanly closed. If the user returns, reconnecting picks up the conversation context seamlessly.

**Why this priority**: Connection stability directly affects user trust. Dropped connections mid-conversation are frustrating and can lose context. However, this is lower priority than core chat and alerts since short sessions still deliver value.

**Independent Test**: Can be tested by establishing a connection, waiting through multiple keepalive cycles, verifying the connection remains active, then verifying it closes after the idle timeout. Reconnection can be tested by re-establishing a connection and verifying conversation history is preserved.

**Acceptance Scenarios**:

1. **Given** an established connection with no user activity, **When** 30 seconds pass, **Then** the system sends a keepalive ping and expects a pong response.
2. **Given** an established connection with no user-initiated messages, **When** 30 minutes of inactivity elapse, **Then** the connection is gracefully closed with a timeout notification.
3. **Given** a user whose connection was closed (timeout or network drop), **When** they reconnect with valid credentials, **Then** they can resume their previous conversation.

---

### User Story 5 - Graceful System Maintenance (Priority: P3)

During a planned deployment or scaling event, connected users experience a graceful transition. The system stops accepting new connections, drains existing ones with a warning message, and users can reconnect to a healthy instance within seconds.

**Why this priority**: Operational resilience is essential for production but is not user-facing in the same way as chat and alerts. Users should never lose data or context due to a deployment.

**Independent Test**: Can be tested by establishing connections, initiating a graceful shutdown signal, verifying users receive a shutdown notification, and confirming they can reconnect to a new instance.

**Acceptance Scenarios**:

1. **Given** multiple users with active connections, **When** the system initiates graceful shutdown, **Then** all connected users receive a shutdown warning message before disconnection.
2. **Given** a user disconnected due to shutdown, **When** they reconnect to another instance, **Then** their conversation context is preserved.

---

### Edge Cases

- What happens when a user sends a message while the AI service is unavailable? The system should return an error message type indicating temporary unavailability and retry guidance.
- What happens when a user opens multiple simultaneous connections from different devices? The system should allow multiple connections per user, each receiving deal notifications independently.
- What happens when a keepalive pong is not received? The connection should be closed after a configurable missed-pong threshold (assumed: 2 missed pongs).
- What happens when the per-pod connection limit is reached? New connection attempts should be rejected with a capacity error, allowing the load balancer to route to another pod.
- What happens when a deal notification arrives for a user whose connection just dropped? The notification should be delivered via fallback channels (email/Telegram) per existing alert dispatcher behaviour.
- What happens when the streamed AI response encounters a mid-stream error? The system should send an error message type to the client and cleanly terminate that response stream without dropping the connection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate users via JWT during the initial connection handshake, rejecting connections with missing, expired, or invalid tokens.
- **FR-002**: System MUST support a bidirectional JSON message protocol with the following server-to-client message types: `text_chunk` (streamed tokens), `chips` (quick-reply options), `image_carousel` (visual property references), `criteria_summary` (finalised criteria card), `search_results` (matching listings), and `error`.
- **FR-003**: System MUST support the `chat_message` client-to-server message type for user natural-language input.
- **FR-004**: System MUST forward user chat messages to the AI chat service via bidirectional streaming and relay streamed response tokens back to the client in real-time.
- **FR-005**: System MUST subscribe to the `alerts.notifications` message stream filtered by currently connected user IDs and push matching deal alerts to the appropriate user connections.
- **FR-006**: System MUST send keepalive pings every 30 seconds and expect pong responses to detect stale connections.
- **FR-007**: System MUST automatically disconnect idle connections after 30 minutes of no user-initiated activity (keepalive pings do not reset the idle timer).
- **FR-008**: System MUST enforce a per-pod connection limit of 10,000 simultaneous connections, rejecting new connections with a capacity error when the limit is reached.
- **FR-009**: System MUST support graceful shutdown by stopping new connection acceptance, notifying connected users, and draining existing connections before terminating.
- **FR-010**: System MUST allow users to reconnect and resume their previous conversation context after disconnection.
- **FR-011**: System MUST support multiple simultaneous connections per user (e.g., different devices), each receiving notifications independently.
- **FR-012**: System MUST return structured error messages (using the `error` message type) for AI service unavailability, malformed client messages, and mid-stream failures without terminating the connection.

### Key Entities

- **Connection**: Represents an active user session — associated with a user identity, device context, connection timestamp, and last-activity timestamp. A user may have multiple concurrent connections.
- **Chat Message**: A unit of conversation — either a user query (client-to-server) or an AI response fragment (server-to-client). Each message has a type, a conversation identifier, and a timestamp.
- **Deal Notification**: A real-time alert payload containing property summary, price, location, relevance score, and the originating alert rule reference. Delivered to all active connections for the target user.
- **Conversation**: A logical grouping of chat messages tied to a user session. Persists across reconnections to enable conversation resumption.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive the first streamed response token within 500 milliseconds of sending a chat message.
- **SC-002**: System supports 1,000 concurrent user connections per instance without degradation in response latency or message delivery.
- **SC-003**: Deal alert notifications are delivered to connected users within 5 seconds of the scoring event.
- **SC-004**: Connections remain stable for at least 30 minutes of idle time through keepalive mechanisms, with automatic cleanup after the idle threshold.
- **SC-005**: Users can reconnect and resume their conversation within 10 seconds of a disconnection event.
- **SC-006**: During graceful shutdown, 100% of connected users receive a shutdown notification before disconnection.
- **SC-007**: All connection attempts with invalid, expired, or missing authentication tokens are rejected within 1 second.
- **SC-008**: All structured message types (text chunks, chips, image carousels, criteria summaries, search results) render correctly on the client without data loss.

## Assumptions

- The existing JWT-based authentication system (from the API gateway) will be reused for connection authentication — no new auth mechanism is needed.
- The AI chat service (feature 018) is already deployed and exposes a bidirectional streaming interface for conversation handling.
- The `alerts.notifications` NATS stream is already published by the alert engine (feature 016) and notification dispatcher (feature 017).
- Conversation state and history are managed by the AI chat service (Redis-backed); this feature does not maintain its own conversation persistence.
- Client-side reconnection logic (exponential backoff, session resumption) is the responsibility of the frontend — this feature provides the server-side support for resumption.
- Multiple connections per user are allowed; each connection independently receives notifications and chat responses.
- The per-pod connection limit of 10,000 is a soft limit enforced at the application level; horizontal scaling handles capacity beyond a single pod.
- Load balancing and connection routing across pods is handled by the infrastructure layer (Kubernetes ingress/service mesh) and is out of scope.
- Message ordering within a single conversation stream is guaranteed; cross-conversation ordering is not required.
