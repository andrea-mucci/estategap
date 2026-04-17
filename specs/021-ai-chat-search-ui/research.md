# Research: AI Conversational Search UI

**Branch**: `021-ai-chat-search-ui` | **Date**: 2026-04-17

## Summary

All technical unknowns resolved. This document records decisions made for the implementation plan.

---

## Decision 1: Streaming Text Rendering Strategy

**Decision**: Buffer incoming `text_chunk` WebSocket messages in a ref-based queue; flush to React state every 50ms via `setInterval` and schedule DOM updates with `requestAnimationFrame`.

**Rationale**: React state updates are batched by the scheduler, but calling `setState` on every token (up to ~50/s) causes excessive reconciliation. A 50ms flush interval amortises the overhead while keeping perceived latency imperceptible to users. `requestAnimationFrame` ensures updates happen before the next paint frame, preventing dropped frames.

**Alternatives considered**:
- **Immediate setState per token**: Simple but causes 50+ renders/second per active stream, degrading overall UI responsiveness.
- **Debounce only**: Introduces variable delay; large debounce values cause jerky rendering. The fixed-interval approach is more predictable.
- **Web Worker for buffering**: Adds complexity with no meaningful gain for this use case.

---

## Decision 2: Voice Input — Web Speech API + Whisper Fallback

**Decision**: Use `window.SpeechRecognition` (with `window.webkitSpeechRecognition` for Safari). Detect support at runtime. On unsupported browsers, upload audio blob to the Whisper API endpoint via a `MediaRecorder` capture pipeline.

**Rationale**: Web Speech API has native support in Chrome (desktop + Android), Edge, and Safari 14.1+. It provides real-time interim results with zero latency overhead. Whisper is required for Firefox and older browsers.

**Alternatives considered**:
- **Whisper-only**: Eliminates the API inconsistency but removes real-time interim feedback and adds ~1-2s network round-trip latency on every utterance.
- **Third-party SDK (e.g., Deepgram)**: Adds cost and a vendor dependency for functionality already available natively in target browsers.

**Auto-stop implementation**: Set `recognition.continuous = false` and `recognition.interimResults = true`. Use a 2-second silence debounce via `setTimeout`; reset the timer on each `onresult` event. On timeout call `recognition.stop()`.

---

## Decision 3: Zustand Store Shape for Chat Sessions

**Decision**: Single `chatStore` with a `Map<sessionId, SessionState>` for O(1) session lookup.

```typescript
interface SessionState {
  messages: ChatMessage[];
  criteria: Record<string, string>;
  status: 'searching' | 'confirming' | 'confirmed' | 'complete';
  streamingMessageId: string | null;
}

interface ChatStore {
  sessions: Map<string, SessionState>;
  activeSessionId: string | null;
  createSession: () => string;           // returns new sessionId
  addMessage: (sessionId: string, msg: ChatMessage) => void;
  appendChunk: (sessionId: string, chunk: string) => void;
  updateCriteria: (sessionId: string, patch: Partial<Record<string, string>>) => void;
  confirmSearch: (sessionId: string) => void;
  loadSession: (sessionId: string) => void;
}
```

**Rationale**: Map allows constant-time lookups when switching between conversations in the sidebar. Flat structure avoids deeply nested Zustand selectors that cause unnecessary re-renders.

**Persistence**: `persist` middleware with a custom `sessionStorage` storage adapter. Only `sessions` and `activeSessionId` are persisted; WebSocket state is not.

**Alternatives considered**:
- **Array of sessions**: Requires `.find()` on every message append during streaming — O(n) per chunk.
- **Server-side session fetch on load**: Adds a round-trip before the user can see the conversation; sessionStorage gives instant restore.

---

## Decision 4: Conversation Sidebar Data Source

**Decision**: Fetch recent conversations from the REST API (`GET /api/chat/sessions`) via TanStack Query with a 30-second stale time. The sidebar does NOT connect a separate WebSocket.

**Rationale**: The sidebar shows a list snapshot; real-time freshness is not required. TanStack Query handles caching, background refetch on window focus, and error states natively.

**Alternatives considered**:
- **Derive from chatStore only**: Would miss conversations started in other tabs or devices.
- **WebSocket push for sidebar updates**: Over-engineering; a stale-while-revalidate REST call is sufficient.

---

## Decision 5: ImageCarousel Interaction Model

**Decision**: Use CSS `scroll-snap-type: x mandatory` on the scroll container for native swipe snap on mobile. Each card is `scroll-snap-align: start`. "Like this" / "Not this" buttons send a `{ type: "image_feedback", payload: { listingId, action: "like" | "dislike" } }` WebSocket message.

**Rationale**: CSS scroll snap is supported in all target browsers, requires no JS gesture library, and preserves native momentum scrolling on iOS. Zero bundle size impact.

**Alternatives considered**:
- **Swiper.js**: Full-featured but ~40KB gzipped; unnecessary given native scroll snap sufficiency.
- **Embla Carousel**: Lighter (~7KB) but still a dependency; CSS solution preferred.

---

## Decision 6: Inline Listing Results — Data Fetching

**Decision**: On `confirmSearch` action, the store status transitions to `'confirmed'`. A `SearchResults` component mounts conditionally below `ChatWindow`; it fires `GET /api/listings/search` via TanStack Query infinite query using the confirmed criteria from the store.

**Rationale**: Decouples search result fetching from the chat message flow. Infinite query with `getNextPageParam` handles cursor-based pagination cleanly. The 2-second result latency requirement is met because the request fires immediately on status transition.

**Alternatives considered**:
- **Listings pushed over WebSocket**: Avoids a second HTTP call but mixes the streaming text protocol with large listing payloads, complicating the message handler.
- **Server-side pagination with RSC**: Requires server round-trips for each page; client-side infinite query provides instant skeleton-to-content transitions.

---

## Decision 7: Map Toggle Implementation

**Decision**: Use MapLibre GL JS (already mandated by the constitution). A `MapView` component renders conditionally when `mapVisible: true` in local component state. Listing coordinates are passed as GeoJSON FeatureCollection. Toggle state is local (not in chatStore).

**Rationale**: MapLibre is already the constitution-mandated map library. The toggle is ephemeral UI state; it does not need to survive navigation or be shared across components.

**Alternatives considered**:
- **Leaflet**: Not in the constitution stack; introduces inconsistency.
- **Google Maps**: Paid API; violates the open-source preference in the constitution.

---

## Decision 8: Markdown Rendering in Assistant Messages

**Decision**: Use `react-markdown` with `remark-gfm` for GitHub Flavoured Markdown. Apply Tailwind `prose` class from `@tailwindcss/typography` for consistent styling.

**Rationale**: The AI assistant frequently returns bullet lists, bold text, and tables in property descriptions. `react-markdown` is the standard React solution; `remark-gfm` adds table and task-list support.

**Alternatives considered**:
- **dangerouslySetInnerHTML + marked**: XSS risk; rejected on security grounds.
- **Custom markdown parser**: Unnecessary complexity.

---

## Resolution Summary

| # | Question | Resolution |
|---|----------|------------|
| 1 | Streaming render strategy | 50ms buffer + rAF flush |
| 2 | Voice API choice | Web Speech API + Whisper fallback |
| 3 | Store shape | Map<sessionId, SessionState> with persist middleware |
| 4 | Sidebar data | REST fetch via TanStack Query |
| 5 | Carousel gesture | CSS scroll snap (native) |
| 6 | Listings fetch | TanStack infinite query on confirmSearch |
| 7 | Map library | MapLibre GL JS |
| 8 | Markdown rendering | react-markdown + remark-gfm + prose |
