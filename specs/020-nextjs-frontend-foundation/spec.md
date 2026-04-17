# Feature Specification: Next.js Frontend Foundation

**Feature Branch**: `020-nextjs-frontend-foundation`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Set up the Next.js frontend with authentication, i18n, API client, and WebSocket integration."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Language-Switching Navigation (Priority: P1)

A visitor arrives at the application and can immediately select their preferred language from a header switcher. All visible text updates instantly without a page reload or loss of navigation state.

**Why this priority**: Language accessibility is a prerequisite for all other user interactions; without it, non-English speakers cannot use any feature.

**Independent Test**: Open the app, click the language switcher, select a non-English language — all text on the page updates and the URL reflects the new locale.

**Acceptance Scenarios**:

1. **Given** the user is on any page, **When** they select a language from the header switcher, **Then** all UI strings update immediately without a full page reload.
2. **Given** the user navigates to a new page after switching language, **Then** the selected language persists.
3. **Given** 10 supported languages (en, es, fr, it, de, pt, nl, pl, sv, el), **When** each is selected, **Then** the interface renders correctly in that language.

---

### User Story 2 - Authentication Flows (Priority: P1)

A new user can register with email+password, an existing user can log in with credentials or Google OAuth, and authenticated users can access protected pages while unauthenticated users are redirected to `/login`.

**Why this priority**: Authentication gates all product features; without it no subscriber can access any protected functionality.

**Independent Test**: Register a new account, log out, log in again, access a protected route — all transitions succeed and the user menu shows subscription tier.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user visits a protected page, **When** the page loads, **Then** they are redirected to `/login`.
2. **Given** a valid email+password, **When** the user submits the login form, **Then** they are authenticated and redirected to the dashboard.
3. **Given** the user initiates Google OAuth, **When** they complete the OAuth flow, **Then** they are authenticated and their session includes subscription tier info.
4. **Given** an authenticated user, **When** they view the user menu, **Then** their subscription tier is displayed.

---

### User Story 3 - API Data Fetching with Loading/Error States (Priority: P2)

An authenticated user browsing listings, zones, or alerts sees loading skeletons while data is being fetched and friendly error messages when a request fails. Data is cached and refetched automatically.

**Why this priority**: Core product data display depends on reliable API integration with good UX feedback.

**Independent Test**: Navigate to any data page, observe loading state, see data render; simulate network failure and observe error message.

**Acceptance Scenarios**:

1. **Given** a user navigates to a data page, **When** the API request is in flight, **Then** a loading skeleton or spinner is displayed.
2. **Given** the API returns an error, **When** the page renders, **Then** a user-friendly error message is shown with a retry option.
3. **Given** data has been fetched once, **When** the user revisits within the cache window, **Then** cached data is shown immediately.

---

### User Story 4 - Real-Time Chat and Notifications via WebSocket (Priority: P2)

An authenticated user on any page receives real-time notifications and can interact with the AI chat. The WebSocket connects automatically on authenticated page load and reconnects silently if disconnected.

**Why this priority**: Real-time features are core differentiators; they depend on reliable WebSocket connectivity.

**Independent Test**: Load any authenticated page, confirm WebSocket handshake in DevTools, disconnect network briefly, reconnect — WebSocket re-establishes automatically and pending messages arrive.

**Acceptance Scenarios**:

1. **Given** a user is authenticated, **When** they load a page, **Then** a WebSocket connection is established automatically.
2. **Given** the WebSocket disconnects, **When** the connection drops, **Then** the client retries with exponential backoff (1s, 2s, 4s, 8s, max 30s) until reconnected.
3. **Given** an incoming notification message, **When** it arrives over the WebSocket, **Then** the notification store is updated and a toast/badge appears.

---

### User Story 5 - Responsive Layout (Priority: P3)

The application header, collapsible sidebar, and main content area adapt correctly across mobile, tablet, and desktop viewport sizes. The sidebar collapses to a drawer/icon-only mode on mobile.

**Why this priority**: Responsive layout is essential for usability across devices but does not block core functionality.

**Independent Test**: Resize the browser from 320px to 1440px — the sidebar collapses on mobile and expands on desktop; the header and content area reflow correctly.

**Acceptance Scenarios**:

