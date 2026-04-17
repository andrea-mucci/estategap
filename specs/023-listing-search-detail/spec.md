# Feature Specification: Listing Search & Detail Pages

**Feature Branch**: `023-listing-search-detail`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Build the listing search page with advanced filters and the listing detail page with full analysis."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Advanced Filtered Property Search (Priority: P1)

An investor opens the `/search` page and uses the filter sidebar to narrow listings by country, city (with autocomplete), zone, property type, price range, area range, bedrooms, deal tier, status, and source portal. Results update instantly as filters change. The URL reflects every active filter so the search can be bookmarked and shared. The investor toggles between a card grid (3 columns on desktop) and a list view. They sort by deal score to see the best opportunities first and scroll down to load more results via infinite scroll.

**Why this priority**: The search page is the primary discovery surface for investors. Without a working, filterable search, no other feature delivers value. Every filter directly maps to an investment decision (price budget, location, deal quality).

**Independent Test**: Can be fully tested by applying each of the 15+ filters, verifying URL params update, verifying results update without page reload, toggling views, changing sort order, and scrolling to load additional pages.

**Acceptance Scenarios**:

1. **Given** a logged-in user on `/search`, **When** the page loads, **Then** results for the default country are displayed in card grid view sorted by deal score.
2. **Given** filters are applied (e.g., city=Madrid, min_price=100000, bedrooms=3), **When** the user applies each filter, **Then** the URL params update to reflect the filter state and results refresh without a full page reload.
3. **Given** a shareable search URL with filter params, **When** another user opens the URL, **Then** the same filters are applied and the same result set is displayed.
4. **Given** results are displayed, **When** the user scrolls to the bottom of the page, **Then** the next page of results loads automatically and appends to the existing list.
5. **Given** results are displayed, **When** the user toggles between grid and list view, **Then** the layout changes immediately with no data re-fetch.
6. **Given** results are displayed, **When** the user changes the sort order, **Then** results re-sort without a full page reload.

---

### User Story 2 - Saved Search CRUD (Priority: P2)

An investor finds a filter combination they want to monitor regularly (e.g., Tier 1 deals in Barcelona under €400k). They save the search with a name. Later, they load a saved search from a dropdown to instantly restore all filters. They can delete saved searches they no longer need. Saved searches persist across devices.

**Why this priority**: Saved searches multiply the value of the filter system by enabling recurring workflows. They depend on P1 filters being functional but deliver independent value — the investor doesn't need to re-enter criteria each session.

**Independent Test**: Can be tested by saving a search, reloading the page (verifying filters restored), loading via dropdown, and deleting — all verifiable without implementing the gallery or detail page.

**Acceptance Scenarios**:

1. **Given** filters are applied, **When** the user clicks "Save Search" and enters a name, **Then** the search is saved and appears in the saved searches dropdown.
2. **Given** saved searches exist, **When** the user selects one from the dropdown, **Then** all associated filters are applied and results update.
3. **Given** a saved search exists, **When** the user deletes it, **Then** it is removed from the dropdown immediately.
4. **Given** a search saved on one device, **When** the user logs in on another device, **Then** the saved search is available (cross-device persistence).

---

### User Story 3 - Listing Detail Page with Full Analysis (Priority: P1)

An investor clicks a listing card and lands on `/listing/[id]`. They see: a photo gallery with lightbox and swipe support, a key stats bar (price, area, rooms, floor, deal score badge), a deal score card with estimated price and confidence range, a SHAP explanation chart showing which factors drive the score, a price history line chart, comparable properties carousel, a mini-map with POIs (metro, schools, parks), the full description with a translate button, listing metadata, CRM pipeline action buttons (favorite/contacted/visited/offer/discard), and a private notes field that auto-saves.

**Why this priority**: The detail page is where investment decisions are made. The AI deal score and SHAP explanation are core differentiators. This page must fully replace the minimal existing `ListingDetailView`.

**Independent Test**: Can be fully tested by navigating to a listing with all data fields populated, verifying each section renders correctly with the right data, and interacting with the gallery, translate button, CRM buttons, and notes.

**Acceptance Scenarios**:

1. **Given** a listing with multiple photos, **When** the user opens the gallery, **Then** photos display in a lightbox with swipe support on mobile and arrows on desktop.
2. **Given** a listing with SHAP data, **When** the detail page loads, **Then** a horizontal bar chart shows the top 5 features with green bars for positive impact and red bars for negative impact, with feature labels from the SHAP data.
3. **Given** a listing with price history, **When** the detail page loads, **Then** a line chart shows all recorded price points over time on the X-axis (date) and Y-axis (price).
4. **Given** a listing with comparable IDs, **When** the detail page loads, **Then** a horizontally scrollable carousel shows up to 5 similar listing cards linking to their detail pages.
5. **Given** a listing with coordinates, **When** the mini-map loads, **Then** it shows the listing marker plus nearby POIs categorized as metro, school, and park.
6. **Given** a description in a foreign language, **When** the user clicks "Translate", **Then** the description updates to the user's language with a loading spinner shown during translation.
7. **Given** a CRM action button (e.g., "Favorite"), **When** the user clicks it, **Then** the button activates immediately (optimistic update) and the CRM status persists after page reload.
8. **Given** the notes textarea, **When** the user types a note, **Then** the note auto-saves 500ms after the last keystroke with a visual save indicator.

