# Feature: Frontend Foundation & Authentication

## /specify prompt

```
Set up the Next.js frontend with authentication, i18n, API client, and WebSocket integration.

## What
1. Next.js 15 project with App Router, TypeScript strict mode, Tailwind CSS 4, shadcn/ui components.
2. Internationalization: next-intl with [locale] route segment. 10 languages: en, es, fr, it, de, pt, nl, pl, sv, el. Language switcher in header. All UI strings externalized in messages/{locale}.json files.
3. Authentication: NextAuth.js v5 with credentials (email+password) and Google OAuth providers. JWT session strategy. Protected route middleware. User context provider with subscription tier info.
4. API Client: auto-generated TypeScript types from OpenAPI spec. TanStack Query for all data fetching with caching, loading/error states, cache invalidation.
5. WebSocket Client: connects on authenticated page load. Auto-reconnect with exponential backoff. Zustand store for chat state (messages, criteria, session) and real-time notifications.
6. Layout: responsive header (logo, language switcher, user menu), collapsible sidebar (navigation: Home/Search, Dashboard, Zones, Alerts, Portfolio, Admin), main content area.

## Acceptance Criteria
- App renders in all 10 languages. Switcher works without page reload.
- Login, register, Google OAuth flows complete. Protected pages redirect to /login.
- API calls work with JWT. Loading and error states displayed.
- WebSocket connects and reconnects automatically.
- Layout responsive across mobile, tablet, desktop. Sidebar collapses on mobile.
- Lighthouse performance > 90, accessibility > 85.
```
