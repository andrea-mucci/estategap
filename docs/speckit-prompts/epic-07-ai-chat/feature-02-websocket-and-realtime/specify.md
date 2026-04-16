# Feature: WebSocket Server & Real-Time

## /specify prompt

```
Build the Go WebSocket server that handles AI chat streaming and real-time deal notifications.

## What
1. WebSocket endpoint /ws/chat: authenticates user via JWT in initial handshake. Bidirectional JSON protocol with message types: chat_message (user→server), text_chunk (server→user, streamed tokens), chips (server→user, quick-reply options), image_carousel (server→user, visual references), criteria_summary (server→user, final criteria card), search_results (server→user, matching listings), error. Forwards user messages to ai-chat-service via gRPC bidirectional streaming. Streams LLM response tokens back to client in real-time.

2. Real-time deal notifications: subscribes to alerts.notifications NATS stream filtered by connected user IDs. Pushes deal alerts to connected users via their WebSocket connection without needing email/Telegram.

3. Connection management: ping/pong keepalive (30s interval), auto-disconnect after 30min idle, graceful shutdown draining connections, per-pod connection limit (10k).

## Acceptance Criteria
- WebSocket connects with JWT. Invalid JWT rejected.
- User message → streamed response tokens appear in < 500ms first-token latency
- Image carousel and chips message types work correctly
- Real-time deal alert pushed within 5s of scoring
- Connection survives 30min idle (ping/pong)
- 1000 concurrent connections per pod without degradation
- Graceful reconnection: client reconnects and resumes conversation
```