1. **Given** a mobile viewport (< 768px), **When** the page loads, **Then** the sidebar is collapsed by default.
2. **Given** a desktop viewport (≥ 1024px), **When** the page loads, **Then** the sidebar is expanded by default.
3. **Given** any viewport, **When** the user toggles the sidebar, **Then** it opens/closes with a smooth animation.

---

### Edge Cases

- What happens when the user's JWT expires mid-session? → Session should be refreshed silently; if refresh fails, redirect to `/login`.
- How does the app handle an unsupported locale in the URL? → Redirect to the default locale (en).
- What if the OpenAPI spec is unavailable during code generation? → Build fails with a clear error; generated types are committed to the repository.
- How does the WebSocket behave when the browser tab is backgrounded? → Heartbeat (ping every 25s) keeps the connection alive; reconnect on visibility change if disconnected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST render all UI strings from locale-specific message files, with no hardcoded strings in components.
- **FR-002**: The system MUST support 10 languages (en, es, fr, it, de, pt, nl, pl, sv, el) via URL-based locale routing (`/[locale]/...`).
- **FR-003**: Users MUST be able to switch language from the header without a full page reload.
- **FR-004**: The system MUST protect all routes under `/(protected)/` and redirect unauthenticated users to `/[locale]/login`.
- **FR-005**: The system MUST support email+password registration and login.
- **FR-006**: The system MUST support Google OAuth login.
- **FR-007**: The authenticated session MUST include the user's subscription tier.
- **FR-008**: The system MUST auto-generate TypeScript API types from the project's OpenAPI spec.
- **FR-009**: All API calls MUST include the JWT access token and display loading and error states.
- **FR-010**: The WebSocket client MUST connect automatically on authenticated page load.
- **FR-011**: The WebSocket client MUST auto-reconnect with exponential backoff (1s → 2s → 4s → 8s → max 30s).
- **FR-012**: The WebSocket client MUST send a heartbeat ping every 25 seconds.
- **FR-013**: The layout MUST include a header (logo, language switcher, user menu) and a collapsible sidebar (Home/Search, Dashboard, Zones, Alerts, Portfolio, Admin).
- **FR-014**: The sidebar MUST collapse by default on mobile viewports and be expandable by the user.
- **FR-015**: Lighthouse performance score MUST be > 90 and accessibility score MUST be > 85 on production build.

### Key Entities

- **User**: Authenticated principal with email, name, avatar, subscription tier (free/pro/enterprise), and JWT session.
- **Locale**: One of 10 supported language codes; determines URL segment and message file loaded.
- **ChatMessage**: A message in the AI chat session (role: user|assistant, content, timestamp, session ID).
- **ChatSession**: A stateful AI conversation linked to a user (criteria, messages, metadata).
- **Notification**: A real-time event delivered via WebSocket (type, payload, read status, timestamp).
- **APIClient**: A typed HTTP client derived from the OpenAPI spec, authenticated with the user's JWT.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 10 languages render correctly; a native speaker can navigate without encountering untranslated strings.
- **SC-002**: Language switch completes in under 200ms (no full page reload).
- **SC-003**: Login and registration flows complete in under 3 steps from landing page.
- **SC-004**: 100% of protected routes redirect unauthenticated users to the login page.
- **SC-005**: WebSocket reconnects within 30 seconds after a connection drop (exponential backoff ceiling).
- **SC-006**: All API interactions display a loading state within 100ms of initiation.
- **SC-007**: Production Lighthouse scores: Performance > 90, Accessibility > 85.
- **SC-008**: Sidebar collapses and expands without layout shift on all viewport sizes.

## Assumptions

- The backend API Gateway exposes an OpenAPI 3.x spec that is available at build time for type generation.
- The WebSocket endpoint is exposed by the existing `019-ws-chat-realtime` service.
- Google OAuth credentials (client ID and secret) are available as environment variables.
- The subscription tier field is included in the JWT claims returned by the auth gateway.
- Admin navigation item is visible only to users with the admin role (role check on the client).
- Mobile-first breakpoints: mobile < 768px, tablet 768–1023px, desktop ≥ 1024px.
- The application is deployed as a Node.js server (not static export) to support RSC and middleware.
- Initial i18n translations are provided in English; other languages may use English as fallback for missing keys.
