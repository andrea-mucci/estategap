# Feature Specification: Landing Page & User Onboarding

**Feature Branch**: `027-landing-onboarding`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Build the public marketing landing page and new user onboarding flow."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Marketing Landing Page for New Visitors (Priority: P1)

A prospective user arrives at estategap.com without being signed in. They see a compelling marketing page that explains what EstateGap does, shows pricing options, and has a clear call-to-action to register.

**Why this priority**: Without a landing page, new users have no context about the product before signing up. This is the top-of-funnel entry point and directly drives conversions.

**Independent Test**: Can be fully tested by visiting `/{locale}/` without a session. Delivers a complete marketing experience without any backend dependency.

**Acceptance Scenarios**:

1. **Given** a visitor lands on `/{locale}/` with no session, **When** the page loads, **Then** a full marketing page is shown with hero, features, pricing, testimonials, FAQ, and CTA buttons — not the chat interface.
2. **Given** a visitor on the landing page clicks "Start for Free" (Free tier CTA), **When** the button is clicked, **Then** they are navigated to `/register?tier=free`.
3. **Given** a visitor on the landing page clicks "Get Pro" (Pro tier CTA), **When** the button is clicked, **Then** they are navigated to `/register?tier=pro`.
4. **Given** an authenticated user visits `/{locale}/`, **When** the page loads, **Then** they are redirected to `/{locale}/home`.
5. **Given** a visitor using a screen reader, **When** navigating the FAQ accordion, **Then** keyboard focus and ARIA attributes work correctly.
6. **Given** the browser locale is `es`, **When** the page loads at `/es/`, **Then** all landing page content is rendered in Spanish.

---

### User Story 2 - Onboarding Tour for New Registrations (Priority: P2)

A user completes registration for the first time. After login, they are guided through a 3-step interactive tour showing the AI chat, alert creation, and dashboard features before being invited to upgrade.

**Why this priority**: Onboarding reduces time-to-value, increases feature adoption, and improves trial-to-paid conversion — but the landing page must exist first to drive registrations.

**Independent Test**: Can be fully tested by registering a new account (or setting `onboarding_completed = false` via admin), logging in, and walking through all 3 steps. Delivers a guided first-use experience independently of the landing page.

**Acceptance Scenarios**:

1. **Given** a newly registered user logs in for the first time, **When** they reach the home page, **Then** the onboarding tour starts automatically with Step 1 (AI Chat introduction).
2. **Given** the tour is active at any step, **When** the user clicks "Skip", **Then** the tour closes, the upgrade modal is dismissed, and `onboarding_completed` is set to `true` on the user profile.
3. **Given** Step 1 is shown, **When** the user interacts with the chat (sends a message), **Then** Step 2 is unlocked and the user is navigated to `/alerts` with pre-filled criteria from the chat.
4. **Given** Step 2 is shown on the alerts page, **When** the user saves or skips the alert, **Then** Step 3 is shown on the dashboard with tooltip overlays highlighting key cards.
5. **Given** Step 3 is completed, **When** the dashboard tour ends, **Then** an upgrade prompt modal appears comparing tiers with CTA to checkout.
6. **Given** a user who has already completed onboarding logs in, **When** they reach the home page, **Then** no tour is shown.

---

### User Story 3 - SEO-Optimized Multilingual Landing Page (Priority: P3)

Search engines index all locale variants of the landing page. Each locale has unique metadata, canonical links, and hreflang tags. A sitemap.xml lists all public URLs.

**Why this priority**: Organic search discovery is a key acquisition channel; however, the functional landing page can be shipped first, with SEO optimization as an enhancement.

**Independent Test**: Can be validated independently using Lighthouse audits, crawlers, and `curl` on `sitemap.xml` and `robots.txt` without any user authentication.

**Acceptance Scenarios**:

1. **Given** Lighthouse runs against `/{locale}/`, **When** the audit completes, **Then** Performance score > 90, SEO score > 95, Accessibility score > 90.
2. **Given** a request to `/sitemap.xml`, **When** the response is returned, **Then** all 10 locale URLs for the landing page are listed.
3. **Given** a request to `/robots.txt`, **When** the response is returned, **Then** it allows public pages and points to the sitemap.
4. **Given** the page HTML for `/en/`, **When** inspected, **Then** `<link rel="alternate" hreflang="es" href="/es/">` (and all other locales) is present.

---

### Edge Cases

