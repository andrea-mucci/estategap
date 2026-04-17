# Feature Specification: Zone Analytics, Portfolio Tracker & Admin Panel

**Feature Branch**: `024-zones-portfolio-admin`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Build the zone analytics page, portfolio tracker, and admin panel with zone metrics, cross-country comparison, property portfolio management with multi-currency support, and admin dashboard for system health monitoring."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Zone Analytics Deep Dive (Priority: P1)

An investor navigates to a specific zone page to evaluate whether it's a good market to invest in. They see key metrics at a glance: median price per square metre, 12-month price trend, transaction volume, average days on market, current inventory count, and deal frequency. A price distribution histogram shows them how prices are spread across the zone, helping them understand if the market is top-heavy or has affordable segments.

**Why this priority**: Zone analytics is the core value proposition of EstateGap. Investors need granular market data to make informed decisions. This drives user engagement and justifies subscription tiers.

**Independent Test**: Can be fully tested by navigating to `/zones/[id]` for any zone with data and verifying all six metrics display with correct values, the trend chart renders 12 months of data points, and the histogram shows the price distribution. Delivers standalone analytical value.

**Acceptance Scenarios**:

1. **Given** a zone with historical listing data, **When** the user navigates to `/zones/[id]`, **Then** they see median price/m², 12-month trend chart, transaction volume, average days on market, inventory count, and deal frequency displayed with current data.
2. **Given** a zone with listing data, **When** the user views the price distribution section, **Then** a histogram renders showing the distribution of listing prices with reasonable bin sizes.
3. **Given** a zone with no listing data, **When** the user navigates to `/zones/[id]`, **Then** they see a clear empty state message indicating no data is available for this zone.
4. **Given** the user's preferred currency differs from the zone's local currency, **When** viewing zone metrics, **Then** prices are displayed in the user's preferred currency with the conversion rate indicated.

---

### User Story 2 - Cross-Country Zone Comparison (Priority: P1)

An investor wants to compare investment opportunities across different countries. They select up to 5 zones (potentially from different countries) and view a side-by-side comparison table and overlay charts. Currency normalization ensures all values are presented in the user's preferred currency for a fair comparison.

**Why this priority**: Cross-country comparison is a key differentiator for EstateGap. Investors operating across borders need this capability to allocate capital efficiently.

**Independent Test**: Can be fully tested by selecting 2-5 zones from different countries, verifying the comparison table renders with normalised currency values, and confirming overlay charts display data series for each selected zone. Delivers comparison value independently.

**Acceptance Scenarios**:

1. **Given** the user is on the zone analytics page, **When** they activate the comparison tool, **Then** they can search and select up to 5 zones from any country.
2. **Given** the user has selected 3 zones from 2 different countries, **When** the comparison loads, **Then** a side-by-side table displays all key metrics (median price/m², volume, days on market, inventory, deal frequency) with all monetary values converted to the user's preferred currency.
3. **Given** the user has selected 5 zones, **When** they try to add a 6th, **Then** the system prevents the addition and displays a message indicating the maximum of 5 zones has been reached.
4. **Given** the user has selected multiple zones, **When** viewing overlay charts, **Then** each zone is represented with a distinct colour and the user can toggle individual zones on/off.
5. **Given** zones are selected from countries with different currencies, **When** viewing the comparison, **Then** all monetary values are normalised to a single currency with the conversion source and date visible.

---

### User Story 3 - Portfolio Property Management (Priority: P2)

A property owner wants to track their real estate investments in one place. They manually add properties by entering the address, purchase price, purchase date, and monthly rental income. They can edit or remove properties as their portfolio changes.

**Why this priority**: Portfolio tracking encourages daily platform usage and increases retention. It is a natural extension once users find properties through the search/analytics tools.

**Independent Test**: Can be fully tested by adding a property with all fields, verifying it appears in the portfolio list, editing its rental income, and deleting it. Delivers CRUD capability independently.

**Acceptance Scenarios**:

1. **Given** the user is on `/portfolio`, **When** they click "Add Property", **Then** a form appears with fields for address, purchase price, purchase currency, purchase date, and monthly rental income.
2. **Given** the user has filled in all required fields, **When** they submit the form, **Then** the property is saved and appears in the portfolio list.
3. **Given** the user has an existing property, **When** they click edit, **Then** they can update any field and save changes.
4. **Given** the user has an existing property, **When** they click delete and confirm, **Then** the property is removed from the portfolio.
5. **Given** the user enters an invalid purchase date (future date), **When** they submit, **Then** the form shows a validation error.

---

### User Story 4 - Portfolio Dashboard & ROI Metrics (Priority: P2)

A property investor views their portfolio dashboard to understand overall performance. They see total invested amount, current estimated value (from the ML model), unrealized gain/loss, and rental yield. All values respect multi-currency support, converting to the user's preferred display currency.

