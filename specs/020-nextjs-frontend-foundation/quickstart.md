# Quickstart: Next.js Frontend Foundation

**Date**: 2026-04-17 | **Branch**: `020-nextjs-frontend-foundation`

---

## Prerequisites

- Node.js 22+, npm 10+
- The `services/api-gateway/openapi.yaml` spec must exist (it does — 1577 lines)
- `.env.local` with the required variables (see below)

---

## Environment Variables

Create `frontend/.env.local`:

```bash
# NextAuth
NEXTAUTH_SECRET="<generate with: openssl rand -base64 32>"
NEXTAUTH_URL="http://localhost:3000"

# Google OAuth (create at console.cloud.google.com)
GOOGLE_CLIENT_ID="<your-client-id>.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="<your-client-secret>"

# Backend URLs (public — safe to expose in browser)
NEXT_PUBLIC_API_URL="http://localhost:8080"
NEXT_PUBLIC_WS_URL="ws://localhost:9090"
```

---

## Install Dependencies

```bash
cd frontend

# Core runtime dependencies
npm install \
  next-intl \
  next-auth@beta \
  @tanstack/react-query \
  @tanstack/react-query-devtools \
  zustand \
  immer \
  openapi-fetch \
  tailwindcss \
  @tailwindcss/postcss \
  clsx \
  tailwind-merge \
  lucide-react \
  class-variance-authority \
  @radix-ui/react-slot \
  @radix-ui/react-dropdown-menu \
  @radix-ui/react-dialog \
  @radix-ui/react-sheet \
  @radix-ui/react-avatar \
  @radix-ui/react-tooltip

# Dev dependencies
npm install -D \
  vitest \
  @vitejs/plugin-react \
  @testing-library/react \
  @testing-library/user-event \
  jsdom
```

---

## Generate API Types

```bash
cd frontend
npm run generate:types
# Output: src/types/api.ts
```

This runs `openapi-typescript ../services/api-gateway/openapi.yaml -o src/types/api.ts`.
Re-run whenever `services/api-gateway/openapi.yaml` changes.

---

## Initialize shadcn/ui

```bash
cd frontend
npx shadcn@latest init
# Select: new-york style, neutral color, CSS variables: yes
# This creates: components.json, src/app/globals.css (updated), src/components/ui/
```

Then add the specific components needed:

```bash
npx shadcn@latest add button input label form card badge avatar
npx shadcn@latest add dropdown-menu dialog sheet tooltip skeleton
npx shadcn@latest add scroll-area separator toast
```

---

## Development Server

```bash
cd frontend
npm run dev
# Open: http://localhost:3000
# Redirects to: http://localhost:3000/en (locale middleware)
```

---

## Key Development Commands

```bash
# Type check
npm run typecheck

# Lint
npm run lint

# Run tests
npm run test          # vitest

# Build for production
npm run build

# Start production server
npm run start
```

---

## File Creation Order

For implementing this feature, create files in this order to avoid circular imports:

1. `src/types/api.ts` — auto-generated (run `generate:types`)
2. `src/i18n/routing.ts` + `src/i18n/request.ts` — locale config
3. `messages/en.json` (and other locales) — all i18n strings
4. `src/stores/uiStore.ts`, `chatStore.ts`, `notificationStore.ts` — Zustand stores
5. `src/lib/ws.ts` — WebSocketManager (depends on store types)
6. `src/lib/api.ts` — API client (depends on `src/types/api.ts`)
7. `src/lib/auth.ts` — NextAuth helpers
8. `src/auth.ts` — NextAuth config
9. `src/providers/` — React providers
10. `middleware.ts` — combined next-intl + auth middleware
11. `src/components/layout/` — Header, Sidebar, MainLayout
12. `src/app/[locale]/layout.tsx` — root layout
13. `src/app/[locale]/(auth)/` — login, register pages
14. `src/app/[locale]/(protected)/layout.tsx` — protected layout with WSProvider
15. `src/app/[locale]/(protected)/` — all protected pages

---

## Testing Strategy

```bash
# Unit tests for stores
vitest src/stores/chatStore.test.ts
vitest src/stores/notificationStore.test.ts

# Unit tests for WebSocketManager (mock WebSocket)
vitest src/lib/ws.test.ts

# Component tests
vitest src/components/layout/Header.test.tsx
vitest src/components/layout/Sidebar.test.tsx

# Auth flow tests (mock NextAuth)
vitest src/app/[locale]/(auth)/login/page.test.tsx
```

---

## Docker Build

The existing `Dockerfile` uses `output: "standalone"` — no changes needed.

```bash
cd frontend
docker build -t estategap-frontend:local .
docker run -p 3000:3000 \
  -e NEXTAUTH_SECRET=... \
  -e NEXTAUTH_URL=http://localhost:3000 \
  -e NEXT_PUBLIC_API_URL=http://localhost:8080 \
  -e NEXT_PUBLIC_WS_URL=ws://localhost:9090 \
  estategap-frontend:local
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `NEXTAUTH_SECRET not set` | Add to `.env.local` and restart dev server |
| `openapi-typescript` generates empty file | Check that `services/api-gateway/openapi.yaml` path is correct (relative to `frontend/`) |
| WebSocket `401` on connect | JWT expired — refresh the NextAuth session |
| Locale not detected | Ensure `middleware.ts` is at `frontend/middleware.ts` (not inside `src/`) |
| shadcn/ui components not found | Run `npx shadcn@latest add <component>` to generate them |
| Tailwind classes not applied | Ensure `tailwind.config.ts` `content` includes `./src/**/*.{ts,tsx}` |
