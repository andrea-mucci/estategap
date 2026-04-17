# Tasks: Landing Page & User Onboarding

**Input**: Design documents from `/specs/027-landing-onboarding/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on other in-progress tasks)
- **[Story]**: Which user story this task belongs to (US1 = Landing Page, US2 = Onboarding Tour, US3 = SEO/Multilingual)
- Exact file paths are included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies and create directory scaffolding before any story work begins.

- [X] T001 Install driver.js tour library: `cd frontend && npm install driver.js`
- [X] T002 Install shadcn/ui accordion and table components: `cd frontend && npx shadcn@latest add accordion table` — verify files created at `frontend/src/components/ui/accordion.tsx` and `frontend/src/components/ui/table.tsx`
- [X] T003 [P] Create landing component directory `frontend/src/components/landing/` and onboarding component directory `frontend/src/components/onboarding/`
- [X] T004 [P] Create pricing constants in `frontend/src/lib/pricing.ts` — export `PRICING_TIERS: PricingTier[]` array for Free/Basic/Pro/Global/API tiers with id, price, highlighted flag, and `/register?tier={id}` CTA href

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend schema + API changes (needed by US2) and middleware + i18n setup (needed by US1 and US2). Must be fully complete before user story implementation begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create Alembic migration `services/pipeline/alembic/versions/027_add_onboarding_completed.py` — `upgrade()`: `op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))` / `downgrade()`: `op.drop_column('users', 'onboarding_completed')` — run `uv run alembic upgrade head` to verify
- [X] T006 [P] Add `onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)` to the `User` class in `services/pipeline/src/pipeline/db/models.py`
- [X] T007 [P] Add `OnboardingCompleted bool \`json:"onboarding_completed" db:"onboarding_completed"\`` field to the `User` struct in `libs/pkg/models/user.go`
- [X] T008 Add `UpdateOnboardingCompleted(ctx context.Context, userID pgtype.UUID, completed bool) error` method to `services/api-gateway/internal/repository/users.go` — SQL: `UPDATE users SET onboarding_completed = $1, updated_at = NOW() WHERE id = $2 AND deleted_at IS NULL`
- [X] T009 Extend `PatchMe` handler in `services/api-gateway/internal/handler/auth.go`: add `OnboardingCompleted *bool \`json:"onboarding_completed"\`` to request struct; after currency block, if non-nil call `UpdateOnboardingCompleted`; add `OnboardingCompleted bool` to `userProfilePayload` response struct (depends on T007, T008)
- [X] T010 Update `services/api-gateway/openapi.yaml`: add `onboarding_completed: boolean` (required) and `preferred_currency: string` to `UserProfile` schema; add `PATCH /api/v1/auth/me` entry with `UpdateUserProfileRequest` schema (fields: `preferred_currency`, `onboarding_completed`) per `contracts/openapi-patch.yaml` (depends on T009)
- [X] T011 Regenerate frontend TypeScript types: `cd frontend && npm run generate:types` — verify `UserProfile.onboarding_completed: boolean` and `UpdateUserProfileRequest` appear in `frontend/src/types/api.ts` (depends on T010)
- [X] T012 Update `frontend/middleware.ts` — in the `auth()` callback, after locale resolution: if `session` exists AND `pathname` equals `/${locale}`, return `NextResponse.redirect(new URL(\`/${locale}/home\`, request.url))` before existing protected-route checks
- [X] T013 Create Zustand onboarding store in `frontend/src/stores/onboardingStore.ts` — state: `active: boolean`, `currentStep: 'CHAT' | 'ALERT' | 'DASHBOARD' | 'COMPLETE'`, `chatCriteria: Record<string, unknown> | null`, `showUpgradeModal: boolean`; actions: `startTour()`, `advanceStep(criteria?)`, `completeTour()`, `skipTour()` — no persistence middleware (server is source of truth)
- [X] T014 Add `landing` and `onboarding` namespaces to all 10 locale message files in `frontend/src/messages/` — full translated content for `en.json`, `es.json`, `fr.json`; copy English values as placeholders for `it.json`, `de.json`, `pt.json`, `nl.json`, `pl.json`, `sv.json`, `el.json` — keys per `research.md` Section 8 structure

