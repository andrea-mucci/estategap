# Feature Specification: Dashboard Analytics & Interactive Map

**Feature Branch**: `022-dashboard-analytics-map`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Build the main dashboard with analytics cards, trend charts, and an interactive property map."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard Summary at a Glance (Priority: P1)

An investor opens the dashboard and immediately sees key metrics for their selected country: total active listings, new listings added today, Tier 1 deals found today, and the count of recent price drops. Tabs at the top let them switch between countries (e.g., Spain, France, Italy) to compare market activity. Each card updates to reflect the selected country's data.

**Why this priority**: The summary cards are the core value proposition of the dashboard — giving investors an instant pulse on the market without navigating multiple pages. This is the landing experience after login.

**Independent Test**: Can be fully tested by logging in, viewing card values, and switching country tabs — delivers immediate market awareness value with no other features required.

**Acceptance Scenarios**:

1. **Given** a logged-in user on the dashboard, **When** the page loads, **Then** four summary cards are displayed (total listings, new today, Tier 1 deals today, recent price drops) with data for the default country.
2. **Given** the dashboard is loaded, **When** the user clicks a different country tab, **Then** all four cards update to reflect that country's data within 1 second.
3. **Given** the dashboard is loaded, **When** any card has a value of zero, **Then** the card displays "0" (not blank or an error).
4. **Given** a user with a "free" subscription, **When** they view the dashboard, **Then** cards show data only for countries available under their subscription tier.

---

### User Story 2 - Trend Charts for Zone Analysis (Priority: P2)

An investor wants to understand market trends over time. They view three interactive charts on the dashboard: a line chart showing price per square meter over the last 12 months grouped by zone, a bar chart showing listing volume over time, and a histogram showing deal frequency distribution. Hovering over data points reveals tooltips with exact values, and clicking a zone legend entry toggles its visibility.

**Why this priority**: Trend data transforms raw numbers into actionable intelligence. It depends on the country filter from P1 but is independently valuable once a country is selected.

**Independent Test**: Can be tested by selecting a country, verifying chart data matches known zone analytics, hovering for tooltips, and toggling legend items — delivers trend insight value standalone.

**Acceptance Scenarios**:

1. **Given** a country is selected, **When** trend charts render, **Then** the line chart shows price/m2 over 12 months with one line per zone, the bar chart shows monthly listing volume, and the histogram shows deal score distribution.
2. **Given** a rendered chart, **When** the user hovers over a data point, **Then** a tooltip shows the exact value, zone name, and month.
3. **Given** a rendered line chart, **When** the user clicks a zone name in the legend, **Then** that zone's line toggles on/off without affecting other zones.
4. **Given** a country with no zone analytics data, **When** charts render, **Then** an empty state message is shown (e.g., "No trend data available for this country yet").

---

### User Story 3 - Interactive Property Map with Markers (Priority: P2)

An investor views listings plotted on an interactive map. Each listing appears as a color-coded marker based on deal tier: green for Tier 1 (great deals), blue for Tier 2, gray for Tier 3, and red for Tier 4. When zoomed out (below zoom level 12), markers cluster to avoid visual clutter. Clicking a marker or cluster expands it, and clicking an individual marker shows a popup with a mini listing card (photo, price, deal score, address).

**Why this priority**: The map provides spatial context that cards and charts cannot — investors need to see where deals are concentrated geographically. It's a core differentiator for a real estate intelligence platform.

**Independent Test**: Can be tested by loading the map, verifying marker colors match deal tiers, zooming to verify clustering behavior, and clicking markers to verify popup content — delivers spatial intelligence standalone.

**Acceptance Scenarios**:

1. **Given** listings exist for the selected country, **When** the map loads, **Then** each listing is displayed as a colored marker (green=T1, blue=T2, gray=T3, red=T4).
2. **Given** the map is at zoom level below 12, **When** multiple markers overlap, **Then** they are grouped into numbered clusters.
3. **Given** a cluster on the map, **When** the user clicks it, **Then** the map zooms in to expand the cluster.
4. **Given** an individual marker, **When** the user clicks it, **Then** a popup appears showing the listing photo, price, deal score, and address.
5. **Given** 50,000+ listings loaded, **When** the user pans and zooms, **Then** the map responds without noticeable lag (frame rate stays above 30fps).

