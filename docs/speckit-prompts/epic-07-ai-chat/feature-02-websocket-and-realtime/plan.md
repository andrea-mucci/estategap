# Feature: WebSocket Server & Real-Time

## /plan prompt

```
Implement with these technical decisions:

## Service (services/ws-server/)
- Go, gorilla/websocket or nhooyr.io/websocket
- Port 8081, separate from API gateway

## Connection Lifecycle
- Upgrade: verify JWT from query param or cookie. Extract user_id, tier. Register connection in hub.
- Hub: concurrent map[user_id][]Connection. Protected by sync.RWMutex.
- Ping/pong: server sends ping every 30s. If no pong in 10s → close connection.
- Idle timeout: 30min no messages → close.
- Graceful shutdown: on SIGTERM, send close frame to all connections, wait 5s, force close.

## Chat Protocol
- JSON envelope: {"type": "chat_message", "session_id": "abc", "payload": {...}}
- Types inbound: chat_message, image_feedback, criteria_confirm
- Types outbound: text_chunk, chips, image_carousel, criteria_summary, search_results, error, deal_alert
- On chat_message: open gRPC stream to ai-chat-service. For each streamed response chunk → send as text_chunk WS message. On stream end → send final criteria state.

## Real-Time Notifications
- NATS consumer on alerts.notifications.> with queue group
- On notification: check if user_id is in hub. If connected → send deal_alert WS message.
- Message format: {type: "deal_alert", payload: {listing_id, address, price, deal_score, photo_url, analysis_url}}

## Scaling
- Multiple ws-server pods. Each pod handles its own connections.
- NATS fanout ensures all pods receive all notifications. Only the pod with the user connected delivers.
- Metrics: ws_connections_active, ws_messages_sent_total, ws_messages_received_total
```