**Checkpoint**: Foundation ready — run `go build ./...` in `services/api-gateway`, `uv run alembic upgrade head` in pipeline, `npm run generate:types` in frontend. All must succeed before proceeding.

---

## Phase 3: User Story 1 — Marketing Landing Page (Priority: P1) 🎯 MVP

**Goal**: Unauthenticated visitors see a complete marketing page at `/{locale}/`. Authenticated users visiting `/{locale}/` are redirected to `/{locale}/home`.

**Independent Test**: Open incognito browser → `http://localhost:3000/en` → marketing page visible with hero, features, pricing (5 tiers), FAQ, CTA buttons. Click "Start for Free" → navigates to `/en/register?tier=free`. Log in, visit `/en` → redirected to `/en/home`.

- [X] T015 [P] [US1] Create `frontend/src/components/landing/LandingNav.tsx` — sticky public nav bar with EstateGap logo, locale switcher (next-intl `Link`), "Sign In" link to `/{locale}/login`, and "Start for Free" `Button` to `/{locale}/register?tier=free`; use `useTranslations('landing.nav')`
- [X] T016 [P] [US1] Create `frontend/src/components/landing/Hero.tsx` — H1 headline + subheadline paragraph + two CTA buttons (primary: `/register?tier=free`, secondary: anchor to `#features`); right-side CSS-animated property card mockup using Tailwind `animate-float` class; no JS animation libraries
- [X] T017 [P] [US1] Create `frontend/src/components/landing/Features.tsx` — map over `landing.features.items[]` i18n array; alternating layout (odd: text-left/SVG-right, even: SVG-left/text-right) using Tailwind flex/grid; one inline SVG React component per feature
- [X] T018 [P] [US1] Create `frontend/src/components/landing/Pricing.tsx` — import `PRICING_TIERS` from `lib/pricing.ts`; render with shadcn `<Table>` + `<TableHeader>` + `<TableBody>`; highlighted Pro tier column with distinct `bg-teal-50 ring-2 ring-teal-600` styling; each tier CTA: `<Button asChild><Link href={tier.ctaHref}>`
- [X] T019 [P] [US1] Create `frontend/src/components/landing/Testimonials.tsx` — grid of 3 shadcn `<Card>` testimonial cards using `landing.testimonials.items[]` i18n keys (quote, author, role, company); responsive: 1 col mobile, 3 col desktop
- [X] T020 [P] [US1] Create `frontend/src/components/landing/FAQ.tsx` — shadcn `<Accordion type="multiple">` with items from `landing.faq.items[]` i18n array; each item maps to `<AccordionItem>` + `<AccordionTrigger>` + `<AccordionContent>`
- [X] T021 [P] [US1] Create `frontend/src/components/landing/LandingFooter.tsx` — footer with links (Privacy Policy, Terms of Service, Contact, GitHub), locale switcher, and copyright line `© {year} EstateGap`
- [X] T022 [P] [US1] Add `animate-float` custom keyframe to `frontend/tailwind.config.ts` — `keyframes: { float: { '0%, 100%': { transform: 'translateY(0px)' }, '50%': { transform: 'translateY(-6px)' } } }`, `animation: { float: 'float 3s ease-in-out infinite' }`
- [X] T023 [US1] Rewrite `frontend/src/app/[locale]/page.tsx` as static marketing landing page — add `export const dynamic = 'force-static'`; add `export async function generateStaticParams()` returning `routing.locales.map(l => ({ locale: l }))`; compose `<LandingNav>`, `<Hero>`, `<Features id="features">`, `<Pricing>`, `<Testimonials>`, `<FAQ>`, `<LandingFooter>` (depends on T015–T022)

**Checkpoint**: `npm run dev` → visit `http://localhost:3000/en` unauthenticated → full marketing page renders. All 5 pricing CTA buttons navigate to correct `/register?tier={id}` URLs. Middleware test: log in → visit `/en` → redirected to `/en/home`.

---

