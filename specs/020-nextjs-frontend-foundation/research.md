# Research: Next.js Frontend Foundation

**Date**: 2026-04-17 | **Branch**: `020-nextjs-frontend-foundation`

## 1. Next.js 15 App Router + next-intl

**Decision**: Use next-intl `^3.x` with the `createNextIntlPlugin` wrapper in `next.config.ts` and a `middleware.ts` that calls `createMiddleware` to detect/redirect locale from the `Accept-Language` header and cookie.

**Rationale**: next-intl is the de-facto i18n library for the Next.js App Router. Its middleware-based locale detection avoids manual redirect logic and supports 10 locales with minimal boilerplate.

**Key implementation details**:
- `src/i18n/routing.ts` defines `locales` array and `defaultLocale: "en"`.
- `src/i18n/request.ts` exports `getRequestConfig` that loads the JSON message file for the active locale.
- All `messages/{locale}.json` files are loaded on the server; the client receives only its locale's strings.
- Language switcher uses `useRouter()` from `next-intl/navigation` and `useLocale()` — no full page reload.
- The `[locale]` path segment is validated by the middleware; unknown locales redirect to `/en`.

**Alternatives considered**:
- `next-i18next`: Does not support RSC/App Router natively.
- Manual `Intl` + URL params: Too much boilerplate; no automatic message loading.

---

## 2. NextAuth v5 (Auth.js)

**Decision**: Use `next-auth@5` (beta) with `CredentialsProvider` and `GoogleProvider`. Session strategy: `jwt`. The `session.user` object is extended to include `subscriptionTier` and `accessToken` (the backend JWT from the API Gateway).

**Rationale**: NextAuth v5 is built for the App Router — it uses Route Handlers, not API Routes, and exposes a typed `auth()` helper for both server components and middleware. The JWT strategy keeps sessions stateless, matching the backend's bearer-token approach.

**Key implementation details**:
- `src/auth.ts` exports `{ auth, handlers, signIn, signOut }`.
- `app/api/auth/[...nextauth]/route.ts` re-exports the handlers.
- `CredentialsProvider.authorize` calls `POST /auth/login` on the API Gateway, receives `{ access_token, refresh_token, expires_in }`, stores the backend JWT in the NextAuth JWT as `accessToken`.
- `GoogleProvider` handles OAuth; on first sign-in, the backend should be called to provision/link the account (handled in the `signIn` callback).
- Middleware chain: `createMiddleware` (next-intl) → `auth` guard for `(protected)` routes.
- `session.user.subscriptionTier` populated from the API Gateway `/users/me` response stored in JWT claims.
- Token refresh: NextAuth `jwt` callback refreshes when `accessToken` is within 60s of expiry.

**Alternatives considered**:
- NextAuth v4: Uses `pages/api/auth` — not compatible with App Router without shims.
- Custom JWT: More control but significant security surface area; not justified for this use case.

---

## 3. openapi-typescript + openapi-fetch

**Decision**: Keep the existing `openapi-typescript` dev dependency for code generation (`npm run generate:types` → `src/types/api.ts`). Add `openapi-fetch` as a runtime client that is typed against the generated schema.

**Rationale**: `openapi-typescript` generates zero-runtime types only; `openapi-fetch` is a tiny (~2KB) fetch wrapper that uses those types for full end-to-end type safety on every API call. Together they replace a full code-gen SDK without runtime overhead.

**Key implementation details**:
- `src/lib/api.ts` creates a singleton `createClient<paths>({ baseUrl })` from `openapi-fetch`.
- All calls go through this client: `api.GET("/listings", { params: { query: { page: 1 } } })`.
- The `Authorization: Bearer {accessToken}` header is injected via a `use` middleware on the client, reading the NextAuth session token.
- Error responses are typed via `ErrorResponse` schema from the OpenAPI spec.

**Alternatives considered**:
- `openapi-typescript-codegen` (user input): Generates class-based SDK with runtime overhead; openapi-fetch is lighter and more idiomatic with App Router.
- Axios + manual types: No type safety, higher maintenance cost.

