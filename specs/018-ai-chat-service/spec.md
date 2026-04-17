# Feature Specification: AI Conversational Search Service

**Feature Branch**: `018-ai-chat-service`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Build the Python AI conversational search service with LLM provider abstraction, prompt management, and visual references."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Progressive Property Search via Conversation (Priority: P1)

A user opens the AI chat and describes what they are looking for in natural language ("I want a modern apartment in the city centre, budget around 300k"). The AI asks focused follow-up questions one at a time to progressively refine the search criteria across multiple dimensions (location, property type, price, size, condition, style, amenities, deal type, urgency, extras). After sufficient refinement the AI presents a summary card and, on user confirmation, executes the search and creates a saved alert.

**Why this priority**: This is the core value proposition of the service — replacing rigid filter UIs with a guided conversation that produces qualified search results and a persistent alert.

**Independent Test**: A test conversation starting from a vague description can reach a confirmed search result and alert creation within 10 turns, demonstrating end-to-end value without any other feature.

**Acceptance Scenarios**:

1. **Given** a user sends "I want a 2-bedroom apartment near the beach under €250k", **When** the AI processes the message, **Then** it responds with a relevant question about one pending dimension and returns a partial criteria JSON block.
2. **Given** 10 conversational turns have refined all dimensions, **When** the AI marks criteria status as "ready", **Then** it presents a summary card with suggested chips and awaits user confirmation.
3. **Given** the user confirms the criteria, **When** finalization runs, **Then** matching listings are returned and an alert rule is created automatically.
4. **Given** a user reconnects with an existing session ID after a disconnection, **When** they send a new message, **Then** the conversation resumes from the last known state without data loss.

---

### User Story 2 - Visual Style Exploration (Priority: P2)

A user mentions a style preference ("something like a Scandinavian loft") during the conversation. The AI detects the style reference, triggers the visual reference library, and returns 4–5 curated property images matching the described style alongside its text response, helping the user articulate preferences they cannot easily express in words.

**Why this priority**: Visual references reduce ambiguity around style dimensions, improving criteria quality. It is non-blocking — the conversation works without it — making it a valuable enhancement rather than a prerequisite.

**Independent Test**: Sending a message containing a style keyword triggers visual references in the response without breaking the normal conversational flow.

**Acceptance Scenarios**:

1. **Given** a user's message contains a style keyword (e.g., "modern", "loft", "rustic"), **When** the AI responds, **Then** 4–5 relevant reference images are included alongside the text response.
2. **Given** a user's message has no style reference, **When** the AI responds, **Then** no images are included and the response is text-only.

---

### User Story 3 - Subscription-Gated Usage Limits (Priority: P3)

A user on the Free tier who has exhausted their daily conversation allowance attempts to start a new chat. The service rejects the request with a clear limit-exceeded error and prompts an upgrade. Within an active conversation, a user who reaches the turn limit for their tier is informed and the session is closed gracefully.

**Why this priority**: Subscription enforcement protects revenue. It is separable from core search logic — the conversation service functions correctly for permitted users even if this enforcement is absent.

**Independent Test**: A simulated Free-tier user making a 4th conversation request in the same day receives a rejection. A simulated Free-tier user exceeding 10 turns within one conversation receives a graceful closure message.

**Acceptance Scenarios**:

1. **Given** a Free-tier user has already had 3 conversations today, **When** they attempt to start a 4th, **Then** the request is rejected with a limit-exceeded error (equivalent to HTTP 403).
2. **Given** a Free-tier user is in a conversation and reaches turn 10, **When** they send another message, **Then** the service returns a graceful session-close message instead of a normal AI response.
3. **Given** a Pro+ user, **When** they start any conversation, **Then** no usage limits are applied.

---

### User Story 4 - Multi-Provider LLM Resilience (Priority: P4)

The platform operator has configured a primary and a fallback LLM provider. The primary provider encounters an error (timeout or rate limit) mid-conversation. The service transparently retries the same request using the fallback provider and delivers the response to the user without interruption.

**Why this priority**: Provider resilience is an operational concern rather than a user-facing feature. Users benefit indirectly through uptime. It is testable in isolation via fault injection.

**Independent Test**: Injecting a forced timeout on the primary provider results in the response being served from the fallback provider without exposing an error to the user.

**Acceptance Scenarios**:

1. **Given** the primary LLM provider returns a timeout error, **When** the service processes a user message, **Then** the request is retried against the fallback provider and a response is delivered.
2. **Given** both primary and fallback providers fail, **When** the service processes a user message, **Then** a user-friendly error is returned and the conversation state is preserved.