## Phase 4: User Story 2 — Onboarding Tour for New Registrations (Priority: P2)

**Goal**: A newly registered user sees a 3-step driver.js tour (Chat → Alerts → Dashboard) with a Skip button at every step and an upgrade modal at the end. `onboarding_completed` is correctly persisted on skip or completion.

**Independent Test**: Register a new account (or reset `onboarding_completed = false` via psql) → log in → tour starts automatically at Step 1 → click Skip → `PATCH /api/v1/auth/me { onboarding_completed: true }` fires → log out → log in again → no tour shown.

- [X] T024 [P] [US2] Create `frontend/src/hooks/useOnboarding.ts` — reads `session.user.onboarding_completed` from NextAuth `useSession()`; on mount: if `!onboarding_completed` calls `onboardingStore.startTour()`; exports `{ active, currentStep, advance, skip }` where `skip()` calls `updateCurrentUser({ onboarding_completed: true })` from `lib/api.ts` then `onboardingStore.skipTour()`
- [X] T025 [P] [US2] Create `frontend/src/components/onboarding/UpgradeModal.tsx` — shadcn `<Dialog>` controlled by `onboardingStore.showUpgradeModal`; 3-tier comparison (Free / Pro / Global) with features list; CTAs: "Stay on Free" (close dialog + mark complete), "Upgrade to Pro" (`/register?tier=pro`), "Get Global" (`/register?tier=global`); on any close: call `updateCurrentUser({ onboarding_completed: true })`
- [X] T026 [US2] Create `frontend/src/components/onboarding/OnboardingTour.tsx` — `'use client'` component; lazy-imports driver.js + CSS inside `useEffect` to avoid SSR; reads from `onboardingStore`; Step 1 (`CHAT`): `driver.highlight({ element: '#chat-input', popover: { title, description, showButtons: ['next', 'close'] } })`; on chat message sent advance to `ALERT` step with criteria + `router.push('/alerts?...')`; Step 2 (`ALERT`): highlight `#alert-form` on `/alerts` page; on save/skip advance to `DASHBOARD` + `router.push('/dashboard')`; Step 3 (`DASHBOARD`): multi-element highlight of `#dashboard-summary-card`; on complete call `onboardingStore.completeTour()` to show `UpgradeModal` (depends on T024, T025, T013)
- [X] T027 [US2] Wire `<OnboardingTour />` and `<UpgradeModal />` into `frontend/src/app/[locale]/(protected)/layout.tsx` — import and render both components inside the layout body; they are no-ops when `onboarding_completed = true` (depends on T026)
- [X] T028 [P] [US2] Add `id="chat-input"` to the chat input wrapper element in `frontend/src/app/[locale]/(protected)/home/page.tsx` — specifically the container `<div>` wrapping the `<ChatInput>` component so driver.js can target it
- [X] T029 [US2] Update `frontend/src/app/[locale]/(protected)/alerts/page.tsx` — read `useSearchParams()` for `country`, `maxPrice`, `minArea`, `propertyType` query params; pass as `defaultValues` to `useForm()`; add `id="alert-form"` to the form element; scroll `#alert-form` into view on mount if any query param is present
- [X] T030 [P] [US2] Add `id="dashboard-summary-card"` to the first summary/stats card element in `frontend/src/app/[locale]/(protected)/dashboard/page.tsx` so driver.js can target it for the Step 3 highlight

**Checkpoint**: New user registers → logs in → tour overlay appears on `/home` with chat input highlighted and Skip visible → clicking Skip fires API call → `onboarding_completed` set to `true` in DB → re-login shows no tour. Full 3-step walk-through completes and shows upgrade modal.

---

## Phase 5: User Story 3 — SEO-Optimized Multilingual Landing Page (Priority: P3)

**Goal**: Search engines can discover and index all locale variants of the landing page. `/sitemap.xml` and `/robots.txt` are reachable. Lighthouse SEO score > 95.

**Independent Test**: `curl http://localhost:3000/sitemap.xml` → 200 response listing 10 locale URLs. `curl http://localhost:3000/robots.txt` → 200 with correct allow/disallow. `view-source:http://localhost:3000/en` → `<link rel="alternate" hreflang="es" href="...">` present for all locales.