---

## 4. TanStack Query v5

**Decision**: Use `@tanstack/react-query@^5` with a single `QueryClient` created once per request on the server (using `HydrationBoundary` for RSC prefetching) and mounted in `QueryProvider.tsx`.

**Rationale**: TanStack Query v5 has first-class RSC support via `dehydrate/hydrate`. Prefetching in server components eliminates loading spinners on initial page load. Client-side re-fetches keep data fresh with configurable `staleTime`.

**Key implementation details**:
- `QueryProvider.tsx` wraps the client subtree with `QueryClientProvider`.
- Default query options: `staleTime: 60_000`, `gcTime: 300_000`, `retry: 2`.
- Loading states: `isPending` → skeleton components; `isError` → `ErrorBoundary` + retry button.
- Cache invalidation: after mutations (e.g., zone save, alert create) use `queryClient.invalidateQueries({ queryKey: [...] })`.

---

## 5. Zustand v5 Stores

**Decision**: Three stores — `chatStore`, `notificationStore`, `uiStore` — each created with `create` and `immer` middleware for ergonomic nested state updates.

**Rationale**: Zustand is the constitution-mandated client state library. Three stores give clean domain separation; immer prevents accidental mutation errors with nested objects.

**Store designs**:

### chatStore
```ts
interface ChatStore {
  sessionId: string | null;
  messages: ChatMessage[];       // {id, role, content, timestamp}
  criteria: SearchCriteria | null;
  wsStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  // Actions
  setSessionId(id: string): void;
  addMessage(msg: ChatMessage): void;
  appendChunk(conversationId: string, chunk: string, isFinal: boolean): void;
  setCriteria(c: SearchCriteria): void;
  setWsStatus(s: WsStatus): void;
  reset(): void;
}
```

### notificationStore
```ts
interface NotificationStore {
  alerts: DealAlert[];           // unread deal alerts
  toastQueue: Toast[];
  // Actions
  addAlert(a: DealAlert): void;
  markRead(eventId: string): void;
  pushToast(t: Toast): void;
  dismissToast(id: string): void;
}
```

### uiStore
```ts
interface UIStore {
  sidebarOpen: boolean;
  // Actions
  toggleSidebar(): void;
  setSidebarOpen(v: boolean): void;
}
```

---

## 6. WebSocket Manager (lib/ws.ts)

**Decision**: Implement `WebSocketManager` as a class with singleton lifecycle managed by `WSProvider.tsx`. The WS endpoint is `ws(s)://{WS_HOST}/ws/chat?token={jwt}` (confirmed from `ws-server/cmd/routes.go` — route `/ws/chat`).

**Rationale**: A class encapsulates reconnect state, heartbeat timer, and message routing in one place, making it straightforward to test and swap.

**Key implementation details**:
- `connect(jwt: string)`: opens `new WebSocket(url)`, attaches handlers.
- Reconnect: on `onclose` / `onerror`, schedule retry with `setTimeout(reconnect, backoffMs)`. Backoff: `Math.min(backoffMs * 2, 30_000)` starting from 1000ms, reset to 1000ms on successful open.
- Heartbeat: `setInterval(() => ws.send(JSON.stringify({ type: "ping" })), 25_000)` cleared on disconnect.
- Message routing: parse `Envelope { type, session_id, payload }` → switch on `type`:
  - `text_chunk` → `chatStore.appendChunk`
  - `chips` → `chatStore.addMessage` (assistant choices)
  - `image_carousel` → `chatStore.addMessage` (listing carousel)
  - `criteria_summary` → `chatStore.setCriteria`
  - `search_results` → `chatStore.addMessage`
  - `deal_alert` → `notificationStore.addAlert` + `notificationStore.pushToast`
  - `error` → `chatStore.addMessage` (error display)
  - `pong` → no-op (heartbeat ack)
- `WSProvider` reads `session.accessToken` and calls `manager.connect(token)` in a `useEffect` on mount; calls `manager.disconnect()` on unmount.