---

### User Story 4 - Zone Polygon Overlay (Priority: P3)

An investor wants to see zone boundaries on the map to understand geographic pricing patterns. They toggle a "Show Zones" layer that overlays zone polygons with semi-transparent fill colors. Hovering over a zone shows its name and key stats (median price/m2, listing count, deal count).

**Why this priority**: Zone overlays add analytical depth to the map but are not required for the primary marker-based exploration. Useful for power users comparing neighborhoods.

**Independent Test**: Can be tested by toggling the zone overlay on, verifying polygons render, and hovering for zone stats — delivers geographic segmentation context independently.

**Acceptance Scenarios**:

1. **Given** the map is displayed, **When** the user toggles "Show Zones" on, **Then** zone boundary polygons appear with semi-transparent fill.
2. **Given** zone polygons are visible, **When** the user hovers over a zone, **Then** a tooltip shows zone name, median price/m2, listing count, and deal count.
3. **Given** zone polygons are visible, **When** the user toggles "Show Zones" off, **Then** all polygons disappear and only markers remain.

---

### User Story 5 - Custom Zone Drawing Tool (Priority: P3)

An investor identifies an area of interest that doesn't match predefined zones. They activate a drawing tool, draw a polygon on the map, name it, and save it as a custom zone. Saved custom zones appear in their zone list and can be used for alerts.

**Why this priority**: Custom zones are a power-user feature that builds on the map infrastructure from P2 stories. It adds personalization but isn't required for core dashboard value.

**Independent Test**: Can be tested by activating the draw tool, drawing a polygon, naming and saving it, and verifying it persists across sessions — delivers custom area tracking independently.

**Acceptance Scenarios**:

1. **Given** the map is displayed, **When** the user activates the drawing tool, **Then** the cursor changes to crosshair mode and a toolbar appears with draw/cancel/save actions.
2. **Given** drawing mode is active, **When** the user clicks points on the map, **Then** a polygon shape is drawn connecting the clicked points in order.
3. **Given** a polygon is drawn, **When** the user clicks "Save" and enters a name, **Then** the zone is saved and appears in their custom zones list.
4. **Given** a custom zone is saved, **When** the user reloads the dashboard, **Then** the custom zone is available in their zone list.

---

### User Story 6 - Heatmap Layer (Priority: P3)

An investor wants to visualize deal density across the map rather than individual markers. They switch to a "Heatmap" layer that shows color intensity based on the concentration of deals in an area (warmer colors = more deals).

**Why this priority**: The heatmap is an alternative visualization mode that enhances the map but is not essential for the primary marker-based experience.

**Independent Test**: Can be tested by switching to heatmap mode, verifying color intensity matches deal density, and toggling back to markers — delivers density visualization independently.

**Acceptance Scenarios**:

1. **Given** the map is displayed, **When** the user switches to "Heatmap" mode, **Then** markers are replaced by a heatmap layer showing deal density.
2. **Given** the heatmap is active, **When** the user pans to an area with many deals, **Then** that area shows warmer colors (red/orange) compared to sparse areas (blue/green).
3. **Given** the heatmap is active, **When** the user switches back to "Markers" mode, **Then** the heatmap disappears and individual markers return.

---

### Edge Cases

