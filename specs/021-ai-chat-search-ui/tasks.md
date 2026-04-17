# Tasks: AI Conversational Search UI

**Input**: Design documents from `/specs/021-ai-chat-search-ui/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5, maps to spec.md)
- Exact file paths are included in every description

## Path Conventions

All source paths are under `frontend/src/` (Next.js app within the monorepo).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies and scaffold the directory structure before any component work begins.

- [ ] T001 Install `react-markdown`, `remark-gfm`, and `@tailwindcss/typography` via `pnpm add react-markdown remark-gfm @tailwindcss/typography` in `frontend/`
- [X] T002 [P] Register `@tailwindcss/typography` plugin in `frontend/tailwind.config.ts` (add to `plugins` array)
- [X] T003 [P] Create `frontend/src/components/chat/` and `frontend/src/components/search/` directories
- [X] T004 [P] Add `WHISPER_API_KEY` and `WHISPER_API_URL` entries to `frontend/.env.local.example` with placeholder values and usage comments

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared TypeScript types, Zustand store, and WebSocket hook that every user story depends on. No user story work can begin until this phase is complete.

**⚠️ CRITICAL**: All subsequent phases depend on these artifacts.

- [X] T005 Create all TypeScript interfaces in `frontend/src/types/chat.ts` — `VoiceInputState`, `MessageRole`, `SessionStatus`, `ChipItem`, `CarouselImage`, `CriteriaField`, `MessageAttachment` (discriminated union), `ChatMessage`, `SessionState`, `ChatStore`, `IncomingWSMessage` (discriminated union), `OutgoingWSMessage`, `ChatSessionSummary`, `ListingCard`, `ListingsPage` (from `data-model.md`)
- [X] T006 Implement `chatStore` skeleton in `frontend/src/stores/chatStore.ts` — `create` + `persist` middleware with a custom `sessionStorage` storage adapter; `Map<string, SessionState>` serialised to/from plain object
- [X] T007 Add read/write actions to `chatStore`: `createSession`, `loadSession`, `addMessage`, `startStreaming`, `appendChunk`, `endStreaming`, `setAttachments` in `frontend/src/stores/chatStore.ts`
- [X] T008 Add criteria actions to `chatStore`: `updateCriteria`, `confirmSearch` (transitions status to `'confirmed'`) in `frontend/src/stores/chatStore.ts`
- [X] T009 Implement `useChatWebSocket` hook in `frontend/src/hooks/useChatWebSocket.ts` — WebSocket connect with JWT query param, exponential backoff reconnect (1→2→4→8→30s), 50ms chunk-buffer (`setInterval`), `requestAnimationFrame` wrapper for store dispatches
- [X] T010 Wire all `IncomingWSMessage` type handlers in `useChatWebSocket.ts` — dispatch `session_ready`, `text_chunk`, `stream_end`, `attachments`, `criteria_update`, `error` to corresponding `chatStore` actions

**Checkpoint**: Types, store, and WebSocket hook complete — user story phases can now begin in parallel.

---

## Phase 3: User Story 1 — Home Page Search Entry (Priority: P1) 🎯 MVP

**Goal**: A visitor lands on the home page, sees a prominent centred search input, types a query, and transitions to the chat window.

**Independent Test**: Load `http://localhost:3000/en`, see centred input with localised placeholder; type a query and press Enter — navigates to `/en/chat` with the message in the conversation.

- [X] T011 [US1] Create `TypingIndicator` in `frontend/src/components/chat/TypingIndicator.tsx` — three dots with CSS `@keyframes` bounce animation (staggered 0ms / 150ms / 300ms delays)
- [X] T012 [US1] Implement `ChatInput` in `frontend/src/components/chat/ChatInput.tsx` — `<textarea>` with auto-resize on `onInput` (`scrollHeight`), Enter-to-submit, Shift+Enter for newline, Send `<Button>` with `<Loader2>` spinner when `isStreaming`, mic button placeholder (wired in Phase 4)
- [X] T013 [US1] Add `chat` namespace keys to `frontend/messages/en.json`, `es.json`, and `fr.json` — keys: `placeholder`, `send`, `mic`, `title`, `newConversation`
- [X] T014 [US1] Build home page layout in `frontend/src/app/[locale]/page.tsx` — full-viewport centred flex column, `<ChatInput>` as hero element, `useTranslations('chat')` for localised placeholder
- [X] T015 [US1] Create chat page shell in `frontend/src/app/[locale]/chat/page.tsx` — minimal layout to receive navigation from the home page (placeholder for `<ChatWindow>` added in Phase 5)
- [X] T016 [US1] Wire `ChatInput` submit in `frontend/src/app/[locale]/page.tsx` — calls `chatStore.createSession()`, `chatStore.addMessage()`, sends `chat_message` over WS, then `router.push('/[locale]/chat')`

