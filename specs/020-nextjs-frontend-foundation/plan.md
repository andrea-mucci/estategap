# Implementation Plan: Next.js Frontend Foundation

**Branch**: `020-nextjs-frontend-foundation` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/020-nextjs-frontend-foundation/spec.md`

## Summary

Extend the existing bare Next.js 15 scaffold (`frontend/`) into a complete application shell with:
locale-based routing (10 languages), NextAuth v5 authentication (credentials + Google OAuth),
auto-generated API types from `services/api-gateway/openapi.yaml`, TanStack Query v5 for
all data fetching, Zustand stores for chat/notifications/UI state, a WebSocket client class
with exponential-backoff reconnect and heartbeat, and a responsive layout with collapsible
sidebar and header language switcher.

## Technical Context

**Language/Version**: TypeScript 5.5 (strict mode), Node.js 22  
**Primary Dependencies**: Next.js 15 (App Router, RSC), Tailwind CSS 4, shadcn/ui, next-intl, NextAuth v5, @tanstack/react-query v5, Zustand 5, openapi-typescript (already in devDeps)  
**Storage**: No direct DB access — state via TanStack Query cache + Zustand; JWT stored in NextAuth session  
**Testing**: Vitest + React Testing Library (constitution §V)  
**Target Platform**: Node.js server container (Dockerfile already present; `output: "standalone"` in next.config.ts)  
**Project Type**: Frontend web application (Next.js App Router)  
**Performance Goals**: Lighthouse Performance > 90, Accessibility > 85 on production build  
**Constraints**: Language switch < 200ms; WebSocket reconnects within 30s; auth redirect on every protected route  
**Scale/Scope**: ~15 pages/routes, 10 locales, single WebSocket connection per session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Frontend lives in `frontend/` as a standalone Next.js 15 unit. No service imports. |
| II. Event-Driven Communication | ✅ PASS | Frontend does not call backend services directly; all interaction via API Gateway (HTTP) or ws-server (WebSocket). No NATS/gRPC from frontend. |
| III. Country-First Data Sovereignty | ✅ PASS | API types include `country_code`. Chat messages pass `country_code` to ws-server. |
| IV. ML-Powered Intelligence | ✅ PASS | Frontend will display deal scores and SHAP explanations from API types. No ML in frontend itself. |
| V. Code Quality Discipline | ✅ PASS | TypeScript strict mode (already enabled), TanStack Query, Zustand, next-intl, React Hook Form + Zod, Vitest + RTL for tests. |
| VI. Security & Ethical Scraping | ✅ PASS | JWT via NextAuth. No secrets in code — env vars only. Google OAuth2 via NextAuth. |
| VII. Kubernetes-Native Deployment | ✅ PASS | Dockerfile present; `output: "standalone"` for container. Helm chart values will expose the service. |

**Result: All gates pass. Proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/020-nextjs-frontend/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── websocket-protocol.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
frontend/
├── Dockerfile                         # Existing — no changes needed
├── next.config.ts                     # Add next-intl plugin, CSP headers
├── package.json                       # Add new deps
├── tsconfig.json                      # Already strict — add path aliases
├── tailwind.config.ts                 # New — Tailwind CSS 4 config
├── components.json                    # New — shadcn/ui config
├── middleware.ts                      # New — next-intl locale + auth guards
└── src/
    ├── app/
    │   └── [locale]/
    │       ├── layout.tsx             # Root layout: providers (Auth, Query, i18n, Zustand init)
    │       ├── page.tsx               # Home — AI chat input
    │       ├── (auth)/
    │       │   ├── login/page.tsx
    │       │   └── register/page.tsx
    │       └── (protected)/
    │           ├── layout.tsx         # Auth guard + WebSocket init
    │           ├── dashboard/page.tsx
    │           ├── search/page.tsx
    │           ├── listing/[id]/page.tsx
    │           ├── zones/page.tsx
    │           ├── alerts/page.tsx
    │           ├── portfolio/page.tsx
    │           └── admin/page.tsx
    ├── components/
    │   ├── layout/
    │   │   ├── Header.tsx             # Logo, language switcher, user menu
    │   │   ├── Sidebar.tsx            # Collapsible nav
    │   │   └── MainLayout.tsx         # Composes header + sidebar + content
    │   ├── chat/
    │   │   ├── ChatInput.tsx
    │   │   ├── ChatMessage.tsx
    │   │   └── ChatPanel.tsx
    │   ├── listings/
    │   │   ├── ListingCard.tsx
    │   │   └── ListingCarousel.tsx
    │   └── ui/                        # shadcn/ui generated components
    ├── lib/
    │   ├── api.ts                     # Typed API client wrapping openapi-fetch
    │   ├── ws.ts                      # WebSocketManager class
    │   └── auth.ts                    # NextAuth helpers (getSession, signIn wrappers)
    ├── stores/
    │   ├── chatStore.ts               # Zustand: messages, session, criteria, WS status
    │   ├── notificationStore.ts       # Zustand: deal alerts, toast queue
    │   └── uiStore.ts                 # Zustand: sidebarOpen, locale preference
    ├── providers/
    │   ├── QueryProvider.tsx          # TanStack Query client provider
    │   ├── AuthProvider.tsx           # NextAuth SessionProvider
    │   └── WSProvider.tsx             # Initialises WebSocketManager on mount
    ├── types/
    │   └── api.ts                     # Auto-generated from openapi.yaml (via openapi-typescript)
    └── messages/
        ├── en.json
        ├── es.json
        ├── fr.json
        ├── it.json
        ├── de.json
        ├── pt.json
        ├── nl.json
        ├── pl.json
        ├── sv.json
        └── el.json
```

**Structure Decision**: Follows the constitution's monorepo layout (`frontend/` at repo root). All feature code is inside `frontend/src/`. The `[locale]` segment gates all user-facing routes. Auth routes are in `(auth)/` group; protected routes in `(protected)/` group with a nested layout that initialises the WebSocket.

## Complexity Tracking

No constitution violations. No additional justification needed.
