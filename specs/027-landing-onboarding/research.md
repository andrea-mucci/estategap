# Research: Landing Page & User Onboarding

**Feature**: 027-landing-onboarding
**Phase**: 0 — Research & Unknowns Resolution
**Date**: 2026-04-17

---

## 1. driver.js Tour Library

**Decision**: Use driver.js v1.x (npm: `driver.js`)

**Rationale**:
- 5 KB gzipped, zero jQuery dependency, no peer dependencies
- Framework-agnostic — works with React/Next.js via `useEffect` and `useRef`
- Supports step-based popover tours with custom HTML content
- Keyboard accessible (arrow keys, Escape to close)
- Active maintenance (2024 rewrite v1.0+), MIT license
- Simple API: `new Driver({ onDestroyStarted, onDestroyed }).drive([steps])`

**Alternatives considered**:
- Shepherd.js: Larger (~30 KB), Popper.js dependency, more config overhead — rejected
- Intro.js: Proprietary license for commercial use — rejected
- React Joyride: React-only, hooks-based — viable but driver.js is simpler for imperative navigation across pages

**Integration pattern for Next.js**:
```tsx
// useOnboarding.ts — lazy-import driver.js client-side only
const { driver } = await import('driver.js');
import 'driver.js/dist/driver.css';
```
Import inside `useEffect` to avoid SSR issues with `document`.

---

## 2. Static Generation with next-intl (generateStaticParams)

**Decision**: Use `generateStaticParams` in `app/[locale]/page.tsx` returning all 10 locales from `routing.locales`.

**Rationale**:
- `routing.locales` already exports the canonical list: `["en", "es", "fr", "it", "de", "pt", "nl", "pl", "sv", "el"]`
- At build time, Next.js generates one static HTML file per locale
- Zero runtime compute cost — CDN-cacheable with `Cache-Control: public, max-age=31536000, stale-while-revalidate`
- next-intl v3's `getTranslations()` is compatible with static generation when called at the module level in RSC

**Implementation**:
```tsx
// app/[locale]/page.tsx
export async function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}
export const dynamic = 'force-static';
```

**Constraint**: Landing page must contain no dynamic server-rendered content (no auth checks, no API calls). Authentication redirect must be handled by middleware.

---

## 3. Middleware: Redirect Authenticated Users from Root

**Decision**: Update `middleware.ts` to redirect authenticated users who hit `/{locale}` (root path) to `/{locale}/home`.

**Rationale**:
- The existing middleware already checks `request.auth` for protected routes
- Adding a root-path check keeps the logic in one place
- Static generation of `app/[locale]/page.tsx` is maintained — no auth check in the page component needed

**Pattern**:
```ts
// In middleware auth callback:
const isRoot = pathname === `/${locale}`;
if (session && isRoot) {
  return NextResponse.redirect(new URL(`/${locale}/home`, request.url));
}
```

---

## 4. Onboarding State: Backend vs. Client-Side

**Decision**: Store `onboarding_completed: boolean` in the PostgreSQL `users` table, surfaced via `UserProfile` response and updatable via `PATCH /api/v1/auth/me`.

**Rationale**:
- Persistent across devices and sessions — user who skips on mobile shouldn't see tour on desktop
- Consistent with existing `preferred_currency` pattern for profile fields
- Simple boolean avoids complexity of step-tracking on the server

**What stays client-side**: Current step number within the tour (not persisted). If user reloads mid-tour, they restart from Step 1.

**Migration**: Single Alembic migration + Go struct update + handler extension. Low-risk additive change.

---

## 5. Shadcn/ui Components to Install

**Decision**: Install `accordion` and `table` via `npx shadcn@latest add accordion table`.

**Rationale**:
- Accordion: used for FAQ section — built on Radix UI, accessible by default (WAI-ARIA 1.1)
- Table: used for pricing tier comparison grid

Already installed and reusable: `button`, `badge`, `card`, `dialog` (upgrade modal), `tooltip` (onboarding overlays).

---

