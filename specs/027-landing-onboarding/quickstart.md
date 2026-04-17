# Quickstart: Landing Page & User Onboarding (027)

**Feature Branch**: `027-landing-onboarding`
**Date**: 2026-04-17

---

## Prerequisites

- Go 1.23 toolchain
- Node.js 22 + npm
- Docker / docker-compose (for PostgreSQL + Redis)
- `uv` (Python package manager, for Alembic migrations)

---

## 1. Run the Database Migration

```bash
# From repo root — apply the onboarding_completed column migration
cd services/pipeline
uv run alembic upgrade head
```

The migration adds `onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE` to the `users` table.

---

## 2. Install New Frontend Dependencies

```bash
cd frontend

# Install driver.js tour library
npm install driver.js

# Add shadcn/ui components not yet installed
npx shadcn@latest add accordion
npx shadcn@latest add table
```

After running `shadcn add`, verify new files appear at:
- `src/components/ui/accordion.tsx`
- `src/components/ui/table.tsx`

---

## 3. Regenerate Frontend API Types

The OpenAPI spec gains new fields (`onboarding_completed`, `UpdateUserProfileRequest`). Regenerate the TypeScript types:

```bash
cd frontend
npm run generate:types
```

Verify `src/types/api.ts` now includes `onboarding_completed: boolean` on `UserProfile` and the new `UpdateUserProfileRequest` type.

---

## 4. Start Development Servers

```bash
# Terminal 1 — API Gateway (Go)
cd services/api-gateway
go run ./cmd/main.go

# Terminal 2 — Frontend (Next.js)
cd frontend
npm run dev
```

---

## 5. Verify the Landing Page

1. Open a browser in **incognito mode** (no session)
2. Navigate to `http://localhost:3000/en`
3. You should see the **marketing landing page** (hero, features, pricing, FAQ)
4. Click "Start for Free" → should navigate to `/en/register?tier=free`
5. Navigate to `http://localhost:3000/es` → verify Spanish content

---

## 6. Verify the Onboarding Tour

1. Register a new account at `http://localhost:3000/en/register`
2. After registration + login, you should land on `/en/home`
3. The driver.js tour should start automatically (Step 1: chat input highlighted)
4. Test **Skip** — verify `PATCH /api/v1/auth/me` is called with `{ onboarding_completed: true }`
5. Walk through all 3 steps → verify upgrade modal appears after Step 3
6. Log out and log back in → verify tour does NOT appear again

---

## 7. SEO Checks

```bash
# Build and check sitemap
cd frontend
npm run build
curl http://localhost:3000/sitemap.xml   # should list 10 locale URLs
curl http://localhost:3000/robots.txt   # should allow /en/, /es/, etc.
```

Run Lighthouse on the production build:
```bash
npm install -g lighthouse
lighthouse http://localhost:3000/en --output html --output-path ./lighthouse-report.html
```
Target: Performance > 90, SEO > 95, Accessibility > 90.

---

## Key File Locations

| File | Purpose |
|------|---------|
| `frontend/src/app/[locale]/page.tsx` | Marketing landing page (static, public) |
| `frontend/src/app/sitemap.ts` | Dynamic sitemap generator |
| `frontend/src/app/robots.ts` | robots.txt generator |
| `frontend/src/components/landing/` | Landing page section components |
| `frontend/src/components/onboarding/` | OnboardingTour + UpgradeModal |
| `frontend/src/hooks/useOnboarding.ts` | Tour logic hook |
| `frontend/src/stores/onboardingStore.ts` | Transient onboarding state |
| `frontend/src/lib/pricing.ts` | PricingTier constants |
| `frontend/src/messages/en.json` | Add `landing` + `onboarding` i18n keys |
| `frontend/middleware.ts` | Add root redirect for authenticated users |
| `libs/pkg/models/user.go` | Add `OnboardingCompleted bool` field |
| `services/api-gateway/internal/handler/auth.go` | Extend PatchMe handler |
| `services/api-gateway/internal/repository/users.go` | Add UpdateOnboardingCompleted |
| `services/api-gateway/openapi.yaml` | Add PATCH spec + new fields |
| `services/pipeline/alembic/versions/027_*.py` | DB migration |
| `services/pipeline/src/pipeline/db/models.py` | Add SQLAlchemy column |
