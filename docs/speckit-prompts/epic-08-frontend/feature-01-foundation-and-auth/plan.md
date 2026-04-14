# Feature: Frontend Foundation & Authentication

## /plan prompt

```
Implement with these technical decisions:

## Stack
- Next.js 15 (App Router, RSC), TypeScript 5.5, Tailwind CSS 4, shadcn/ui
- next-intl for i18n with middleware-based locale detection
- next-auth v5 for auth (JWT strategy, credentials + Google providers)
- @tanstack/react-query v5 for server state
- zustand for client state (chat, notifications, UI preferences)
- openapi-typescript-codegen for API types from OpenAPI spec

## Project Structure (frontend/src/)
- app/[locale]/layout.tsx — root layout with providers (QueryClient, Auth, i18n, Zustand)
- app/[locale]/page.tsx — home page with AI chat input
- app/[locale]/(auth)/login/page.tsx, register/page.tsx
- app/[locale]/(protected)/dashboard/, search/, listing/[id]/, zones/, alerts/, portfolio/, admin/
- components/ — reusable UI components (chat/, map/, listings/, dashboard/, layout/)
- lib/api.ts — generated API client, lib/ws.ts — WebSocket manager, lib/auth.ts — auth helpers
- messages/ — i18n JSON files per locale
- stores/ — Zustand stores (chatStore, notificationStore, uiStore)

## WebSocket Manager (lib/ws.ts)
- Class WebSocketManager with: connect(jwt), disconnect(), send(message), onMessage(handler)
- Auto-reconnect: exponential backoff (1s, 2s, 4s, 8s, max 30s)
- Message routing: parse type → dispatch to appropriate Zustand store action
- Heartbeat: send ping every 25s to keep connection alive
```