---

### User Story 4 - CRM Status Visible on Search Cards (Priority: P2)

An investor who has favorited, contacted, or discarded listings sees those CRM statuses reflected as badges on listing cards in the search results. This prevents revisiting listings they've already processed.

**Why this priority**: Closes the loop between the detail page CRM actions and the search discovery workflow. Depends on P3 CRM implementation but delivers independent workflow value — investors can triage at a glance.

**Independent Test**: Can be tested by setting a CRM status on a listing detail page, returning to search results, and verifying the status badge appears on the corresponding card.

**Acceptance Scenarios**:

1. **Given** a listing has CRM status "favorite", **When** it appears in search results, **Then** a "Favorite" badge or icon is visible on the card.
2. **Given** a listing has CRM status "discard", **When** it appears in search results, **Then** a visual indicator marks it as discarded.

---

### Edge Cases

- What happens when a listing has no photos? A placeholder image is displayed in the gallery and on the card.
- What happens when SHAP data is missing? The SHAP chart section is hidden with a "No analysis available" message.
- What happens when the price history has only one data point? The chart renders a single point rather than a line.
- What happens when the translate API is unavailable? An error toast is shown and the original text remains.
- What happens when infinite scroll loads a page with zero results? A "No more listings" message replaces the sentinel loader.
- What happens when all filters are cleared? Results reset to the default query with all listings.
- What happens when the city autocomplete returns no results? A "No cities found" message is shown in the dropdown.
- What happens when notes save fails? An error indicator replaces the save indicator; the text is not lost.
- What happens on mobile for the filter sidebar? The sidebar collapses into a modal/drawer triggered by a filter button.

## Requirements *(mandatory)*

### Functional Requirements

**Search Page:**

- **FR-001**: System MUST display a filter sidebar with controls for: country (select), city (autocomplete input), zone (hierarchical select), property category (residential/commercial/industrial/land), property type (within category), price range (dual slider with manual input), area in m² (dual slider with manual input), bedrooms (button group: 1, 2, 3, 4, 5+), deal tier (multi-select checkboxes: T1, T2, T3, T4), listing status (multi-select: active, delisted, price-changed), and source portal (multi-select).
- **FR-002**: System MUST encode all active filter values as URL search params so the search URL is bookmarkable and shareable.
- **FR-003**: System MUST update search results on every filter change without a full page reload.
- **FR-004**: System MUST provide a sort dropdown with options: deal score (default), price ascending, price descending, price per m² ascending, recency (newest first), days on market (fewest first).
- **FR-005**: System MUST support infinite scroll pagination: automatically loading the next page when the user reaches the bottom sentinel element.
- **FR-006**: System MUST allow toggling results between card grid view (3 columns desktop, 1 column mobile) and list view (full-width rows).
- **FR-007**: System MUST support saved searches: create (from current filter state with a user-provided name), load (restore all filters from saved search), delete. Saved searches MUST persist across devices via API.
- **FR-008**: System MUST show a loading skeleton while the first results page is fetching and a spinner near the sentinel while additional pages are loading.
- **FR-009**: City autocomplete MUST query available cities with a debounce and show matching suggestions.
- **FR-010**: Zone selector MUST be hierarchical (district → neighborhood) and filter available zones based on the selected city/country.
- **FR-011**: On mobile, the filter sidebar MUST be accessible via a "Filters" button that opens it as a bottom sheet or modal drawer.

**Detail Page:**