**Checkpoint**: Home page renders, query submission navigates to chat page — User Story 1 independently testable.

---

## Phase 4: User Story 2 — Voice Input (Priority: P1)

**Goal**: User clicks the mic button, speaks, and their transcription appears in the input field within 500ms of recognition ending. Whisper fallback activates automatically on unsupported browsers.

**Independent Test**: In Chrome, click mic, speak "three bedroom flat in Madrid", wait 2s — text appears in `ChatInput`. In Firefox, same flow routes through Whisper proxy.

- [X] T017 [P] [US2] Implement `useVoiceInput` hook in `frontend/src/hooks/useVoiceInput.ts` — runtime detection of `window.SpeechRecognition || window.webkitSpeechRecognition`; state machine (`idle→listening→processing→idle|error`); `recognition.continuous = false`, `recognition.interimResults = true`, `recognition.lang = locale`; 2s silence `setTimeout` reset on each `onresult`; returns `{ state, transcript, interimTranscript, start, stop, isSupported }`
- [X] T018 [P] [US2] Create Whisper proxy route handler in `frontend/src/app/api/whisper-proxy/route.ts` — accepts `multipart/form-data` audio blob, forwards to `WHISPER_API_URL` with `WHISPER_API_KEY` (server-side only), returns `{ text: string }`
- [X] T019 [US2] Implement `VoiceInput` component in `frontend/src/components/chat/VoiceInput.tsx` — `listening` state shows `animate-pulse` mic icon; `processing` state shows spinner; Web Audio `AnalyserNode` amplitude waveform bars; Whisper path uses `MediaRecorder` → blob → `fetch('/api/whisper-proxy')`; calls `onTranscript(transcript)` on completion
- [X] T020 [US2] Integrate `VoiceInput` into `ChatInput` mic button in `frontend/src/components/chat/ChatInput.tsx` — `onTranscript` callback sets textarea value; hide mic button entirely when `!isSupported && !whisperAvailable`
- [X] T021 [US2] Add microphone permission denial UI in `VoiceInput` — friendly `<Alert>` explaining how to grant permission when `state === 'error'` due to `NotAllowedError`

**Checkpoint**: Voice input works in Chrome/Edge/Safari (Web Speech API) and Firefox (Whisper fallback) — User Story 2 independently testable.

---

## Phase 5: User Story 3 — Streaming Chat Conversation (Priority: P1)

**Goal**: Full chat window with token-by-token streaming, chips, image carousel, criteria card, and auto-scroll.

**Independent Test**: Send a message via `ChatInput`, observe token-by-token rendering in `MessageBubble`; tap a chip — it sends a new user message; interact with image carousel Like/Not buttons; edit a criteria field inline; confirm criteria — triggers search status transition.