**Message types** (from `ws-server/internal/protocol/messages.go`):

| Server → Client | Payload |
|----------------|---------|
| `text_chunk` | `{ text, conversation_id, is_final }` |
| `chips` | `{ options: [{label, value}] }` |
| `image_carousel` | `{ listings: CarouselItem[] }` |
| `criteria_summary` | `{ conversation_id, criteria, ready_to_search }` |
| `search_results` | `{ conversation_id, total_count, listings: SearchListing[] }` |
| `deal_alert` | `{ event_id, listing_id, title, price_eur, deal_score, … }` |
| `error` | `{ code, message }` |
| `pong` | _(empty payload)_ |

| Client → Server | Payload |
|----------------|---------|
| `chat_message` | `{ user_message, country_code? }` |
| `image_feedback` | `{ listing_id, action }` |
| `criteria_confirm` | `{ confirmed, notes? }` |
| `ping` | _(empty)_ |

---

## 7. Layout: Header + Collapsible Sidebar

**Decision**: `MainLayout.tsx` renders a fixed header and a CSS-grid sidebar. Sidebar state comes from `uiStore.sidebarOpen`. On mobile (< 768px), sidebar defaults to closed and overlays as a drawer. On desktop (≥ 1024px), defaults to open as a rail.

**Rationale**: Using Tailwind CSS 4 responsive classes and a single Zustand boolean avoids complex media-query event listeners. shadcn/ui `Sheet` component handles the mobile drawer overlay gracefully.

**Navigation items**:
| Route | Label key | Icon | Requires Admin |
|-------|-----------|------|---------------|
| `/[locale]` | `nav.home` | Home | No |
| `/[locale]/search` | `nav.search` | Search | No |
| `/[locale]/dashboard` | `nav.dashboard` | BarChart | No |
| `/[locale]/zones` | `nav.zones` | Map | No |
| `/[locale]/alerts` | `nav.alerts` | Bell | No |
| `/[locale]/portfolio` | `nav.portfolio` | Briefcase | No |
| `/[locale]/admin` | `nav.admin` | Settings | Yes (role check) |

---

## 8. Tailwind CSS 4 + shadcn/ui Setup

**Decision**: Use Tailwind CSS 4 (via `@tailwindcss/vite` or the Next.js PostCSS plugin depending on release; fall back to `tailwindcss@4.x` with `@import "tailwindcss"` in globals.css). Use shadcn/ui with the `"new-york"` style and `"neutral"` base color.

**Rationale**: Tailwind CSS 4 uses CSS-native cascade layers and a zero-config approach (no tailwind.config.js required for basic use). shadcn/ui provides accessible, unstyled primitives (Button, Dialog, Sheet, Avatar, DropdownMenu, etc.) that work with Tailwind 4.

---

## 9. Environment Variables

All config via `.env.local` (local) / Kubernetes Sealed Secrets (production):

```
NEXTAUTH_SECRET=...                  # Random 32-byte secret
NEXTAUTH_URL=https://estategap.com   # Public URL
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
NEXT_PUBLIC_API_URL=https://api.estategap.com
NEXT_PUBLIC_WS_URL=wss://ws.estategap.com
```

`NEXT_PUBLIC_*` vars are inlined at build time; no secrets should use this prefix.

---

## 10. NEEDS CLARIFICATION resolutions

All items resolved from user input and code inspection — no open clarifications remain.

| Item | Resolution |
|------|-----------|
| WebSocket endpoint path | `/ws/chat` (confirmed from `ws-server/cmd/routes.go`) |
| WS auth mechanism | JWT as `?token=` query param (standard for gorilla/websocket — header auth not supported during upgrade) |
| API types generation tool | `openapi-typescript` already in devDeps; runtime client uses `openapi-fetch` |
| Subscription tier field | `subscription_tier` in `UserProfile` schema (confirmed from `api-gateway/openapi.yaml`) |
| `openapi-typescript-codegen` vs `openapi-typescript` | Using `openapi-typescript` + `openapi-fetch` — lighter, zero runtime, already installed |