- [X] T031 [P] [US3] Create `frontend/src/app/sitemap.ts` — export default function returning `MetadataRoute.Sitemap`; map `routing.locales` to entries: `{ url: \`https://estategap.com/${locale}\`, lastModified: new Date(), changeFrequency: 'monthly', priority: 1 }` with `alternates.languages` object listing all locale variants
- [X] T032 [P] [US3] Create `frontend/src/app/robots.ts` — export default function returning `MetadataRoute.Robots`; `rules: { userAgent: '*', allow: '/', disallow: ['/api/', '*/dashboard', '*/admin', '*/alerts', '*/portfolio'] }`; `sitemap: 'https://estategap.com/sitemap.xml'`
- [X] T033 [US3] Add `export async function generateMetadata({ params }: { params: Promise<{ locale: string }> })` to `frontend/src/app/[locale]/page.tsx` — per-locale `title`, `description`, `openGraph` title/description/locale; `alternates: { canonical: \`/${locale}\`, languages: Object.fromEntries(routing.locales.map(l => [l, \`/${l}\`])) }` for hreflang tags (depends on T023)

**Checkpoint**: `npm run build` succeeds. `curl /sitemap.xml` lists 10 locale entries. `curl /robots.txt` correct. `view-source:/en` has 10 `<link rel="alternate" hreflang>` tags. Lighthouse SEO score ≥ 95.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, accessibility review, and responsive testing across all stories.

- [ ] T034 [P] Run Lighthouse audit on production build at `http://localhost:3000/en` — record Performance, SEO, Accessibility scores; all must exceed 90 / 95 / 90 thresholds respectively; fix any failing items
- [ ] T035 [P] Verify `sitemap.xml` — `curl http://localhost:3000/sitemap.xml` returns HTTP 200; validate all 10 locale URLs (`/en`, `/es`, `/fr`, `/it`, `/de`, `/pt`, `/nl`, `/pl`, `/sv`, `/el`) are listed
- [ ] T036 [P] Verify `robots.txt` — `curl http://localhost:3000/robots.txt` returns HTTP 200; confirm `Sitemap:` directive points to `https://estategap.com/sitemap.xml`
- [ ] T037 Verify onboarding skip API call — register new account → log in → click Skip at Step 1 → open Network tab in DevTools → confirm `PATCH /api/v1/auth/me` with body `{ "onboarding_completed": true }` returns 200
- [ ] T038 Verify no tour repeat — complete T037 → log out → log in → confirm no driver.js overlay appears and `onboarding_completed = true` in DB
- [ ] T039 Verify responsive design — test landing page (`/en`) at 375px (mobile), 768px (tablet), and 1440px (desktop) breakpoints; verify hero layout, pricing table, and FAQ accordion render correctly at each breakpoint; fix any overflow or layout issues
- [ ] T040 [P] Verify all CTA buttons — on the landing page, confirm each of the 5 pricing tier CTA buttons navigates to `/en/register?tier=free`, `/en/register?tier=basic`, `/en/register?tier=pro`, `/en/register?tier=global`, `/en/contact?subject=api` respectively

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 Landing Page (Phase 3)**: Depends on Phase 2 (i18n keys, middleware, pricing constants)
- **US2 Onboarding Tour (Phase 4)**: Depends on Phase 2 (backend API, onboardingStore, types regenerated)
- **US3 SEO (Phase 5)**: Depends on Phase 3 (T023 page.tsx must exist before adding generateMetadata)
- **Polish (Phase 6)**: Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on US2 or US3
- **US2 (P2)**: Can start after Phase 2 in parallel with US1 — backend and store are foundational
- **US3 (P3)**: T031 and T032 can run in parallel with US1/US2; T033 depends on T023 (US1)

### Within Each User Story

- US1: Landing components T015–T022 can all run in parallel; T023 (page.tsx rewrite) waits for all components
- US2: T024 (hook) + T025 (modal) can run in parallel; T026 (tour controller) depends on both; T027 (wire into layout) depends on T026; T028/T030 can run in parallel with tour work
- US3: T031 + T032 are independent; T033 depends on T023

