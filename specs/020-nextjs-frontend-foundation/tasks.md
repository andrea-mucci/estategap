# Tasks: Next.js Frontend Foundation

**Input**: Design documents from `/specs/020-nextjs-frontend-foundation/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.  
**Tests**: Vitest unit tests included in Polish phase (constitution §V mandates Vitest + RTL).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Paths are relative to repo root; all frontend code lives under `frontend/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install all new dependencies, configure tooling, and generate API types. No user story work begins until this phase is complete.

- [X] T001 Update `frontend/package.json` — add runtime deps: `next-intl`, `next-auth@beta`, `@tanstack/react-query`, `@tanstack/react-query-devtools`, `zustand`, `immer`, `openapi-fetch`, `tailwindcss`, `@tailwindcss/postcss`, `clsx`, `tailwind-merge`, `lucide-react`, `class-variance-authority`, `@radix-ui/react-slot`; add dev deps: `vitest`, `@vitejs/plugin-react`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`
- [X] T002 Add Tailwind CSS 4 PostCSS config — create `frontend/postcss.config.mjs` with `@tailwindcss/postcss` plugin; add `@import "tailwindcss"` to `frontend/src/app/globals.css`
- [X] T003 [P] Initialize shadcn/ui — run `npx shadcn@latest init` (new-york style, neutral color, CSS variables); then add components: `button input label form card badge avatar dropdown-menu dialog sheet tooltip skeleton scroll-area separator toast`; config written to `frontend/components.json`
- [ ] T004 [P] Generate API TypeScript types — run `npm run generate:types` inside `frontend/`; verify `frontend/src/types/api.ts` is created from `services/api-gateway/openapi.yaml`
- [X] T005 [P] Update `frontend/tsconfig.json` — add path aliases: `@/*` → `./src/*`, `@/types/*` → `./src/types/*`; confirm `strict: true` is set
- [X] T006 [P] Update `frontend/next.config.ts` — wrap config with `createNextIntlPlugin` from `next-intl/plugin`; add `images.remotePatterns` for API image domains; keep `output: "standalone"`
- [X] T007 Create `frontend/.env.local.example` with all required variable names: `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core project structure and configuration that every user story depends on. Must complete before any story begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T008 Create `frontend/src/i18n/routing.ts` — export `locales` array (`["en","es","fr","it","de","pt","nl","pl","sv","el"]`), `defaultLocale: "en"`, and typed `createNavigation` helpers using `next-intl/navigation`
- [X] T009 Create `frontend/src/i18n/request.ts` — export `getRequestConfig` that reads the active locale from `requestLocale` and dynamically imports `messages/{locale}.json`
- [X] T010 [P] Create `frontend/src/types/next-auth.d.ts` — extend `Session` with `{ user: { subscriptionTier, role }, accessToken, accessTokenExpires }` and extend `JWT` with `{ accessToken, accessTokenExpires, refreshToken, subscriptionTier, role, error? }` per `data-model.md`
- [X] T011 [P] Scaffold Zustand store files — create `frontend/src/stores/chatStore.ts`, `notificationStore.ts`, `uiStore.ts` as typed stubs with `create<StoreType>()(() => initialState)` (no logic yet; implementations in Phase 6)
- [X] T012 [P] Create `frontend/src/lib/auth.ts` — export `requireSession()` (calls `auth()` and throws redirect if null) and `getAccessToken()` (extracts `session.accessToken`) using `next-auth`
- [X] T013 Create `frontend/src/app/[locale]/layout.tsx` — root layout that composes `NextIntlClientProvider`, `SessionProvider`, `QueryClientProvider`; accepts `{ children, params: { locale } }`; loads messages via `getMessages()`; sets `<html lang={locale}>`

**Checkpoint**: Core configuration ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Language-Switching Navigation (Priority: P1) 🎯 MVP

**Goal**: App renders in all 10 languages. URL-based locale routing works. Language switcher updates UI without page reload.

**Independent Test**: Start dev server → open `http://localhost:3000` → redirected to `/en` → click language switcher → select `es` → URL changes to `/es/...` → all visible text changes to Spanish without page reload.

### Implementation for User Story 1

- [X] T014 [US1] Create `frontend/src/messages/en.json` — define complete English message tree with all keys from `data-model.md §6`: `nav.*`, `auth.*`, `chat.*`, `common.*`, `listing.*`, `alerts.*`, `meta.*` (canonical reference; ~50 keys)
- [X] T015 [P] [US1] Create `frontend/src/messages/es.json`, `fr.json`, `it.json`, `de.json` — translate all 50 keys from `en.json`; use English as fallback for any missing keys
- [X] T016 [P] [US1] Create `frontend/src/messages/pt.json`, `nl.json`, `pl.json`, `sv.json`, `el.json` — translate all 50 keys from `en.json`; use English as fallback for any missing keys
- [X] T017 [US1] Create `frontend/middleware.ts` — chain `createMiddleware` from `next-intl/middleware` using routing config from `src/i18n/routing.ts`; handles locale detection from `Accept-Language` header and redirects `/` → `/{defaultLocale}`
- [X] T018 [US1] Create `frontend/src/app/[locale]/page.tsx` — minimal home page stub that renders `useTranslations("meta").appName` heading and `useTranslations("meta").tagline` subheading (verifies i18n works)
- [X] T019 [P] [US1] Create `frontend/src/components/layout/LanguageSwitcher.tsx` — renders a `DropdownMenu` (shadcn/ui) listing all 10 locales by display name; on select calls `router.replace(pathname, { locale: selected })` from `next-intl/navigation`; shows current locale flag/code

**Checkpoint**: User Story 1 fully functional. `http://localhost:3000/es` shows Spanish strings. Switcher works without page reload.

---

## Phase 4: User Story 2 — Authentication Flows (Priority: P1)

**Goal**: Email+password and Google OAuth login/register work. Protected routes redirect unauthenticated users. Session includes subscription tier.

**Independent Test**: Visit `/en/dashboard` unauthenticated → redirected to `/en/login` → login with credentials → redirected to dashboard → user menu shows subscription tier → logout → redirected to login.

### Implementation for User Story 2

- [X] T020 [US2] Create `frontend/src/auth.ts` — configure `NextAuth` with `CredentialsProvider` (calls `POST {API_URL}/auth/login`, stores `access_token` and `refresh_token` in JWT) and `GoogleProvider`; implement `jwt` callback (token refresh when within 60s of expiry using `POST /auth/refresh`) and `session` callback (copies `accessToken`, `subscriptionTier`, `role` to session object)
- [X] T021 [US2] Create `frontend/src/app/api/auth/[...nextauth]/route.ts` — re-export `{ GET, POST }` from `src/auth.ts` handlers
- [X] T022 [US2] Create `frontend/src/providers/AuthProvider.tsx` — thin wrapper that renders `SessionProvider` from `next-auth/react` around `{children}`; imported in root layout (T013)
- [X] T023 [US2] Update `frontend/middleware.ts` (extends T017) — add `auth` middleware from `next-auth` to protect `/(protected)` routes; chain: locale middleware first, then auth check; unauthenticated requests to `/(protected)/*` redirect to `/{locale}/login`
- [X] T024 [P] [US2] Create `frontend/src/app/[locale]/(auth)/login/page.tsx` — email+password form using React Hook Form + Zod (schema: email required, password min 8); on submit calls `signIn("credentials", { email, password, redirect: false })`; displays `auth.loginError` on failure; link to `/register`; "Sign in with Google" button calls `signIn("google")`
- [X] T025 [P] [US2] Create `frontend/src/app/[locale]/(auth)/register/page.tsx` — name, email, password form; on submit calls `POST {API_URL}/auth/register` via `fetch`; on success calls `signIn("credentials")`; link to `/login`
- [X] T026 [US2] Create `frontend/src/app/[locale]/(protected)/layout.tsx` — server component that calls `requireSession()` from `src/lib/auth.ts`; renders `{children}` only when session is valid (middleware is the primary guard; this is a belt-and-suspenders server-side check)
- [X] T027 [US2] Create `frontend/src/components/layout/UserMenu.tsx` — `DropdownMenu` showing user avatar (`session.user.image`), name, email, subscription tier badge; menu items: Profile, Settings, Logout (calls `signOut()`); uses `useSession()` from `next-auth/react`

**Checkpoint**: User Story 2 fully functional. Auth flows work. Protected routes redirect. Session contains tier.

---

## Phase 5: User Story 3 — API Data Fetching (Priority: P2)

**Goal**: API calls authenticated with JWT. Loading skeletons and error messages with retry shown on all data pages.

**Independent Test**: Navigate to `/en/dashboard` while logged in → observe loading skeleton → data renders → disconnect API (set wrong URL) → observe error message with Retry button → fix URL → Retry → data loads from cache or re-fetches.

### Implementation for User Story 3

- [X] T028 [US3] Create `frontend/src/lib/api.ts` — create `openapi-fetch` client typed with `paths` from `src/types/api.ts`; set `baseUrl: process.env.NEXT_PUBLIC_API_URL`; add `use` middleware that injects `Authorization: Bearer {accessToken}` (reads token from `getAccessToken()` in `src/lib/auth.ts` for server components; from `useSession()` for client components)
- [X] T029 [US3] Create `frontend/src/providers/QueryProvider.tsx` — `"use client"` component that creates a `QueryClient` with `defaultOptions: { queries: { staleTime: 60_000, gcTime: 300_000, retry: 2 } }`; wraps children with `QueryClientProvider`; adds `ReactQueryDevtools` (dev only); import this in root layout (T013)
- [X] T030 [P] [US3] Create `frontend/src/components/ui/LoadingSkeleton.tsx` — generic skeleton component using shadcn/ui `Skeleton`; accepts `rows?: number` and `className`; used by all data pages during `isPending`
- [X] T031 [P] [US3] Create `frontend/src/components/ui/ErrorDisplay.tsx` — renders error message (`common.error`) + Retry button that calls provided `refetch()` function; accepts `error: Error`, `refetch: () => void`
- [X] T032 [US3] Create `frontend/src/hooks/useListings.ts` — `useQuery` hook that calls `GET /listings` via `src/lib/api.ts`; returns `{ data, isPending, isError, refetch, error }`; query key: `["listings", params]`
- [X] T033 [US3] Update `frontend/src/app/[locale]/(protected)/dashboard/page.tsx` — server component that prefetches listings using `HydrationBoundary`; client child shows `<LoadingSkeleton>` when `isPending`, `<ErrorDisplay>` when `isError`, listing count summary when success

**Checkpoint**: User Story 3 fully functional. All API calls show loading/error states. Data is cached.

---

## Phase 6: User Story 4 — Real-Time Chat and Notifications (Priority: P2)

**Goal**: WebSocket connects on authenticated page load, auto-reconnects with backoff, dispatches messages to Zustand stores, chat UI functional.

**Independent Test**: Open DevTools → Network → WS tab → load `/en/dashboard` while logged in → `wss://…/ws/chat?token=…` connection appears → disconnect network briefly → watch reconnect attempts in console → reconnect succeeds → send a chat message → response streams in chat panel.

### Implementation for User Story 4

- [X] T034 [US4] Implement `frontend/src/lib/ws.ts` — `WebSocketManager` class with `connect(jwt: string)`, `disconnect()`, `send(message: object)`, `onMessage(handler)` methods; `connect` opens `new WebSocket(\`${WS_URL}/ws/chat?token=${jwt}\`)`; stores `onMessage` handlers in array; `send` serialises to JSON; `disconnect` clears timers and closes socket
- [X] T035 [US4] Add auto-reconnect to `WebSocketManager` in `frontend/src/lib/ws.ts` — `onclose`/`onerror` handlers schedule `reconnect()` with `backoffMs = Math.min(backoffMs * 2, 30_000)` starting from 1000ms; reset to 1000ms on successful `onopen`; update `chatStore.wsStatus` on each state transition (`connecting`, `connected`, `disconnected`, `error`)
- [X] T036 [US4] Add heartbeat to `WebSocketManager` in `frontend/src/lib/ws.ts` — on `onopen` start `setInterval(() => send({ type: "ping" }), 25_000)`; clear interval on `disconnect()`; handle `pong` message as no-op
- [X] T037 [P] [US4] Implement `frontend/src/stores/chatStore.ts` (replaces T011 stub) — full Zustand store with `immer`; implement all actions from `data-model.md §2`: `setSessionId`, `addMessage`, `appendChunk` (accumulates streaming chunks, sets `isStreaming: false` on `is_final`), `setCriteria`, `setWsStatus`, `reset`
- [X] T038 [P] [US4] Implement `frontend/src/stores/notificationStore.ts` (replaces T011 stub) — full Zustand store with `immer`; implement all actions from `data-model.md §3`: `addAlert`, `markRead`, `markAllRead`, `pushToast`, `dismissToast`; compute `unreadCount` as derived value
- [X] T039 [US4] Implement `frontend/src/stores/uiStore.ts` (replaces T011 stub) — `sidebarOpen: true` default (desktop); `toggleSidebar`, `setSidebarOpen` actions
- [X] T040 [US4] Add WebSocket message routing to `WebSocketManager` in `frontend/src/lib/ws.ts` — `onmessage` parses `Envelope { type, session_id, payload }`; switch on `type`: `text_chunk` → `chatStore.appendChunk`; `chips`/`image_carousel`/`criteria_summary`/`search_results` → `chatStore.addMessage`; `deal_alert` → `notificationStore.addAlert` + `notificationStore.pushToast`; `error` → `chatStore.addMessage`; `pong` → no-op
- [X] T041 [US4] Create `frontend/src/providers/WSProvider.tsx` — `"use client"` component; reads `session.accessToken` via `useSession()`; creates singleton `WebSocketManager` in `useRef`; `useEffect` calls `manager.connect(token)` when session is authenticated, `manager.disconnect()` on unmount; exports `useWebSocket()` hook
- [X] T042 [P] [US4] Create `frontend/src/components/chat/ChatInput.tsx` — text input + send button; on submit calls `manager.send({ type: "chat_message", session_id, payload: { user_message, country_code } })`; disabled when `wsStatus !== "connected"`
- [X] T043 [P] [US4] Create `frontend/src/components/chat/ChatMessage.tsx` and `ChatPanel.tsx` — `ChatMessage` renders a single message (text with streaming cursor, chips buttons, listing carousel, search results list, error); `ChatPanel` reads `chatStore.messages` and renders list; includes WS status indicator badge

**Checkpoint**: User Story 4 fully functional. WebSocket connects, reconnects, chat streams, deal alerts appear as toasts.

---

## Phase 7: User Story 5 — Responsive Layout (Priority: P3)

**Goal**: Header, collapsible sidebar, and main content area adapt across mobile/tablet/desktop. Sidebar collapses to drawer on mobile.

**Independent Test**: Open `/en/dashboard` on desktop → sidebar visible with nav items → resize to 375px → sidebar collapsed → hamburger button appears → tap it → sidebar slides in as drawer → tap outside → closes.

### Implementation for User Story 5

- [X] T044 [US5] Create `frontend/src/components/layout/Sidebar.tsx` — nav items list (Home, Search, Dashboard, Zones, Alerts, Portfolio, Admin) from `data-model.md §7`; reads `uiStore.sidebarOpen`; on desktop (≥1024px) renders as collapsible rail via CSS grid; on mobile (<768px) renders as shadcn/ui `Sheet` (drawer overlay); Admin item only shown when `session.user.role === "admin"`; uses `useTranslations("nav")` for labels; active item highlighted via `usePathname()`
- [X] T045 [US5] Create `frontend/src/components/layout/Header.tsx` — fixed top bar with: app logo/wordmark (`meta.appName`), `<LanguageSwitcher />` (T019), notification bell with `notificationStore.unreadCount` badge, `<UserMenu />` (T027), hamburger toggle button (calls `uiStore.toggleSidebar`) visible on mobile
- [X] T046 [US5] Create `frontend/src/components/layout/MainLayout.tsx` — CSS grid layout: header row (fixed, full width), sidebar column (collapsible, controlled by `uiStore.sidebarOpen`), main content area (scrollable); passes `{children}` to main; composites `<Header>` and `<Sidebar>`
- [X] T047 [US5] Update `frontend/src/app/[locale]/(protected)/layout.tsx` (extends T026) — wrap children with `<MainLayout>` and `<WSProvider>` (from T041); ensures layout and WebSocket are both active for all protected pages
- [X] T048 [P] [US5] Create stub pages for remaining protected routes — `frontend/src/app/[locale]/(protected)/search/page.tsx`, `zones/page.tsx`, `alerts/page.tsx`, `portfolio/page.tsx`, `admin/page.tsx`; each renders a heading from `useTranslations("nav")` and a `<LoadingSkeleton rows={3} />` as placeholder
- [X] T049 [US5] Create `frontend/src/app/[locale]/(protected)/listing/[id]/page.tsx` — server component that fetches `GET /listings/{id}` via `src/lib/api.ts`; renders listing title, price, area, deal score, photo; shows `<LoadingSkeleton>` / `<ErrorDisplay>` per US3 pattern

**Checkpoint**: User Story 5 fully functional. Sidebar responsive. Header shows in all locales. All nav routes load.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Test coverage, production build validation, Lighthouse scores, final wiring checks.

- [X] T050 [P] Configure Vitest — create `frontend/vitest.config.ts` with `@vitejs/plugin-react`, `jsdom` environment, `globals: true`, `setupFiles: ["src/test/setup.ts"]`; create `frontend/src/test/setup.ts` with `@testing-library/jest-dom` import
- [X] T051 [P] Write unit tests for `WebSocketManager` in `frontend/src/lib/ws.test.ts` — mock `global.WebSocket`; test: connects with correct URL, reconnects with backoff on close, sends heartbeat, routes `text_chunk` to `chatStore.appendChunk`, routes `deal_alert` to `notificationStore.addAlert`, disconnects cleanly
- [X] T052 [P] Write unit tests for `chatStore` and `notificationStore` in `frontend/src/stores/chatStore.test.ts` and `notificationStore.test.ts` — test: `addMessage`, `appendChunk` streaming accumulation, `setCriteria`, `addAlert` increments `unreadCount`, `markRead` decrements
- [X] T053 Update `frontend/src/app/[locale]/(protected)/home/page.tsx` (or root page) — integrate `<ChatInput>` and `<ChatPanel>` for the AI chat home screen; `<WSProvider>` already active from protected layout
- [ ] T054 Run production build and Lighthouse audit — `npm run build` inside `frontend/`; serve with `npm run start`; run Lighthouse on `/en` and `/en/dashboard`; fix any issues causing Performance < 90 or Accessibility < 85 (common fixes: `next/image` for all images, `aria-label` on icon buttons, font preloading)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (deps installed, Tailwind/shadcn configured)
- **Phase 3 (US1 - i18n)**: Depends on Phase 2 (routing config, root layout ready)
- **Phase 4 (US2 - Auth)**: Depends on Phase 2; benefits from Phase 3 (i18n strings in login page)
- **Phase 5 (US3 - API)**: Depends on Phase 2 (T004 types, T013 root layout); can start alongside Phase 4
- **Phase 6 (US4 - WebSocket)**: Depends on Phase 2 (store scaffolds T011); can start alongside Phase 4/5
- **Phase 7 (US5 - Layout)**: Depends on Phase 3 (LanguageSwitcher), Phase 4 (UserMenu), Phase 6 (uiStore)
- **Phase 8 (Polish)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 — fully independent
- **US2 (P1)**: Depends only on Phase 2 — fully independent (benefits from US1 for i18n in pages)
- **US3 (P2)**: Depends on Phase 2 — fully independent (API types from T004)
- **US4 (P2)**: Depends on Phase 2 — fully independent (store stubs from T011)
- **US5 (P3)**: Depends on US1 (LanguageSwitcher), US2 (UserMenu), US4 (uiStore + WSProvider)

### Critical Path

```
T001 → T002 → T003/T004/T005/T006 → T008/T009/T010/T011/T012 → T013
  → [T014/T015/T016/T017/T018/T019] (US1)
  → [T020/T021/T022/T023/T024/T025/T026/T027] (US2)
  → [T028/T029/T030/T031/T032/T033] (US3) — can overlap with US2
  → [T034–T043] (US4) — can overlap with US2/US3
  → [T044/T045/T046/T047/T048/T049] (US5) — needs US1+US2+US4
  → [T050/T051/T052/T053/T054] (Polish)
```

### Parallel Opportunities

Within each phase, tasks marked `[P]` can be run concurrently:

**Phase 1 parallel**: T003, T004, T005, T006 — all configure different files simultaneously

**Phase 2 parallel**: T010, T011, T012 — independent type/store/provider files

**Phase 3 parallel**: T015, T016 (locale JSON files); T019 (LanguageSwitcher) after T014

**Phase 4 parallel**: T024, T025 (login and register pages after T020+T021)

**Phase 5 parallel**: T030, T031 (LoadingSkeleton and ErrorDisplay)

**Phase 6 parallel**: T037, T038 (chatStore and notificationStore); T042, T043 (chat components after T037–T040)

**Phase 7 parallel**: T048 (stub pages) after T047

**Phase 8 parallel**: T050, T051, T052 (test setup, WS tests, store tests)

---

## Parallel Example: Phase 2

```
# These can all run simultaneously in separate sub-agents:
Task T010: "Create frontend/src/types/next-auth.d.ts with extended session types"
Task T011: "Scaffold frontend/src/stores/chatStore.ts, notificationStore.ts, uiStore.ts as typed stubs"
Task T012: "Create frontend/src/lib/auth.ts with requireSession() and getAccessToken() helpers"
```

## Parallel Example: Phase 6 (WebSocket)

```
# After T034–T036 (WebSocketManager core) complete:
Task T037: "Implement chatStore.ts with full Zustand state and all message routing actions"
Task T038: "Implement notificationStore.ts with full Zustand state and toast queue"
# Then after T037+T038+T039+T040 complete:
Task T042: "Create frontend/src/components/chat/ChatInput.tsx"
Task T043: "Create frontend/src/components/chat/ChatMessage.tsx and ChatPanel.tsx"
```

---

## Implementation Strategy

### MVP First (US1 + US2 — Language and Auth)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (locale routing + language switcher)
4. **STOP and VALIDATE**: All 10 locales render; switcher works
5. Complete Phase 4: US2 (auth flows + protected routes)
6. **STOP and VALIDATE**: Login/register/Google OAuth work; protected routes redirect; tier in session
7. Deploy minimal authenticated app

### Incremental Delivery

1. Setup + Foundational → Project skeleton ready
2. Add US1 → App speaks 10 languages (MVP slice ①)
3. Add US2 → Auth-gated app (MVP slice ②, shippable)
4. Add US3 → Data fetching with UX states (adds listings/dashboard data)
5. Add US4 → Real-time chat and deal alerts (core differentiator)
6. Add US5 → Full responsive layout (production-ready shell)

### Parallel Team Strategy

With multiple developers after Phase 2:

- **Dev A**: US1 (i18n) → US5 (layout shell)
- **Dev B**: US2 (auth) → US3 (API client + queries)
- **Dev C**: US4 (WebSocket + stores + chat)

Stories integrate cleanly at Phase 7 (layout) which uses outputs of all three streams.

---

## Notes

- `[P]` tasks operate on different files with no incomplete dependencies
- `[Story]` label maps each task to its user story for traceability
- **No shadcn components need to be coded** — generated by `npx shadcn@latest add`; only wrapper/composition files need implementation
- **Generated `src/types/api.ts`** must be committed and regenerated only when `openapi.yaml` changes
- **`middleware.ts`** is built in two steps (T017 for i18n, T023 extends for auth) — coordinate edits
- Commit after each phase checkpoint to keep branch history clean
- Validate each user story independently at its checkpoint before moving to next phase
