# Data Model: AI Conversational Search UI

**Branch**: `021-ai-chat-search-ui` | **Date**: 2026-04-17

All types live in `frontend/src/types/chat.ts` unless noted.

---

## Core Types

### VoiceInputState

```typescript
type VoiceInputState = 'idle' | 'listening' | 'processing' | 'error';
```

### MessageRole

```typescript
type MessageRole = 'user' | 'assistant';
```

### SessionStatus

```typescript
type SessionStatus = 'searching' | 'confirming' | 'confirmed' | 'complete';
```

### MessageAttachment

Discriminated union — each variant maps to a rendered component.

```typescript
type MessageAttachment =
  | { type: 'chips';    chips: ChipItem[] }
  | { type: 'carousel'; images: CarouselImage[] }
  | { type: 'criteria'; fields: CriteriaField[] }
  | { type: 'listings'; count: number };   // triggers SearchResults component

interface ChipItem {
  id: string;
  label: string;
}

interface CarouselImage {
  listingId: string;
  src: string;
  alt: string;
  price: string;
  location: string;
}

interface CriteriaField {
  key: string;
  label: string;
  value: string;
  inputType: 'text' | 'number' | 'select';
  options?: string[];   // for inputType === 'select'
}
```

### ChatMessage

```typescript
interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;                        // accumulated text (grows during streaming)
  attachments: MessageAttachment[];
  timestamp: number;                      // unix ms
  isStreaming: boolean;                   // true while text_chunk messages are arriving
}
```

### SessionState

```typescript
interface SessionState {
  messages: ChatMessage[];
  criteria: Record<string, string>;       // confirmed key-value pairs
  status: SessionStatus;
  streamingMessageId: string | null;      // id of the message currently being streamed
  snippetText: string;                    // first 100 chars of last assistant message
  updatedAt: number;                      // unix ms — used for sidebar ordering
}
```

### ChatStore (Zustand)

```typescript
interface ChatStore {
  sessions: Map<string, SessionState>;
  activeSessionId: string | null;

  // actions
  createSession: () => string;
  loadSession: (sessionId: string) => void;
  addMessage: (sessionId: string, message: ChatMessage) => void;
  startStreaming: (sessionId: string, messageId: string) => void;
  appendChunk: (sessionId: string, messageId: string, chunk: string) => void;
  endStreaming: (sessionId: string, messageId: string) => void;
  setAttachments: (sessionId: string, messageId: string, attachments: MessageAttachment[]) => void;
  updateCriteria: (sessionId: string, patch: Partial<Record<string, string>>) => void;
  confirmSearch: (sessionId: string) => void;
}
```

---

## API Response Types

### ChatSessionSummary (Sidebar)

```typescript
// GET /api/chat/sessions
interface ChatSessionSummary {
  sessionId: string;
  snippetText: string;
  updatedAt: string;    // ISO 8601
  status: SessionStatus;
}
```

### ListingCard (Search Results)

```typescript
// GET /api/listings/search (paginated)
interface ListingCard {
  listingId: string;
  title: string;
  price: number;
  currency: string;
  dealScore: number;      // 0–100
  photos: string[];       // URLs
  bedrooms?: number;
  areaSqm?: number;
  location: string;
  latitude: number;
  longitude: number;
}

interface ListingsPage {
  items: ListingCard[];
  nextCursor: string | null;
  total: number;
}
```

---

## WebSocket Message Protocol

Incoming messages from `019-ws-chat-realtime`:

```typescript
type IncomingWSMessage =
  | { type: 'text_chunk';       sessionId: string; messageId: string; chunk: string }
  | { type: 'stream_end';       sessionId: string; messageId: string }
  | { type: 'attachments';      sessionId: string; messageId: string; attachments: MessageAttachment[] }
  | { type: 'criteria_update';  sessionId: string; criteria: Record<string, string> }
  | { type: 'session_ready';    sessionId: string }
  | { type: 'error';            code: string; message: string };

type OutgoingWSMessage =
  | { type: 'chat_message';     sessionId: string; content: string }
  | { type: 'image_feedback';   sessionId: string; listingId: string; action: 'like' | 'dislike' }
  | { type: 'criteria_confirm'; sessionId: string; criteria: Record<string, string> };
```

---

## State Transitions

```text
SessionStatus transitions:
  searching  ──[assistant sends criteria attachment]──▶  confirming
  confirming ──[user sends criteria_confirm]───────────▶  confirmed
  confirmed  ──[listings_ready received]────────────────▶  complete
  Any        ──[user sends new chat_message]────────────▶  searching
```

---

## Validation Rules

| Field | Rule |
|-------|------|
| `ChatMessage.content` | Non-empty string after trim (outgoing only) |
| `CriteriaField.value` | Non-empty; validated per `inputType` (number fields must be numeric) |
| `ListingCard.dealScore` | Integer 0–100 |
| `VoiceInputState` | Transition: idle → listening → processing → idle (or error at any step) |