### Parallel Opportunities

- All Phase 1 tasks (T001–T004) can run in parallel
- T006 + T007 in Phase 2 can run in parallel (different files in different services)
- All 8 landing section components (T015–T022) can run in parallel within US1
- T024 (hook) + T025 (modal) can run in parallel within US2
- T028, T029, T030 (anchor IDs) can run in parallel within US2
- T031 + T032 (sitemap + robots) can run in parallel within US3
- T034–T040 validation tasks can largely run in parallel in Phase 6

---

## Parallel Example: User Story 1 (Landing Components)

```bash
# All 8 component/config tasks can be dispatched simultaneously:
Task T015: "Create LandingNav in frontend/src/components/landing/LandingNav.tsx"
Task T016: "Create Hero in frontend/src/components/landing/Hero.tsx"
Task T017: "Create Features in frontend/src/components/landing/Features.tsx"
Task T018: "Create Pricing in frontend/src/components/landing/Pricing.tsx"
Task T019: "Create Testimonials in frontend/src/components/landing/Testimonials.tsx"
Task T020: "Create FAQ in frontend/src/components/landing/FAQ.tsx"
Task T021: "Create LandingFooter in frontend/src/components/landing/LandingFooter.tsx"
Task T022: "Add animate-float keyframe to frontend/tailwind.config.ts"

# Then once all complete:
Task T023: "Rewrite frontend/src/app/[locale]/page.tsx as static marketing landing page"
```

## Parallel Example: User Story 2 (Onboarding Components)

```bash
# These can run in parallel:
Task T024: "Create useOnboarding hook in frontend/src/hooks/useOnboarding.ts"
Task T025: "Create UpgradeModal in frontend/src/components/onboarding/UpgradeModal.tsx"
Task T028: "Add id='chat-input' to home/page.tsx"
Task T030: "Add id='dashboard-summary-card' to dashboard/page.tsx"

# Then once T024 + T025 complete:
Task T026: "Create OnboardingTour in frontend/src/components/onboarding/OnboardingTour.tsx"

# Then:
Task T027: "Wire OnboardingTour + UpgradeModal into protected layout.tsx"
Task T029: "Add pre-fill query param handling to alerts/page.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only — Landing Page)

1. Complete **Phase 1: Setup** (T001–T004)
2. Complete **Phase 2: Foundational** (T005–T014) — especially T012 (middleware), T014 (i18n)
3. Complete **Phase 3: User Story 1** (T015–T023) — 8 components in parallel, then page.tsx
4. **STOP and VALIDATE**: Incognito browser → `/en` shows marketing page. Auth redirect works. All CTAs correct.
5. Deploy/demo the landing page independently

### Incremental Delivery

1. **Phase 1 + 2** → Infrastructure ready
2. **Phase 3 (US1)** → Marketing landing page live → Demo to stakeholders → Drive registrations
3. **Phase 4 (US2)** → Onboarding tour live → Improves trial conversion
4. **Phase 5 (US3)** → SEO + sitemap → Organic search visibility
5. **Phase 6** → Validation + polish → Ship

### Parallel Team Strategy

With 2+ developers after Phase 2:
- **Dev A**: US1 landing components (T015–T023)
- **Dev B**: US2 onboarding tour (T024–T030) + US3 SEO (T031–T033) — T031/T032 are quick wins

---

## Notes

- [P] tasks operate on different files with no in-flight dependencies — safe to parallelize
- [Story] labels map each task to a specific user story for traceability and independent delivery
- driver.js must be lazy-imported inside `useEffect` — never imported at module level (SSR will break)
- `export const dynamic = 'force-static'` on `app/[locale]/page.tsx` is required; any auth check in that file will break static generation
- The middleware handles authenticated user redirect — the landing page component stays auth-unaware
- `onboarding_completed` update is optimistic on skip — user is not blocked if the API call fails
- Run `npm run generate:types` (T011) before any frontend work that reads `UserProfile.onboarding_completed`
- Total tasks: **40** across 6 phases