- **FR-012**: System MUST display a photo gallery with lightbox. The lightbox MUST support keyboard navigation (arrow keys, Escape) on desktop and swipe gestures on mobile.
- **FR-013**: System MUST display a key stats bar with: asking price (formatted with currency), area in m², bedroom count, floor number, and a color-coded deal score badge (T1=green, T2=blue, T3=gray, T4=red).
- **FR-014**: System MUST display a deal score card showing: estimated fair price (EUR), confidence range (low–high), deal tier badge, and percentage gap between asking price and estimated price.
- **FR-015**: System MUST display a SHAP explanation horizontal bar chart showing the top 5 features from `shap_features` JSONB. Bars pointing right (positive SHAP value) are green; bars pointing left (negative SHAP value) are red. Feature labels are human-readable.
- **FR-016**: System MUST display a price history line chart with date on the X-axis and price on the Y-axis, showing all recorded price changes.
- **FR-017**: System MUST display a comparable properties carousel showing up to 5 listings (from `comparable_ids`). Each card shows photo, price, area, deal score, and links to the comparable's detail page.
- **FR-018**: System MUST display a zone statistics card showing the zone's median price/m², listing count, deal count, and price trend percentage.
- **FR-019**: System MUST display a mini-map centered on the listing's coordinates. The map MUST show nearby POIs categorized as metro, school, and park with distinct icons.
- **FR-020**: System MUST display the listing description. A "Translate" button MUST call the translation API and replace the description with the translated version in the user's browser language.
- **FR-021**: System MUST display listing metadata: source portal name, published date, days on market, and a link to the original source listing.
- **FR-022**: System MUST provide CRM pipeline action buttons (favorite, contacted, visited, offer made, discard) implemented as a toggle group. The active state MUST persist via API and display immediately via optimistic update.
- **FR-023**: System MUST provide a private notes textarea that auto-saves 500ms after the last keystroke and shows a visual save indicator (saving → saved → error).
- **FR-024**: CRM status set on the detail page MUST be reflected as a visual badge on the corresponding listing card in search results.

### Key Entities

- **ListingSearchParams**: The complete set of filter parameters that define a search — country, city, zone_id, property_category, property_type, price range, area range, bedrooms, deal_tier[], status[], source_portal[], sort_by, sort_dir. Serializable to URL params.
- **SavedSearch**: A named snapshot of ListingSearchParams — id, name, filters, created_at. Owned by a user and persisted across devices.
- **ListingSummary**: A condensed representation of a listing for search cards — id, photo, price, area, bedrooms, city, zone, deal_score, deal_tier, status, CRM status (if any).
- **ListingDetail**: The full listing record for the detail page — all ListingSummary fields plus: all photos, floor, estimated_price, confidence range, shap_features, price_history, comparable_ids, zone_stats, description, source_url, published_date.
- **CRMEntry**: A user's pipeline state for a specific listing — listing_id, status (favorite/contacted/visited/offer/discard), notes (text), updated_at.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Search results page loads initial results within 2 seconds on standard broadband.
- **SC-002**: Applying any filter updates visible results within 500 milliseconds.
- **SC-003**: URL search params update on every filter change, enabling 100% of filter states to be restored from the URL alone.
- **SC-004**: Saved search CRUD completes (create, load, delete) without page reload and persists across browser sessions.
- **SC-005**: Listing detail page renders all sections (gallery, stats, SHAP, charts, map) within 3 seconds for a server-side rendered response.
- **SC-006**: Photo gallery swipe works correctly on iOS Safari and Android Chrome.
- **SC-007**: CRM status update is reflected in the UI within 100 milliseconds of button click (optimistic update), before server confirmation.
- **SC-008**: Notes auto-save triggers reliably after 500ms of inactivity and shows correct status indicators (saving/saved/error).
- **SC-009**: All 15+ filter types correctly narrow results — applying a filter never shows listings that don't match.
- **SC-010**: Comparable properties carousel links correctly navigate to their respective detail pages.

## Assumptions

- The backend `/api/v1/listings` endpoint already supports all filter params defined in `ListingsQuery` (country, city, zone_id, property_category, property_type, min/max price, min/max area, min_bedrooms, deal_tier, status, sort_by, sort_dir, cursor, limit) — confirmed from existing `ListingsQuery` type.
- The `ListingDetail` type already includes all required fields: `shap_features` (JSONB), `price_history` (array), `comparable_ids` (array of IDs), `zone_stats`, `photo_urls` (array), `estimated_price`, `confidence_low`, `confidence_high` — confirmed from existing API types.
- New backend endpoints are needed for: saved searches (CRUD), CRM status (PATCH listing status/notes), and translation (POST translate). These will be stub-called initially with localStorage fallback for saved searches.
- `nuqs` library will be added to the frontend for type-safe URL search param management.
- `yet-another-react-lightbox` will be added for the photo gallery lightbox.
- The existing MapLibre setup will be extended (not replaced) for the mini-map on the detail page.
- SHAP feature labels are human-readable strings stored in the `shap_features` JSONB object — no lookup table needed.
- "Saved searches API persistence" uses `localStorage` as a fallback if the API endpoint is unavailable, ensuring the feature works even before the API is implemented.
- The DeepL translation API is proxied through the Go API gateway to avoid exposing API keys to the client.
- CRM notes are per-user and per-listing, stored server-side. The UI uses optimistic updates backed by TanStack Query mutations.
- Zone POI data for the mini-map is available via the existing `/api/v1/zones/{id}` endpoint or the zone detail includes POI arrays (metro, school, park coordinates).