**Why this priority**: Aggregated ROI metrics transform the portfolio from a simple list into an actionable investment dashboard. This is the value that justifies maintaining portfolio data.

**Independent Test**: Can be fully tested by adding 2+ properties in different currencies and verifying that the dashboard correctly calculates total invested, estimated value, gain/loss, and rental yield in the user's preferred currency.

**Acceptance Scenarios**:

1. **Given** the user has 3 properties in their portfolio, **When** they view the portfolio dashboard, **Then** they see summary cards for total invested, current estimated value, unrealized gain/loss (with percentage), and average rental yield.
2. **Given** properties are in EUR and GBP and the user's preferred currency is USD, **When** viewing the dashboard, **Then** all summary values are displayed in USD with correct conversions applied.
3. **Given** the ML model has a current estimate for a property, **When** viewing the portfolio, **Then** the estimated value column shows the ML-derived value with a timestamp of when it was last updated.
4. **Given** the ML model has no estimate for a manually-entered property, **When** viewing the portfolio, **Then** the estimated value shows "Not available" and the property is excluded from gain/loss calculations.
5. **Given** the user has no properties, **When** they view the portfolio dashboard, **Then** they see an empty state with a call-to-action to add their first property.

---

### User Story 5 - Admin Scraping & ML Health Monitoring (Priority: P3)

An admin needs to monitor the health of the data pipeline and ML models. They access the admin panel to see scraping health per portal and country, ML model performance (MAPE per country), model version history, and can trigger a manual model retrain when needed.

**Why this priority**: Operational visibility is essential but serves internal users only. The platform can operate without a visual admin panel (CLI/logs exist), making this lower priority than user-facing features.

**Independent Test**: Can be fully tested by an admin logging in, viewing each admin tab, verifying metrics load, and triggering a retrain action. Delivers operational visibility independently.

**Acceptance Scenarios**:

1. **Given** an admin user navigates to `/admin`, **When** the page loads, **Then** they see tabs for Scraping Health, ML Models, Users, Countries, and System.
2. **Given** the admin is on the Scraping Health tab, **When** viewing the data, **Then** they see a table of portals grouped by country with status (active/error/paused), last scrape time, listings scraped (24h), and error rate.
3. **Given** the admin is on the ML Models tab, **When** viewing model data, **Then** they see MAPE per country, model version history with timestamps, and a "Retrain" button per country.
4. **Given** the admin clicks the Retrain button for a country, **When** the action is confirmed, **Then** the system triggers a model retrain job and displays a confirmation with a job reference.
5. **Given** a non-admin user navigates to `/admin`, **When** the page attempts to load, **Then** the user receives a 403 Forbidden response and is redirected away.

---

### User Story 6 - Admin User & System Management (Priority: P3)

An admin manages user accounts and system configuration. They view user lists with subscription tiers and activity, enable or disable countries with portal configurations, and monitor system health metrics including NATS queue depths, database size, and Redis statistics.

**Why this priority**: User and system management is operational overhead. These are important for scaling but not for initial platform value delivery.

**Independent Test**: Can be fully tested by navigating through Users, Countries, and System tabs and verifying data displays correctly. Country enable/disable can be tested by toggling a country and confirming the change persists.

**Acceptance Scenarios**:

1. **Given** the admin is on the Users tab, **When** viewing the list, **Then** they see a paginated table with user email, name, subscription tier, role, last active date, and account creation date.
2. **Given** the admin is on the Countries tab, **When** viewing a country, **Then** they see its enabled/disabled status and a list of configured portals with their scraping status.
3. **Given** the admin toggles a country's enabled status, **When** they confirm the change, **Then** the country status updates and scraping is started or stopped accordingly.
4. **Given** the admin is on the System tab, **When** viewing metrics, **Then** they see NATS queue depths per subject, database size and connection count, and Redis memory usage and hit rate.

---

### Edge Cases

- What happens when exchange rate data is unavailable for a currency pair? Display values in the original currency with a warning that conversion is unavailable.
- How does the system handle a zone with very few listings (e.g., 1-2)? Display available metrics but show a low-confidence indicator and suppress the histogram when fewer than 5 data points exist.
- What happens when a user adds a property with an address that doesn't match any zone? The property is saved but marked as "unmatched" — estimated value is unavailable until a zone match is established.
- How does the admin retrain trigger handle a retrain that is already in progress? The button is disabled with a "Retrain in progress" status indicator and the user cannot trigger a duplicate job.
- What happens when the system health endpoints are unreachable? The admin panel shows a connection error per section rather than failing entirely, allowing healthy sections to still display.

## Requirements *(mandatory)*

### Functional Requirements

**Zone Analytics**