- [X] T022 [P] [US3] Implement `MessageBubble` in `frontend/src/components/chat/MessageBubble.tsx` — user: `justify-end`, brand-colour bg, plain text; assistant: `justify-start`, gray bg, `<ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-sm dark:prose-invert">`; renders `<AttachmentRenderer>` after text content
- [X] T023 [P] [US3] Implement `ChipSelector` in `frontend/src/components/chat/ChipSelector.tsx` — `chips.map` to shadcn `<Button variant="outline" size="sm">`; `onClick` calls `useChatWebSocket().send({ type: 'chat_message', sessionId, content: chip.label })`
- [X] T024 [P] [US3] Implement `ImageCarousel` in `frontend/src/components/chat/ImageCarousel.tsx` — container `overflow-x-auto snap-x snap-mandatory flex gap-3`; each card `snap-start min-w-[280px]` with `next/image`, price, location; "Like this" / "Not this" buttons send `image_feedback` WS event
- [X] T025 [US3] Implement `CriteriaSummaryCard` in `frontend/src/components/chat/CriteriaSummaryCard.tsx` — shadcn `<Card>` with 2-col grid; each field: label + value + pencil icon; click pencil → inline `<input>` or `<select>` based on `CriteriaField.inputType`; on blur/Enter dispatches `chatStore.updateCriteria`; "Search + Alert" `<Button>` calls `chatStore.confirmSearch` + sends `criteria_confirm` WS event
- [X] T026 [US3] Create `AttachmentRenderer` helper function in `frontend/src/components/chat/MessageBubble.tsx` — switch on `attachment.type` → renders `<ChipSelector>`, `<ImageCarousel>`, `<CriteriaSummaryCard>`, or null
- [X] T027 [US3] Implement `ChatWindow` in `frontend/src/components/chat/ChatWindow.tsx` — scrollable `<div ref={scrollRef}>` containing `messages.map(<MessageBubble>)`; `useEffect` on `messages.length` scrolls `scrollRef.current.scrollTop = scrollHeight`; renders `<TypingIndicator>` when `session.streamingMessageId && lastMessage.role === 'assistant'`; `<ChatInput>` pinned at bottom; calls `useChatWebSocket` on mount
- [X] T028 [US3] Build full chat page layout in `frontend/src/app/[locale]/chat/page.tsx` — `<ChatWindow>` in main area; `<ConversationSidebar>` slot (wired in Phase 7); `<SearchResults>` conditional slot (wired in Phase 6)

**Checkpoint**: Full conversational loop works — streaming, chips, carousel, criteria card all functional — User Story 3 independently testable.

---

## Phase 6: User Story 4 — Inline Search Results (Priority: P2)

**Goal**: After criteria confirmation, listing cards appear within 2s. User can toggle map, sort results, and scroll infinitely.

**Independent Test**: Confirm a criteria card — within 2s listing cards with photo, price, deal score badge appear; scroll to bottom to load more; toggle map — pins appear; change sort order — list re-orders.

- [X] T029 [P] [US4] Implement `ListingCard` in `frontend/src/components/search/ListingCard.tsx` — `next/image` `width=320 height=200 object-cover`; price formatted with `Intl.NumberFormat(locale, { style: 'currency', currency })`; deal score badge: `≥70 bg-green-500`, `40–69 bg-amber-500`, `<40 bg-red-500`; bedrooms, areaSqm, location fields
- [X] T030 [P] [US4] Implement `MapView` in `frontend/src/components/search/MapView.tsx` — MapLibre GL JS `new Map({ container: ref.current })`; `useEffect` on `listings` updates GeoJSON source; marker click shows `<ListingCard>` popup; exported with `next/dynamic({ ssr: false })` to avoid SSR issues
- [X] T031 [US4] Implement `SearchResults` in `frontend/src/components/search/SearchResults.tsx` — `useInfiniteQuery({ queryKey: ['listings', criteria], queryFn, getNextPageParam: r => r.nextCursor })`; `IntersectionObserver` on sentinel `<div>` calls `fetchNextPage()`; local `sortBy` state invalidates query on change; local `showMap` boolean toggles `<MapView>` vs card grid
- [X] T032 [US4] Add sort controls bar to `SearchResults` — four `<Button>` variants for `price_asc`, `price_desc`, `deal_score_desc`, `date_desc`; active sort highlighted with `variant="default"`, others `variant="ghost"`
- [X] T033 [US4] Add empty-state to `SearchResults` in `frontend/src/components/search/SearchResults.tsx` — illustration + "No listings found" text + a `<ChipSelector>` with a single "Refine your search" chip that transitions session back to `'searching'`
- [X] T034 [US4] Conditionally mount `<SearchResults criteria={session.criteria}>` in `frontend/src/app/[locale]/chat/page.tsx` when `session.status === 'confirmed' || session.status === 'complete'`

