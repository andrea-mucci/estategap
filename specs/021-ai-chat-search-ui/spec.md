# Feature Specification: AI Conversational Search UI

**Feature Branch**: `021-ai-chat-search-ui`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Build the AI conversational search UI — the primary entry point of the application."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Home Page Search Entry (Priority: P1)

A visitor arrives at the home page and sees a prominent, Google-like search input centred on the screen. They type a natural-language property query (e.g. "3-bedroom apartment in Barcelona under €500k") and press Enter. The application transitions into a full chat window with the AI assistant.

**Why this priority**: This is the primary entry point of the entire product. Without it no user can begin a property search.

**Independent Test**: Load the home page, type a query, press Enter — the chat window opens and the assistant begins responding.

**Acceptance Scenarios**:

1. **Given** a user lands on the home page, **When** the page renders, **Then** a centred text input with a localised placeholder and a microphone button are the dominant visual elements.
2. **Given** the user types a query and presses Enter (or clicks Send), **When** the submission is processed, **Then** the view transitions to the chat window showing the user's message and an AI typing indicator.
3. **Given** the placeholder text, **When** the locale is switched, **Then** the placeholder text updates to the selected language.

---

### User Story 2 - Voice Input (Priority: P1)

A user clicks the microphone button. The mic pulses to signal it is listening. They speak their query. After 2 seconds of silence the recording stops, the transcription appears in the text input, and the user can review and send.

**Why this priority**: Voice is the primary input method on mobile; it also differentiates the product for accessibility.

**Independent Test**: Click mic, speak a sentence, wait 2s — transcription text appears in the input field.

**Acceptance Scenarios**:

1. **Given** the user is on Chrome, Edge, or Safari, **When** they click the microphone, **Then** the browser speech recognition API starts and the mic button shows a pulsing animation.
2. **Given** the microphone is active, **When** the user stops speaking for 2 seconds, **Then** recognition stops automatically and the transcription is placed in the input field.
3. **Given** interim results are available, **When** the user is speaking, **Then** partial transcription is shown live in the input field.
4. **Given** the user's browser does not support the Web Speech API, **When** they click the microphone, **Then** a Whisper API fallback is invoked for speech-to-text.
5. **Given** the user denies microphone permission, **When** they click the microphone, **Then** a friendly message explains how to grant permission.

---

### User Story 3 - Streaming Chat Conversation (Priority: P1)

An authenticated user asks the AI assistant a property question. The assistant's reply streams in token-by-token with a typewriter effect. The user can respond with typed text, tap a quick-reply chip, or interact with image carousels and criteria cards embedded in the conversation.

**Why this priority**: Conversational interaction is the core product loop for collecting search criteria.

**Independent Test**: Send a message, observe token-by-token text rendering; tap a chip, observe it sent as a new user message.

**Acceptance Scenarios**:

1. **Given** the assistant is generating a reply, **When** tokens arrive over WebSocket, **Then** each token is appended to the message bubble with a smooth typewriter animation (no layout jumps).
2. **Given** the assistant sends a chip list, **When** the chips render, **Then** tapping one sends its label as a user chat message.
3. **Given** the assistant embeds an image carousel, **When** the user swipes (mobile) or clicks (desktop) a card and taps "Like this" or "Not this", **Then** the feedback is sent as a `image_feedback` WebSocket message.
4. **Given** the assistant embeds a criteria summary card, **When** the user clicks the edit icon on a field, **Then** an inline input or select appears; on save the updated value is reflected immediately.
5. **Given** the user scrolls up to read history, **When** a new message arrives, **Then** the view auto-scrolls to the bottom.

---

### User Story 4 - Inline Search Results (Priority: P2)

After the user confirms their search criteria, matching property listings appear below the chat as cards containing a photo, price, deal score badge, and key attributes. The user can toggle a map view, sort listings, and scroll infinitely to load more.

**Why this priority**: This is the payoff of the conversation flow — it delivers the actual property search results.

**Independent Test**: Confirm criteria in the summary card, observe listings render within 2 seconds; toggle map, observe map/list switch.

**Acceptance Scenarios**:

1. **Given** the user confirms search criteria, **When** the backend returns results, **Then** listing cards appear below the chat within 2 seconds.
2. **Given** listing cards are displayed, **When** the user scrolls to the bottom, **Then** the next page of results loads automatically (infinite scroll).
3. **Given** listing cards are displayed, **When** the user clicks the map toggle, **Then** a map view replaces the card list with pins for each listing.
4. **Given** listing cards are displayed, **When** the user selects a sort option (price, deal score, date), **Then** the list re-orders immediately.
5. **Given** a listing card, **When** it renders, **Then** it shows photo, price (formatted for locale), deal score badge (colour-coded), bedrooms, area, and location.

---

### User Story 5 - Conversation Persistence and History (Priority: P2)

An authenticated user navigates away from the chat and returns. Their conversation is exactly where they left it. They can also view a sidebar listing all recent conversations with snippet previews and switch between them.

**Why this priority**: Persistence prevents loss of work and enables multi-session property search journeys.

**Independent Test**: Start a conversation, navigate to another page, return — conversation is intact; open sidebar, see list of recent conversations.

**Acceptance Scenarios**:

1. **Given** an active conversation, **When** the user navigates to a different page and returns, **Then** the full conversation history and current criteria are restored.
2. **Given** the conversation sidebar is open, **When** it renders, **Then** each item shows a snippet of the last message and a relative timestamp.
3. **Given** multiple past conversations, **When** the user clicks one in the sidebar, **Then** that conversation's full history is loaded.
4. **Given** the user is not authenticated, **When** they access the chat, **Then** they are prompted to sign in to save conversation history (unauthenticated users get a single ephemeral session).