- What happens when the user closes the browser mid-tour? → Tour restarts from Step 1 (state is server-side, `onboarding_completed` remains `false`).
- What if the API call to mark `onboarding_completed = true` fails on skip? → Skip is optimistic; a retry is queued. User is not blocked from using the app.
- What if a user tries to access `/en/onboarding` directly without being authenticated? → Redirect to `/en/login?callbackUrl=/en/onboarding`.
- What if a locale is unsupported by the landing page i18n keys? → Fall back to English content.
- What happens on very slow 3G connections during the tour? → Tour overlay shows skeleton placeholders while navigating between steps.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST display a marketing landing page at `/{locale}/` for unauthenticated visitors, separate from the authenticated app experience.
- **FR-002**: The landing page MUST include: hero section, feature highlights (4 features), pricing table (5 tiers: Free/Basic/Pro/Global/API), testimonials section, FAQ accordion, and navigation with CTA buttons.
- **FR-003**: All landing page copy MUST be available in at least English, Spanish, and French from internationalization message files.
- **FR-004**: The landing page MUST use only static generation — no server-side rendering or client-side data fetching for page content.
- **FR-005**: Each pricing tier CTA MUST link to `/register?tier={tier}` to pre-select the tier during registration.
- **FR-006**: The system MUST generate a `sitemap.xml` listing all public locale variants of the landing page and a `robots.txt` that permits crawling of public pages.
- **FR-007**: The system MUST redirect authenticated users who visit `/{locale}/` to `/{locale}/home`.
- **FR-008**: After first-time registration, the user profile's `onboarding_completed` field MUST be set to `false` and the onboarding tour MUST start automatically on next page load.
- **FR-009**: The onboarding tour MUST consist of exactly 3 steps: (1) AI Chat introduction with highlighted chat input, (2) Alert setup with form pre-filled from chat criteria, (3) Dashboard feature highlights with tooltip overlays.
- **FR-010**: A "Skip" button MUST be visible at every step of the onboarding tour and MUST mark `onboarding_completed = true` on the user profile when clicked.
- **FR-011**: After completing all 3 onboarding steps, the system MUST display a subscription upgrade modal comparing tier features with CTA links to checkout.
- **FR-012**: The system MUST NOT show the onboarding tour to users who have `onboarding_completed = true`.
- **FR-013**: The backend PATCH `/api/v1/auth/me` endpoint MUST accept and persist the `onboarding_completed` boolean field.

### Key Entities *(include if feature involves data)*

- **User** (extended): Adds `onboarding_completed: boolean` field (default `false` for new registrations). Persisted in the `users` table and returned in `UserProfile` responses.
- **LandingContent**: Structured i18n message keys for each landing section (hero, features, pricing tiers, testimonials, FAQ items). Lives in `messages/{locale}.json`.
- **PricingTier**: Logical entity representing a subscription tier's marketing attributes (name, price, features list, highlighted flag, CTA label). Defined as a constant in frontend code, not fetched from the API.
- **OnboardingStep**: Enum of values `CHAT | ALERT | DASHBOARD`. Tracks current tour position in client state; the only server-persisted state is `onboarding_completed`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The landing page achieves Lighthouse scores of Performance > 90, SEO > 95, and Accessibility > 90 on mobile and desktop profiles.
- **SC-002**: The landing page fully loads in under 2 seconds on a simulated 3G connection (throttled network in Lighthouse).
- **SC-003**: A new user completing all 3 onboarding steps finishes the tour in under 2 minutes.
- **SC-004**: All CTA buttons on the landing page navigate to the correct registration URL with the correct `tier` query parameter on click.
- **SC-005**: The Skip button is reachable within 1 click at every onboarding step and correctly marks the tour as complete.
- **SC-006**: All 10 supported locale variants of the landing page render correct translated content with no untranslated English fallback strings visible.
- **SC-007**: `sitemap.xml` returns HTTP 200 and lists all public locale URLs. `robots.txt` returns HTTP 200.

## Assumptions

- The existing user registration flow (`/register`) and API (`POST /api/v1/auth/register`) are already functional; this feature adds the `tier` query parameter handling and `onboarding_completed` initialization.
- The `preferred_currency` update via `PATCH /api/v1/auth/me` is the model for extending the endpoint with the `onboarding_completed` field.
- Testimonials content is fictional/placeholder at launch (no external review system integration required).
- The hero animation is a CSS-only animated property card mockup — no video file hosting or streaming is required.
- The upgrade modal at onboarding end does NOT need to trigger a Stripe checkout directly — it links to the existing subscription/checkout page.
- Mobile-first responsive design is applied across all landing sections using the existing Tailwind CSS 4 configuration.
- The driver.js tour library is added as a new frontend dependency; no backend changes are needed to support driver.js itself.
- The existing `next-intl` routing (10 locales, `localePrefix: "always"`) is the foundation for multilingual landing page delivery.