**Checkpoint**: Full search result display works with map, sort, and infinite scroll — User Story 4 independently testable.

---

## Phase 7: User Story 5 — Conversation Persistence and History (Priority: P2)

**Goal**: Active conversation survives page navigation. Sidebar lists all recent sessions with snippets; clicking one restores the conversation.

**Independent Test**: Start a conversation, navigate away, return — full history restored from sessionStorage. Open sidebar — recent sessions listed with snippets and timestamps; click one — that conversation loads.

- [X] T035 [US5] Implement `ConversationSidebar` in `frontend/src/components/chat/ConversationSidebar.tsx` — `useQuery({ queryKey: ['chat-sessions'], queryFn: fetchSessions, staleTime: 30_000 })`; each item: snippet (100-char truncation), `formatDistanceToNow` relative timestamp, shadcn `<Badge>` for `status`; click dispatches `chatStore.loadSession(sessionId)` + navigates to `/[locale]/chat`
- [X] T036 [US5] Add mobile slide-over to `ConversationSidebar` — wrap in shadcn `<Sheet>` with `side="left"` for viewports < 768px; accept `open` / `onOpenChange` props
- [X] T037 [US5] Add hamburger `<Button>` to `ChatWindow` header in `frontend/src/components/chat/ChatWindow.tsx` — visible only on mobile; toggles `ConversationSidebar` Sheet open state
- [X] T038 [US5] Wire sidebar into chat page in `frontend/src/app/[locale]/chat/page.tsx` — desktop: persistent sidebar column; mobile: `<Sheet>` controlled by hamburger button
- [X] T039 [US5] Handle unauthenticated sidebar state in `ConversationSidebar` — when no session exists, render sign-in prompt with `<Button>` linking to `/[locale]/login`; skip `GET /api/chat/sessions` fetch for unauthenticated users
- [ ] T040 [US5] Verify sessionStorage persistence: manually navigate from `/en/chat` to `/en` and back — confirm `chatStore.sessions` and `chatStore.activeSessionId` are restored (test per `quickstart.md` checklist)

**Checkpoint**: Conversation persists across navigation; sidebar shows and switches conversations — User Story 5 independently testable.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility, performance, and final quality pass across all user stories.

- [X] T041 [P] Add `aria-label` attributes to all interactive elements: `ChatInput` textarea, mic button, send button, each chip `<Button>`, carousel "Like this"/"Not this" buttons, criteria edit pencil icons in `frontend/src/components/chat/`
- [X] T042 [P] Add focus trap and keyboard `Escape`-to-close for `CriteriaSummaryCard` inline edit fields in `frontend/src/components/chat/CriteriaSummaryCard.tsx`
- [X] T043 [P] Wrap `<ChatWindow>` and `<SearchResults>` in React error boundaries in `frontend/src/app/[locale]/chat/page.tsx` to prevent full-page crashes on WS or API errors
- [ ] T044 [P] Verify `MapView` loads via `next/dynamic` with `ssr: false` and confirm MapLibre GL JS is excluded from the server bundle in `frontend/src/components/search/MapView.tsx`
- [ ] T045 Run the full pre-PR checklist from `quickstart.md` — voice in Chrome/Edge/Safari, Whisper fallback in Firefox, streaming fps, chips WS message, carousel snap on mobile, criteria inline edit, listings within 2s, map toggle, navigation persistence, sidebar snippets
- [X] T046 [P] Final i18n completeness pass — ensure all keys in the `chat` namespace are present and non-empty in `frontend/messages/en.json`, `es.json`, and `fr.json`
- [ ] T047 [P] Verify Lighthouse accessibility score > 85 on home page (`/en`) and chat page (`/en/chat`) using production build (`pnpm build && pnpm start`)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
  └─▶ Phase 2 (Foundational) — BLOCKS all user story phases
        ├─▶ Phase 3 (US1 — Home Page)   ─▶ Phase 4 (US2 — Voice)     ─▶ Phase 8 (Polish)
        └─▶ Phase 5 (US3 — Chat Window) ─▶ Phase 6 (US4 — Results)   ─▶ Phase 8 (Polish)
                                          └─▶ Phase 7 (US5 — History) ─▶ Phase 8 (Polish)