---

### Edge Cases

- What happens when the WebSocket disconnects mid-stream? → The in-progress message is marked as incomplete; a reconnect attempt is made immediately; once reconnected the assistant can continue or start a new turn.
- What if the browser does not support both Web Speech API and the Whisper fallback (offline)? → The mic button is hidden; the user can only type.
- What happens when no listings match the confirmed criteria? → An empty-state illustration with a "Refine your search" chip is shown instead of cards.
- What if the user sends a message while a previous response is still streaming? → The new message is queued and sent after the stream completes.
- What happens when voice recognition produces no transcript (ambient noise)? → The mic resets to idle state without filling the input.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The home page MUST display a centred search input with a localised placeholder as the primary visual element.
- **FR-002**: The search input MUST include a microphone button that triggers voice input.
- **FR-003**: Voice input MUST use the Web Speech API (with webkit prefix for Safari) and fall back to Whisper API when unavailable.
- **FR-004**: Voice recognition MUST auto-stop after 2 seconds of silence.
- **FR-005**: Interim transcription MUST be shown live in the input field while the user is speaking.
- **FR-006**: The chat window MUST display the full conversation history, auto-scrolling to the latest message on new arrivals.
- **FR-007**: Assistant messages MUST render streaming text token-by-token using a typewriter effect.
- **FR-008**: Streaming MUST be implemented with a 50ms flush buffer and `requestAnimationFrame` to avoid excessive re-renders.
- **FR-009**: The system MUST support rendering the following message attachment types inline: `ChipSelector`, `ImageCarousel`, `CriteriaSummaryCard`, `TypingIndicator`.
- **FR-010**: Tapping a chip MUST send the chip's label as a user `chat_message` WebSocket event.
- **FR-011**: The image carousel MUST be swipeable on touch devices and clickable on desktop, with snap points.
- **FR-012**: "Like this" / "Not this" actions on image carousel cards MUST send an `image_feedback` WebSocket event.
- **FR-013**: The criteria summary card MUST allow inline editing of individual fields.
- **FR-014**: After criteria confirmation, matching listings MUST appear within 2 seconds as cards with photo, price, deal score badge, and key attributes.
- **FR-015**: Listing results MUST support infinite scroll, map toggle, and sort controls (price, deal score, date).
- **FR-016**: Conversation state MUST persist in `sessionStorage` so it survives page navigation.
- **FR-017**: The conversation sidebar MUST list recent conversations with snippet and timestamp; clicking one loads that conversation.
- **FR-018**: The chat state MUST be managed via a Zustand store (`chatStore`) with sessions map, active session pointer, and actions: `createSession`, `addMessage`, `updateCriteria`, `confirmSearch`.
- **FR-019**: Voice input MUST work in Chrome, Edge, and Safari in English, Spanish, and French locales.
- **FR-020**: Markdown MUST be rendered in assistant message bubbles.

### Key Entities

- **ChatSession**: A stateful AI conversation (sessionId, userId, messages[], criteria, status: searching | confirming | confirmed | complete, createdAt, updatedAt).
- **ChatMessage**: One message in a session (id, role: user | assistant, content, attachments[], timestamp, isStreaming).
- **MessageAttachment**: Polymorphic: `chips` (label[]), `carousel` (images with Like/Not), `criteria` (key-value map), `listings` (Listing[]).
- **Listing**: A property search result shown inline (listingId, title, price, currency, dealScore, photos[], attributes, mapCoords).
- **VoiceInputState**: Enum — `idle | listening | processing | error`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The search input is visible above the fold on all viewports without scrolling.
- **SC-002**: Voice-to-text transcription appears in the input field within 500ms of recognition completing.
- **SC-003**: Streaming tokens render at ≥ 30 frames per second with no visible layout jumps.
- **SC-004**: Chips, carousels, and criteria cards are interactive within 200ms of render.
- **SC-005**: Listing cards appear within 2 seconds of criteria confirmation on a standard broadband connection.
- **SC-006**: Conversation state is fully restored after navigating away and returning.
- **SC-007**: Voice input works correctly in Chrome, Edge, and Safari in English, Spanish, and French.
- **SC-008**: The image carousel is swipeable on mobile (< 768px) and clickable on desktop (≥ 1024px).
- **SC-009**: The conversation sidebar shows all recent conversations with correct snippet and timestamp.
- **SC-010**: The Whisper API fallback activates automatically on browsers without Web Speech API support.

## Assumptions

- The WebSocket endpoint is provided by the existing `019-ws-chat-realtime` service and the message protocol (text_chunk, chat_message, image_feedback, criteria_update, listings_ready) is already defined.
- The AI chat backend (`018-ai-chat-service`) returns structured attachment payloads (chips, carousels, criteria) within the WebSocket message stream.
- The listings API (from `007-listing-zone-endpoints`) is available for fetching search results after criteria confirmation.
- The frontend foundation (`020-nextjs-frontend-foundation`) provides authentication, i18n (next-intl), TanStack Query, and the Zustand store infrastructure.
- The Whisper API key is available as an environment variable for the fallback speech-to-text path.
- The deal score is a 0–100 numeric value produced by the ML scorer; colour coding thresholds are: green ≥ 70, amber 40–69, red < 40.
- Unauthenticated users can start a conversation but are prompted to sign in to save history; session is ephemeral (in-memory only) without auth.
- react-markdown and its remark plugins are available as frontend dependencies.
- MapLibre GL JS (already planned in the constitution) is used for the map toggle view.
