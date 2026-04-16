# Feature: AI Chat Interface

## /specify prompt

```
Build the AI conversational search UI — the primary entry point of the application.

## What
1. Home page: centered large text input with placeholder "What are you looking for?" (localized). Microphone button for voice input. Prominent, search-engine-like design.
2. Voice Input component: uses Web Speech API for browser-native speech-to-text. Visual feedback (pulsing mic, waveform). Auto-stop on 2s silence. Transcription shown in input before sending. Fallback to Whisper API for unsupported browsers.
3. Chat message components: MessageBubble (user/assistant variants), ChipSelector (tappable quick-reply buttons), ImageCarousel (horizontal scrolling cards with "yes, like this"/"no, not this" actions), CriteriaSummaryCard (editable criteria display), TypingIndicator (streaming dots animation).
4. Chat window: full conversation history, auto-scroll to bottom, streaming text (typewriter effect), inline chips/images/summary. Conversation list sidebar with recent conversations and preview snippets.
5. Search results inline: after criteria confirmation, display matching listings below chat as cards with photo, price, deal score badge. Map toggle. Infinite scroll. Sort controls.

## Acceptance Criteria
- AI chat input is the first thing users see on the home page
- Voice input works in Chrome, Edge, Safari in Spanish, English, French
- Streaming text renders token-by-token smoothly
- Chips send selection as user message on tap
- Image carousel swipeable on mobile, clickable on desktop
- Summary card fields editable inline
- Search results appear within 2s of confirmation
- Full conversation persists across page navigations
- Conversation list shows recent chats with snippets
```
