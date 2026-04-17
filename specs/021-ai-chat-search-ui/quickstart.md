# Quickstart: AI Conversational Search UI

**Branch**: `021-ai-chat-search-ui` | **Date**: 2026-04-17

## Prerequisites

- Node.js 22 + pnpm (or npm)
- The existing `020-nextjs-frontend-foundation` is implemented (auth, i18n, WebSocket client base, TanStack Query setup)
- Services `018-ai-chat-service` and `019-ws-chat-realtime` running locally (or pointed at staging)

## Install New Dependencies

```bash
cd frontend
pnpm add react-markdown remark-gfm @tailwindcss/typography
```

MapLibre GL JS is already installed from `020-nextjs-frontend-foundation`.

## Environment Variables

Add to `frontend/.env.local`:

```env
# WebSocket endpoint (already set in 020)
NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws/chat

# Whisper API fallback (only needed if Web Speech API unavailable in dev)
WHISPER_API_KEY=sk-...
WHISPER_API_URL=https://api.openai.com/v1/audio/transcriptions
```

## File Structure to Create

```text
frontend/src/
├── components/chat/
│   ├── ChatInput.tsx
│   ├── VoiceInput.tsx
│   ├── MessageBubble.tsx
│   ├── ChipSelector.tsx
│   ├── ImageCarousel.tsx
│   ├── CriteriaSummaryCard.tsx
│   ├── TypingIndicator.tsx
│   ├── ChatWindow.tsx
│   └── ConversationSidebar.tsx
├── components/search/
│   ├── SearchResults.tsx
│   ├── ListingCard.tsx
│   └── MapView.tsx
├── stores/
│   └── chatStore.ts
├── types/
│   └── chat.ts
├── hooks/
│   ├── useVoiceInput.ts
│   └── useChatWebSocket.ts
└── app/[locale]/
    ├── page.tsx           (home page — search entry point)
    └── chat/
        └── page.tsx       (chat window + results)
```

## Run Dev Server

```bash
cd frontend
pnpm dev
```

Navigate to `http://localhost:3000/en` — the home page should show the centred search input.

## Testing Voice Input

1. Open Chrome DevTools → Application → Permissions → Microphone → Allow
2. Click the mic button and speak: "3-bedroom flat in Madrid under 400k"
3. Wait 2s — transcription should appear in the input field

To test Whisper fallback, open Firefox (no Web Speech API support); the mic should silently switch to `MediaRecorder` capture.

## Key Integration Points

| Integration | How |
|-------------|-----|
| WebSocket | `useChatWebSocket` hook connects on mount; dispatches to `chatStore` |
| Auth JWT | Passed as query param to WebSocket URL from NextAuth session |
| Listings API | TanStack `useInfiniteQuery` on `confirmSearch` status change |
| i18n | `useTranslations('chat')` from `next-intl`; add keys to `messages/en.json` etc. |

## Checklist Before PR

- [ ] Voice input tested in Chrome, Edge, Safari (macOS + iOS)
- [ ] Whisper fallback tested in Firefox
- [ ] Streaming renders at ≥ 30fps (check with Chrome Performance tab)
- [ ] Chips send correct WebSocket message
- [ ] Image carousel snap behaviour on mobile (device emulation)
- [ ] Criteria card inline edit round-trip
- [ ] Listing cards appear within 2s of confirmation
- [ ] Map toggle shows pins
- [ ] Navigate away and back — conversation persists
- [ ] Sidebar shows recent sessions with correct snippets