---

### Edge Cases

- What happens when the LLM returns a response without the required JSON criteria block?
- What happens when the LLM response JSON fails Pydantic validation?
- How does the system handle a Redis connection loss mid-conversation?
- What happens when the market context gRPC call to api-gateway times out?
- How are conversations with more than 40 messages handled (sliding window)?
- What happens when no visual references match the user's style tags?
- How does the system behave when the listings search or alert creation gRPC call fails at finalization?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST expose a bidirectional streaming gRPC interface for conversational interaction, delivering response tokens incrementally as they are generated.
- **FR-002**: The service MUST maintain conversation state (session ID, user ID, language, criteria state, turn count, message history) that persists across reconnections for at least 24 hours.
- **FR-003**: The service MUST support at least three LLM backends (Anthropic Claude, OpenAI GPT-4o, self-hosted models via LiteLLM) and allow the active provider to be selected via configuration without code changes.
- **FR-004**: The service MUST automatically retry a failed LLM request against a configured fallback provider before surfacing an error to the user.
- **FR-005**: The service MUST inject current zone-level market data (median prices, deal counts, listing volume) into each LLM request to ground the AI's responses in real market context.
- **FR-006**: The AI MUST guide the conversation through up to 10 property-search dimensions, asking at most one question per turn.
- **FR-007**: The service MUST extract and validate a structured criteria JSON block from every LLM response. If extraction fails, it MUST retry once; if it fails again, it MUST return the text response with the last known criteria state unchanged.
- **FR-008**: The service MUST return 4–5 curated visual reference images when the AI response signals a style preference is being explored.
- **FR-009**: When the AI declares criteria complete and the user confirms, the service MUST execute a listing search and create an alert rule, returning both results in the same streaming response.
- **FR-010**: The service MUST enforce per-tier daily conversation and per-conversation turn limits: Free (3 conversations/day, 10 turns), Basic (10 conversations/day, 20 turns), Pro+ (unlimited).
- **FR-011**: The service MUST respond in the language detected from the user's messages.

### Key Entities

- **Conversation**: A stateful session identified by a session ID, owned by a user, carrying language preference, message history, progressive criteria state, and turn count.
- **CriteriaState**: Structured representation of the property search criteria being progressively refined — includes status (in-progress / ready), confidence score, values for each search dimension, pending dimensions, and UI hints (chips, visual trigger flag).
- **LLMMessage**: A single exchange unit within the conversation history (role: user | assistant, content text, timestamp).
- **VisualReference**: A curated property image with descriptive tags (style, feature, property type) used to illustrate style preferences.
- **MarketContext**: Snapshot of zone-level real estate indicators (median price, deal count, listing volume) fetched fresh before each LLM call.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive the first streaming token of an AI response within 2 seconds of sending a message under normal load.
- **SC-002**: A full property search conversation (from open-ended description to confirmed search results) completes within 10 turns for at least 80% of test scenarios.
- **SC-003**: Criteria JSON output matches the platform taxonomy (all required fields present and valid) for 100% of test conversations when the LLM backend is functioning correctly.
- **SC-004**: Conversation state is fully recoverable after reconnection — no message history or criteria state is lost — across 100% of test reconnection scenarios.
- **SC-005**: The service remains available to permitted users during a primary LLM provider outage, falling back to the secondary provider with no user-visible error.
- **SC-006**: Subscription limits are enforced correctly (no over-limit conversations or turns allowed) across 100% of limit-boundary test cases.
- **SC-007**: Visual references are returned within the same streaming response as the AI text in 100% of cases where the AI signals a style preference.

## Assumptions

- Users are already authenticated; the service receives a verified user ID and subscription tier from the caller — it does not handle authentication itself.
- Zone taxonomy (countries, property types, active zones) is available via the existing api-gateway gRPC interface and does not require a new endpoint.
- The visual reference image collection (200+ images) is pre-seeded in the database; curation and upload tooling are out of scope for this feature.
- Market context data (zone median prices, deal counts) is available via an existing api-gateway gRPC method; if that call fails, the AI proceeds without market context rather than blocking the conversation.
- The LLM system prompt is authored in English; multilingual behaviour is delegated to the LLM via an explicit language instruction.
- Conversation history is capped at 40 messages using a sliding window; very long conversations lose the oldest messages, which is acceptable given the progressive refinement pattern.
- The alert rule created at finalization uses the same criteria JSON as the search query; no additional user configuration of the alert is required at this stage.
- Redis availability is a hard dependency; there is no in-memory fallback for conversation state.
