# Feature: AI Chat Interface

## /plan prompt

```
Implement with these technical decisions:

## Components (frontend/src/components/chat/)
- ChatInput.tsx: textarea with auto-resize, Shift+Enter for newline, Enter to send. Mic button triggers VoiceInput. Send button with loading state.
- VoiceInput.tsx: window.SpeechRecognition (webkit prefix for Safari). States: idle, listening, processing. Interim results shown in real-time. On end → set transcription in input.
- MessageBubble.tsx: user (right-aligned, brand color) and assistant (left-aligned, gray). Support markdown rendering in assistant messages (react-markdown).
- ChipSelector.tsx: horizontal flex wrap of shadcn Button variants. On click → send as chat_message via WebSocket.
- ImageCarousel.tsx: horizontal scroll container with snap points. Each card: image + "Like this" / "Not this" buttons. On action → send image_feedback via WebSocket.
- CriteriaSummaryCard.tsx: shadcn Card with grid of criteria fields. Each field: label + value + edit icon. Edit opens inline input or select. "Search + Alert" primary CTA button.
- TypingIndicator.tsx: three animated dots (CSS keyframes).
- ChatWindow.tsx: scrollable message list + ChatInput at bottom. Uses chatStore (Zustand) for message state. On mount: connect WebSocket, load conversation from chatStore or create new.
- ConversationSidebar.tsx: list of recent conversations from API. Each item: snippet, date, status badge. Click loads conversation.

## State Management (stores/chatStore.ts)
- Zustand store: { sessions: Map<sessionId, { messages, criteria, status }>, activeSession, createSession(), addMessage(), updateCriteria(), confirmSearch() }
- WebSocket messages update store directly
- Persistence: sessionStorage for active conversation (survives navigation)

## Streaming
- WebSocket text_chunk messages appended to last assistant message character by character
- Use requestAnimationFrame for smooth rendering at high token rates
- Buffer chunks and flush every 50ms to avoid excessive re-renders
```
