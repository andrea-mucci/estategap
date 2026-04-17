# Data Model: Landing Page & User Onboarding

**Feature**: 027-landing-onboarding
**Phase**: 1 — Design
**Date**: 2026-04-17

---

## Entity Changes

### 1. User (Extended)

**Change**: Add `onboarding_completed` boolean column.

**PostgreSQL migration** (`services/pipeline/alembic/versions/027_add_onboarding_completed.py`):
```sql
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE;
```

**Go struct** (`libs/pkg/models/user.go`):
```go
type User struct {
    // ... existing fields ...
    OnboardingCompleted bool `json:"onboarding_completed" db:"onboarding_completed"`
}
```

**SQLAlchemy model** (`services/pipeline/src/pipeline/db/models.py`):
```python
onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

**HTTP response payload** (`services/api-gateway/internal/handler/common.go`):
```go
type userProfilePayload struct {
    // ... existing fields ...
    OnboardingCompleted bool `json:"onboarding_completed"`
}
```

**Default**: `FALSE` for all existing users. New registrations default to `FALSE` (tour shown on first login). Setting to `TRUE` is idempotent (skip or complete).

**Constraints**:
- NOT NULL
- Default `FALSE`
- No unique constraint — purely boolean per user

---

### 2. LandingContent (i18n — no DB entity)

Landing page content is **not** stored in the database. It lives in `frontend/src/messages/{locale}.json` under the `landing` namespace. This includes:

| Key Path | Type | Description |
|----------|------|-------------|
| `landing.nav.*` | string | Navigation bar labels |
| `landing.hero.*` | string | Hero headline, subheadline, CTA labels |
| `landing.features.items[]` | object[] | Feature card title + body pairs |
| `landing.pricing.tiers[]` | object[] | Tier name, price, feature list, highlighted flag |
| `landing.testimonials.items[]` | object[] | Testimonial quote, author, role, company |
| `landing.faq.items[]` | object[] | FAQ question + answer pairs |
| `onboarding.*` | string | Tour step labels, skip label, upgrade prompt |

**Required locales at launch**: `en`, `es`, `fr` (minimum per spec). All 10 locales will have the `landing` and `onboarding` namespaces added; non-translated locales fall back to `en`.

---

### 3. PricingTier (Frontend Constant — no DB entity)

Defined as a TypeScript constant array in `frontend/src/lib/pricing.ts`. Not fetched from the API.

```ts
type PricingTier = {
  id: 'free' | 'basic' | 'pro' | 'global' | 'api';
  nameKey: string;         // i18n key
  price: number | null;    // null = "Contact us"
  currency: 'EUR';
  billingPeriod: 'month';
  featuresKey: string[];   // i18n keys for feature list items
  highlighted: boolean;    // true = visually emphasized column
  ctaKey: string;          // i18n key for CTA button label
};
```

**Tiers**:

| id | Price/month | Highlighted | CTA Target |
|----|------------|-------------|------------|
| free | €0 | false | `/register?tier=free` |
| basic | €19 | false | `/register?tier=basic` |
| pro | €49 | true | `/register?tier=pro` |
| global | €99 | false | `/register?tier=global` |
| api | null | false | `/contact?subject=api` |

---

### 4. OnboardingStep (Client-Side Enum — no DB entity)

```ts
// frontend/src/types/onboarding.ts
export type OnboardingStep = 'CHAT' | 'ALERT' | 'DASHBOARD' | 'COMPLETE';

export interface OnboardingState {
  active: boolean;
  currentStep: OnboardingStep;
  chatCriteria: Record<string, unknown> | null;  // Captured from chatStore after Step 1
}
```

**State management**: Held in a transient `onboardingStore` (Zustand, no persistence). Initialized from `session.user.onboarding_completed`. If page is refreshed mid-tour, `onboarding_completed = false` triggers restart from `CHAT`.

---

## API Contract Changes

### PATCH /api/v1/auth/me (Extended)

**Existing behavior**: Accepts `{ preferred_currency: string }`.

**New behavior**: Also accepts `{ onboarding_completed: boolean }`.

**Request body** (extended):
```json
{
  "preferred_currency": "EUR",
  "onboarding_completed": true
}
```

Both fields remain optional. Each update is applied independently (partial update semantics preserved).

**Go handler change**: Extend request struct:
```go
var req struct {
    PreferredCurrency   string `json:"preferred_currency"`
    OnboardingCompleted *bool  `json:"onboarding_completed"`
}
```
Use pointer-to-bool so the zero value (`false`) is distinguishable from "not provided".

**Repository method added**:
```go
func (r *UsersRepository) UpdateOnboardingCompleted(ctx context.Context, userID pgtype.UUID, completed bool) error
```

---

## State Transitions

```
New Registration
      │
      ▼
onboarding_completed = false
      │
      ├─ First login → tour starts (Step: CHAT)
      │       │
      │       ├─ Chat interaction → Step: ALERT (criteria captured)
      │       │       │
      │       │       ├─ Alert saved/skipped → Step: DASHBOARD
      │       │       │       │
      │       │       │       └─ Tour complete → upgrade modal
      │       │       │               │
      │       │       │               └─ Modal dismissed/CTA clicked
      │       │       │                       │
      │       │       │                       ▼
      │       │       │               onboarding_completed = true
      │       │       │
      │       │       └─ Skip at Step: ALERT
      │       │               │
      │       │               ▼
      │       │       onboarding_completed = true
      │       │
      │       └─ Skip at Step: CHAT
      │               │
      │               ▼
      │       onboarding_completed = true
      │
      └─ Subsequent logins (onboarding_completed = true) → no tour
```
