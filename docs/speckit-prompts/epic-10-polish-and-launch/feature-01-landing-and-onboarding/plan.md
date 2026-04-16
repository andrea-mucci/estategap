# Feature: Landing Page & User Onboarding

## /plan prompt

```
Implement with these technical decisions:

## Landing Page
- Next.js static page (app/[locale]/page.tsx for unauthenticated users, app/[locale]/(protected)/page.tsx for authenticated)
- Static generation (generateStaticParams for locales) for maximum performance
- Hero: large headline + subtitle + CTA button + animated property card mockup (CSS animation, no JS)
- Features: alternating left/right sections with illustrations (SVG)
- Pricing: shadcn Table component with tier comparison. CTA per tier links to /register?tier=pro
- FAQ: shadcn Accordion component. Content from i18n JSON.
- SEO: Next.js Metadata API with per-locale titles and descriptions. Sitemap.xml. robots.txt.

## Onboarding
- Onboarding state stored in user profile (onboarding_completed: boolean)
- Tour library: driver.js (lightweight, no jQuery) for step-by-step highlighting
- Step 1: Navigate to / (home), highlight chat input, auto-focus
- Step 2: After first conversation completes, navigate to /alerts, show pre-filled form
- Step 3: Navigate to /dashboard, highlight key cards with driver.js popover
- Skip: button in tour overlay. Sets onboarding_completed = true via API.
- Upgrade prompt: modal at end with tier comparison and CTA to checkout.
```