```

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2. No dependency on other user stories.
- **US2 (P1)**: Starts after Phase 2. Integrates into `ChatInput` from US1 (T020 depends on T012 being done).
- **US3 (P1)**: Starts after Phase 2. Builds on `ChatInput` from US1 and `useChatWebSocket` from Phase 2.
- **US4 (P2)**: Starts after US3's `CriteriaSummaryCard` (T025) and `confirmSearch` store action (T008) are complete.
- **US5 (P2)**: Starts after Phase 2. `ConversationSidebar` (T035–T040) can be built in parallel with US3/US4.

### Within Each User Story

- Types and store actions before hooks
- Hooks before components that consume them
- Leaf components (TypingIndicator, ChipSelector, ImageCarousel) before container components (MessageBubble, ChatWindow)
- All components before page assembly

---

## Parallel Opportunities

### Phase 2 — Foundational

```
Parallel: T005 (types) — standalone, no deps
Then parallel: T006 + T009 (store skeleton, WS hook skeleton) — both depend only on T005
Then sequential: T007 → T008 (store actions, in order)
Then: T010 (WS handlers, depends on T009 + T007 + T008)
```

### Phase 5 — US3 Chat Window

```
Parallel: T022 (MessageBubble) + T023 (ChipSelector) + T024 (ImageCarousel)
  — all are leaf components with no inter-dependency
Then: T025 (CriteriaSummaryCard) — independent leaf
Then: T026 (AttachmentRenderer) — depends on T022–T025 types
Then: T027 (ChatWindow) — depends on T022, T026, T011 (TypingIndicator from US1)
Then: T028 (chat page) — depends on T027
```

### Phase 6 — US4 Search Results

```
Parallel: T029 (ListingCard) + T030 (MapView)
Then: T031 (SearchResults) — depends on T029 + T030
Then: T032, T033, T034 — sequential enhancements to SearchResults
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 — all P1 stories)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: US1 Home Page → **validate independently**
4. Complete Phase 4: US2 Voice Input → **validate independently**
5. Complete Phase 5: US3 Chat Window → **validate independently**
6. **STOP and DEMO**: All P1 stories functional — full conversational loop works

### Full Delivery

7. Complete Phase 6: US4 Search Results → validate
8. Complete Phase 7: US5 Persistence + History → validate
9. Complete Phase 8: Polish

### Parallel Team Strategy

With two developers after Phase 2 completes:

- **Dev A**: Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (US4)
- **Dev B**: Phase 7 (US5 — ConversationSidebar) in parallel with Dev A's Phase 5/6

---

## Summary

| Phase | Stories | Tasks | Parallel Tasks |
|-------|---------|-------|---------------|
| Phase 1: Setup | — | T001–T004 | T002, T003, T004 |
| Phase 2: Foundational | — | T005–T010 | T005, T006, T009 |
| Phase 3: US1 Home Page | US1 (P1) | T011–T016 | T012, T013 |
| Phase 4: US2 Voice Input | US2 (P1) | T017–T021 | T017, T018 |
| Phase 5: US3 Chat Window | US3 (P1) | T022–T028 | T022, T023, T024 |
| Phase 6: US4 Search Results | US4 (P2) | T029–T034 | T029, T030 |
| Phase 7: US5 Persistence | US5 (P2) | T035–T040 | — |
| Phase 8: Polish | — | T041–T047 | T041, T042, T043, T044, T046, T047 |
| **Total** | **5 stories** | **47 tasks** | **18 parallelizable** |

---

## Notes

- `[P]` tasks touch different files and have no incomplete-task dependencies — safe to run concurrently
- Each user story phase ends with an explicit **Checkpoint** that can be validated independently before moving on
- No test tasks are included (not requested in spec); add them per story if TDD approach is preferred
- Commit after each checkpoint at minimum; commits after individual tasks are recommended
- The Whisper proxy (T018) keeps `WHISPER_API_KEY` strictly server-side — never expose in client bundles
- MapLibre GL JS (~600KB) is dynamic-imported (T030/T044) to keep initial bundle lean