- What happens when a country has zero listings? Dashboard cards show "0" values, charts show empty state, map centers on the country with no markers.
- What happens when a listing has no coordinates? The listing appears in cards and charts but is excluded from the map.
- What happens when a listing has no photo? The marker popup shows a placeholder image.
- What happens when the user draws an invalid polygon (e.g., self-intersecting)? The system warns the user and prevents saving.
- What happens on slow network connections? Skeleton loaders appear for cards and charts; map tiles load progressively.
- What happens on mobile devices? Map supports pinch-to-zoom and drag-to-pan; charts are scrollable; country tabs wrap or become a dropdown.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a dashboard page at `/dashboard` with four summary cards: total active listings, new listings today, Tier 1 deals today, and recent price drops (last 7 days).
- **FR-002**: System MUST provide country tabs at the top of the dashboard that filter all cards, charts, and map data by the selected country.
- **FR-003**: System MUST display a line chart showing median price per square meter over the last 12 months, with one line per zone within the selected country.
- **FR-004**: System MUST display a bar chart showing monthly listing volume (new listings per month) for the selected country over the last 12 months.
- **FR-005**: System MUST display a histogram showing deal score distribution across all active listings in the selected country.
- **FR-006**: System MUST render an interactive map using color-coded markers for each listing: green (Tier 1), blue (Tier 2), gray (Tier 3), red (Tier 4).
- **FR-007**: System MUST cluster markers at zoom levels below 12, showing the count of grouped listings in each cluster.
- **FR-008**: System MUST show a popup with mini listing card (photo, price, deal score, address) when a user clicks an individual marker.
- **FR-009**: System MUST provide a togglable zone polygon overlay on the map showing zone boundaries with semi-transparent fill.
- **FR-010**: System MUST allow users to draw a custom polygon on the map, name it, and save it as a custom zone.
- **FR-011**: System MUST provide a heatmap layer option that visualizes deal density as an alternative to individual markers.
- **FR-012**: System MUST support touch gestures (pinch-to-zoom, drag-to-pan) on the map for mobile devices.
- **FR-013**: Charts MUST support hover tooltips showing exact values and click-to-toggle on legend entries to show/hide individual data series.
- **FR-014**: System MUST show skeleton loaders while dashboard data is being fetched.
- **FR-015**: System MUST restrict country tabs based on the user's subscription tier (e.g., "free" tier sees only one country).

### Key Entities

- **Dashboard Summary**: Aggregated metrics per country — total listings, new today, Tier 1 deals count, price drops count. Refreshed on each country tab switch.
- **Zone Analytics**: Monthly time-series data per zone — median price/m2, listing count, deal count. Used to populate trend charts.
- **Listing Marker**: A geographic point representing a listing on the map — includes coordinates, deal tier, and summary data for popup display.
- **Zone Polygon**: A geographic boundary representing a predefined or custom zone — includes geometry, name, and aggregate statistics.
- **Custom Zone**: A user-created geographic boundary — polygon coordinates, user-assigned name, and creation date. Persists across sessions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard page loads and displays all summary cards within 3 seconds on a standard broadband connection.
- **SC-002**: Country tab switch updates all visible data (cards, charts, map) within 1 second.
- **SC-003**: Map renders and remains interactive (pan, zoom, click) with 50,000+ listings loaded simultaneously.
- **SC-004**: Chart tooltips appear within 200 milliseconds of hover.
- **SC-005**: Custom zone drawing and saving completes within 5 user interactions (activate tool, draw points, close polygon, name, save).
- **SC-006**: Map is fully functional on touch devices — pinch-to-zoom, drag-to-pan, and marker tap all work correctly.
- **SC-007**: All dashboard data (cards, charts, map markers) is consistent — switching countries shows the same totals across all widgets.
- **SC-008**: 90% of users can locate a Tier 1 deal on the map within 30 seconds of loading the dashboard.

## Assumptions

- Users have a modern browser with WebGL support (required for map rendering).
- The existing listings search endpoint provides sufficient data for summary card calculations; a dedicated dashboard stats endpoint may be needed for performance.
- Zone geometry data (polygons) will need to be exposed via a new endpoint, as the current zone endpoints do not return GeoJSON geometry.
- Listing coordinates (latitude/longitude) will need to be included in listing responses for map plotting, as they are stored in the database but not currently returned by the listings endpoint.
- The zone analytics endpoint (returning 12-month time series per zone) already exists and will be used for trend charts.
- The countries endpoint provides the list of available countries for tabs, filtered by user subscription tier.
- Custom zone persistence requires a new endpoint to save user-drawn polygons; this will be scoped as part of implementation planning.
- "Recent price drops" is defined as listings with at least one price decrease recorded in their price history within the last 7 days.
- Recharts (or equivalent charting library) will be used for trend charts; the specific library choice is an implementation detail.
- The existing MapLibre GL JS setup in the codebase will be extended for the interactive map.