## 6. SEO: Next.js Metadata API + Sitemap + robots.txt

**Decision**: Use Next.js built-in `generateMetadata()`, `app/sitemap.ts`, and `app/robots.ts`.

**Rationale**:
- Zero dependencies — built into Next.js 15
- `generateMetadata` receives `{ params: { locale } }` allowing per-locale title/description/OG tags
- `alternates.languages` in Metadata generates `<link rel="alternate" hreflang>` tags automatically
- `app/sitemap.ts` exporting `MetadataRoute.Sitemap` generates `/sitemap.xml` at build time
- `app/robots.ts` generates `/robots.txt`

**Sitemap structure**: 10 locale entries for `/`, each with `changeFrequency: 'monthly'` and `priority: 1`.

---

## 7. Hero Animation (CSS-only)

**Decision**: Implement hero property card animation using CSS `@keyframes` + Tailwind custom utilities.

**Rationale**:
- No JavaScript execution cost — animation runs on GPU compositor thread
- Core Web Vitals: no TBT (Total Blocking Time) impact
- Implemented as a floating/scaling card mockup with `animation: float 3s ease-in-out infinite`

**Pattern**: Define `animate-float` in `tailwind.config.ts` extending the `animation` and `keyframes` keys.

---

## 8. Landing Page i18n Keys Structure

**Decision**: Add a dedicated `landing` namespace to each `messages/{locale}.json` file.

**Structure** (English):
```json
{
  "landing": {
    "nav": { "logo": "EstateGap", "login": "Sign In", "cta": "Start for Free" },
    "hero": {
      "headline": "Find Your Next Property Deal — Powered by AI",
      "subheadline": "AI-driven property search, real-time deal scoring, and instant alerts across 30+ portals in Europe and the US.",
      "cta_primary": "Start for Free",
      "cta_secondary": "See How It Works"
    },
    "features": {
      "title": "Everything You Need to Find the Right Deal",
      "items": [
        { "title": "AI-Powered Search", "body": "Describe what you want in plain language..." },
        { "title": "Deal Scoring", "body": "LightGBM models score every listing..." },
        { "title": "Multi-Country Coverage", "body": "30+ portals across Europe and the US..." },
        { "title": "Real-Time Alerts", "body": "Get notified the moment a matching deal appears..." }
      ]
    },
    "pricing": { ... },
    "testimonials": { ... },
    "faq": { "items": [...] }
  },
  "onboarding": {
    "step1": { "title": "Find Your First Deal", "body": "Tell the AI what you're looking for...", "cta": "Start Searching" },
    "step2": { "title": "Set Up an Alert", "body": "Never miss a deal...", "cta": "Create Alert" },
    "step3": { "title": "Explore Your Dashboard", "body": "Track market trends...", "cta": "Go to Dashboard" },
    "skip": "Skip Tour",
    "upgrade": { "title": "Unlock More", "body": "Upgrade to Pro to get unlimited alerts...", "cta": "Upgrade Now" }
  }
}
```

---

## 9. Pre-filled Alert Form (Step 2 of Onboarding)

**Decision**: Pass chat-extracted criteria to the alerts page via URL query parameters.

**Rationale**:
- Stateless approach — no shared store needed between onboarding controller and the alerts form
- The `chatStore` already stores `criteria` (structured search criteria) per session
- After Step 1 chat interaction, the onboarding hook reads criteria from `chatStore` and encodes them as `?country=FR&maxPrice=300000&...` when navigating to `/alerts`
- The alerts page already uses `react-hook-form` with Zod; `useSearchParams()` can pre-populate form defaults

---

## 10. Upgrade Modal at Onboarding End

**Decision**: Use `shadcn Dialog` component (already installed) for the upgrade modal.

**Rationale**: Already available, accessible, controlled open/close state with Zustand.

**Content**: A condensed pricing comparison (3 key tiers: Free vs. Pro vs. Global) with CTA buttons linking to `/register?tier=pro` and `/register?tier=global`. No Stripe checkout initiated directly from this modal.