- **FR-001**: System MUST display six core zone metrics on the zone detail page: median price per square metre, 12-month price trend, transaction volume, average days on market, current inventory count, and deal frequency.
- **FR-002**: System MUST render a price distribution histogram for each zone, automatically determining appropriate bin sizes based on data range.
- **FR-003**: System MUST display a 12-month price trend as an interactive line chart with monthly data points.
- **FR-004**: System MUST support a zone comparison tool allowing selection of up to 5 zones from any country.
- **FR-005**: System MUST render a side-by-side comparison table with all core metrics for selected zones.
- **FR-006**: System MUST render overlay charts (trend lines) for compared zones with distinct visual identifiers and toggle controls.
- **FR-007**: System MUST normalise all monetary values in zone comparisons to the user's preferred currency.

**Portfolio Tracker**

- **FR-008**: System MUST allow users to add properties with: address (free text), purchase price, purchase currency, purchase date, and monthly rental income.
- **FR-009**: System MUST allow users to edit and delete existing portfolio properties.
- **FR-010**: System MUST display portfolio summary metrics: total invested, current estimated value, unrealized gain/loss (absolute and percentage), and average rental yield.
- **FR-011**: System MUST convert all portfolio monetary values to the user's preferred display currency.
- **FR-012**: System MUST source current estimated property values from the ML scoring model when a zone match exists.
- **FR-013**: System MUST validate portfolio form inputs: purchase date must not be in the future, purchase price and rental income must be positive numbers.

**Admin Panel**

- **FR-014**: System MUST restrict access to the admin panel to users with the admin role, returning 403 for non-admin users.
- **FR-015**: System MUST display scraping health metrics: portal status, last scrape time, 24-hour listing count, and error rate, grouped by country.
- **FR-016**: System MUST display ML model metrics: MAPE per country, model version history with dates, and training status.
- **FR-017**: System MUST allow admins to trigger a manual ML model retrain per country.
- **FR-018**: System MUST display a paginated user list with email, name, subscription tier, role, last active date, and creation date.
- **FR-019**: System MUST allow admins to enable or disable countries, affecting scraping activity.
- **FR-020**: System MUST display system health metrics: NATS queue depths per subject, database size and connection count, Redis memory usage and cache hit rate.

### Key Entities

- **Zone Metrics**: Represents aggregated analytical data for a geographic zone — includes median price, volume, trend data, days on market, inventory, and deal frequency. Related to a Zone.
- **Zone Comparison**: A transient selection of up to 5 zones used for side-by-side analysis. Not persisted — exists only in the user's session.
- **Portfolio Property**: A user-owned property record — includes address, purchase price, purchase currency, purchase date, rental income, and a link to a zone (if matched). Belongs to a User.
- **Portfolio Summary**: Computed aggregation of all portfolio properties — total invested, estimated value, gain/loss, yield. Derived from Portfolio Properties and ML estimates.
- **Scraping Health Record**: Operational status of a scraping portal — includes portal name, country, status, last run, volume, and error rate.
- **ML Model Record**: Metadata about a trained ML model — includes country, MAPE, version, training date, and status.
- **System Health Snapshot**: Point-in-time system metrics — NATS queue depths, database stats, Redis stats.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view all six zone metrics within 2 seconds of navigating to a zone page.
- **SC-002**: Zone comparison table renders for 5 selected zones with currency-normalised values within 3 seconds.
- **SC-003**: Users can add a property to their portfolio and see it reflected in the dashboard within 5 seconds of submission.
- **SC-004**: Portfolio summary calculations (total invested, gain/loss, yield) are accurate to within 1% of manual calculation using the same exchange rates.
- **SC-005**: Admin panel loads each tab's data within 3 seconds for a system with up to 50 countries and 200 portals.
- **SC-006**: Non-admin users are blocked from accessing any admin functionality — 0% of requests from non-admin users succeed.
- **SC-007**: Manual retrain trigger initiates the retrain job within 10 seconds of the admin clicking the button.
- **SC-008**: All monetary values in zone analytics and portfolio are displayed in the user's preferred currency when a conversion rate is available.

## Assumptions

- The existing zone analytics API endpoints (`/api/v1/zones/:id/analytics`) provide all six required metrics. If additional metrics are needed, new backend endpoints will be added as part of this feature.
- Exchange rate data is available through an existing or newly provisioned service. Rates are updated at least daily and the source of rates is documented in the UI.
- The ML scoring model already produces per-property value estimates accessible through existing API endpoints. Portfolio properties are matched to zones for value estimation.
- Admin role detection uses the existing `@estategap.com` email domain convention already implemented in NextAuth configuration.
- The retrain trigger invokes an existing backend endpoint that creates a Kubernetes CronJob or one-off Job. The admin panel does not manage K8s resources directly.
- Portfolio data (user-owned properties) is persisted server-side via new API endpoints. A new `portfolio_properties` database table will be needed.
- The system health endpoints (NATS, PostgreSQL, Redis stats) are exposed through an admin-only API route that aggregates data from monitoring infrastructure.
- Currency preference is a user-level setting. If not yet implemented, a default of EUR is assumed with the ability to change it in user settings.
