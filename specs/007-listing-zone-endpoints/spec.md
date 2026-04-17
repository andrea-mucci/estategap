# Feature Specification: Listing & Zone Data Endpoints

**Feature Branch**: `007-listing-zone-endpoints`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Implement the REST API endpoints for listing search, listing detail, zones, countries, and portals."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find Investment Opportunities (Priority: P1)

A property investor searches for undervalued properties across a country, filtering by deal score, price range, property type, and geographic zone. Results are sorted by best deals first and paginated. Prices are shown in the investor's preferred currency.

**Why this priority**: Core product value proposition — discovering below-market properties is the primary reason users sign up. Without a functional search, no other feature matters.

**Independent Test**: Can be fully tested by querying the listings search endpoint with various filter combinations and verifying results are correctly filtered, sorted, paginated, and reflect the requested currency.

**Acceptance Scenarios**:

1. **Given** an authenticated Pro user, **When** they search with `country=ES&deal_tier=1&sort_by=deal_score&currency=USD`, **Then** results are sorted by best deal score descending, prices are in USD, and the response includes `X-Currency: USD` and `X-Exchange-Rate-Date` headers.
2. **Given** an authenticated Free user, **When** they search listings, **Then** only listings first published more than 48 hours ago appear in results.
3. **Given** a paginated search returning a `next_cursor`, **When** the user fetches the next page using that cursor, **Then** results continue exactly where the previous page ended with no duplicates or gaps.
4. **Given** a search with a `zone_id` filter, **When** results are returned, **Then** only listings whose location falls within that zone's geographic boundary are included.

---

### User Story 2 - Research a Specific Property (Priority: P1)

A user found a promising listing in search results and wants full details: all property attributes, price change history, the deal score explanation, and how it compares to nearby similar properties.

**Why this priority**: Converts search interest into actionable decisions. SHAP explanations are a key differentiator — users need to understand *why* a property is scored as a deal.

**Independent Test**: Can be fully tested by fetching a listing detail by ID and verifying all nested data (price history, SHAP features, comparable IDs, zone stats) is present and correct.

**Acceptance Scenarios**:

1. **Given** a valid listing ID, **When** the detail endpoint is called, **Then** the response includes all property fields, full price history ordered by date, deal score with confidence interval, the top 5 SHAP factors with labels and values, comparable listing IDs, and a zone stats summary.
2. **Given** a listing that has never had a price change, **When** detail is requested, **Then** `price_history` is an empty array (not null or absent).
3. **Given** an unscored listing (no deal score), **When** detail is requested, **Then** `deal_score`, `shap_features`, and `comparables` are null/empty without causing an error.

---

### User Story 3 - Analyse a Market Zone (Priority: P2)

A user wants to understand price trends, listing volumes, and deal frequency for a specific geographic zone over the past year to benchmark properties against local market conditions.

**Why this priority**: Essential context for evaluating listings. Users need market benchmarks to judge whether a deal score reflects genuine value.

**Independent Test**: Can be fully tested by fetching zone analytics and verifying exactly 12 monthly data points are returned, covering the previous 12 complete calendar months.

**Acceptance Scenarios**:

1. **Given** a zone ID, **When** the analytics endpoint is called, **Then** exactly 12 monthly data points are returned, each with median price/m², listing volume, and deal frequency for that calendar month.
2. **Given** a zone with no listings in a particular month, **When** analytics are requested, **Then** that month's entry returns zero values rather than being omitted.

---

### User Story 4 - Compare Zones Side by Side (Priority: P2)

A user considering multiple cities or neighbourhoods wants to compare up to 5 zones simultaneously in a single request, including cross-country comparisons with EUR-normalized values.

**Why this priority**: Differentiating feature for multi-market investors. Cross-country comparison is unique to EstateGap's coverage footprint.

**Independent Test**: Can be tested by calling the zone compare endpoint with IDs from different countries and verifying EUR-normalised and local-currency values are both present per zone.

**Acceptance Scenarios**:

1. **Given** zone IDs from two different countries, **When** the compare endpoint is called, **Then** each zone's stats include both EUR-normalised and local-currency values, enabling direct comparison.
2. **Given** more than 5 zone IDs in the request, **When** the endpoint is called, **Then** a validation error is returned.

---

### User Story 5 - Discover Available Markets (Priority: P3)

A new user wants to know which countries EstateGap covers and see a quick summary of activity (listing count, deals found, portals monitored) before choosing a market to explore.

**Why this priority**: Supports onboarding and market selection. Important for the product's international positioning but does not block core search functionality.

**Independent Test**: Can be tested by fetching the countries endpoint and verifying only active countries are returned with accurate summary statistics.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they fetch the countries endpoint, **Then** only active countries are returned, each with listing count, active deal count, and active portal count.

---

### User Story 6 - Monitor Data Source Health (Priority: P3)

An administrator or power user wants to see which property portals are being scraped, when they last ran successfully, and whether they are enabled — to gauge data freshness.

**Why this priority**: Operational transparency feature that builds user trust and supports debugging data gaps, but is not blocking for core user value.

**Independent Test**: Can be tested by fetching the portals endpoint and verifying all active portals are returned with health metrics.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they fetch the portals endpoint, **Then** all active portals are returned with their country, display name, enabled status, and last successful scrape timestamp.

---

### Edge Cases

- What happens when a cursor is reused with different filter parameters than the original query?
- How does the system respond when the requested currency has no exchange rate in the database?
- What happens when all listings in a zone are unscored (no deal tier)?
- How does pagination behave when new listings are inserted between page requests?
- What is returned when a zone compare request includes an invalid or non-existent zone ID?
- How does the 48-hour free-tier gate interact with listings that were delisted and re-listed?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Listing search MUST support filtering by: country, city, zone (geographic boundary), property category, property type, price range in EUR, price range in original currency, area range, bedrooms, bathrooms, deal tier, listing status, source portal, and days-on-market range.
- **FR-002**: Listing search MUST support sorting by: deal score, price, price per m², recency (published date), and days on market — each in ascending or descending direction.
- **FR-003**: Listing search MUST use cursor-based pagination that guarantees no duplicate or skipped results across sequential page requests for the same query.
- **FR-004**: Listing search MUST support a `currency` parameter for on-the-fly price conversion, returning the applied exchange rate date in an `X-Exchange-Rate-Date` response header alongside an `X-Currency` header.
- **FR-005**: Listing search MUST apply subscription tier gating: Free users see only listings published more than 48 hours ago; Basic users are restricted to their allowed countries; Pro and above users have full unrestricted access.
- **FR-006**: Listing detail MUST include all property fields, complete price change history (ordered chronologically), deal score with confidence interval, the top 5 SHAP factors (feature label, value, direction), comparable listing identifiers, and a summary of zone-level market statistics.
- **FR-007**: Zone list endpoint MUST support filtering by country, hierarchy level (0–4: country/region/province/city/neighbourhood), and parent zone ID. Each zone in the response MUST include summary statistics (listing count, median price per m²).
- **FR-008**: Zone detail endpoint MUST return a single zone with full statistics (listing count, median price/m², deal count, price trend percentage).
- **FR-009**: Zone analytics endpoint MUST return exactly 12 data points — one per calendar month for the past 12 complete months — each with: median price/m², total listing volume, and deal frequency. Months with zero listings MUST appear as zero-value entries.
- **FR-010**: Zone compare endpoint MUST accept 2–5 zone IDs, return side-by-side statistics for each zone (including EUR-normalised and local-currency values), and work across zones from different countries.
- **FR-011**: Countries endpoint MUST return only active countries, each with: total listing count, active deal count (deal_tier 1 or 2), and count of active portals.
- **FR-012**: Portals endpoint MUST return only active portals, each with: display name, country, enabled flag, and last successful scrape timestamp.
- **FR-013**: All list endpoints MUST use a consistent response envelope: `data` array, `pagination` object (next_cursor, has_more), and `meta` object (total_count, currency where applicable).

### Key Entities

- **Listing**: A property sourced from a portal with pricing (original + EUR), location (coordinates + zone), physical attributes, ML deal score, SHAP explanations, and lifecycle timestamps.
- **Price History**: Ordered record of price and status changes for a listing, including old/new values, change direction, and timestamps.
- **Zone**: A named geographic area at one of five hierarchy levels. Contains geometry (boundary polygon) and aggregated market statistics.
- **Zone Statistics**: Periodically refreshed aggregated metrics per zone — median price/m², listing volume, deal frequency, and price trend direction.
- **Country**: A supported market with a primary currency, active status, and aggregated coverage statistics.
- **Portal**: A property website scraped by EstateGap. Belongs to a country and tracks scrape health metadata.
- **Exchange Rate**: Daily EUR conversion rates per currency, used for real-time price display in user-preferred currency.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Listing search responds at or below 500 milliseconds at the 95th percentile with 100,000 active listings and any valid filter combination applied.
- **SC-002**: Cursor pagination across any sequence of pages for the same query returns zero duplicated or skipped listings.
- **SC-003**: Currency conversion values match the most recent exchange rate recorded in the database, with no rounding error exceeding 0.01 of the smallest currency denomination.
- **SC-004**: Free-tier subscription gating reliably excludes listings published within the past 48 hours under all filter and sort combinations.
- **SC-005**: Zone analytics always returns exactly 12 monthly data points, including zero-value entries for months with no listing activity.
- **SC-006**: Zone compare returns EUR-normalised statistics enabling accurate cross-country comparison regardless of each zone's home currency.
- **SC-007**: All endpoints return structured, machine-readable error responses for invalid inputs, enabling client applications to surface localised messages without parsing error strings.

## Assumptions

- The `zone_statistics` materialized view exists in the database and is refreshed by a background job; this feature only reads it.
- Exchange rates are populated daily in the `exchange_rates` table by the data pipeline. If a requested currency has no rate available, the API falls back to EUR with a clear indication in the response.
- The `price_history` table is populated by the data pipeline on every price or status change; this feature only reads it.
- Comparable listings are determined by same zone, same property category, and asking price within ±20% of the subject listing; this heuristic may be tuned after launch.
- The Basic tier's allowed-countries list is stored in the user's database record and requires a DB read on restricted requests (not encoded in the JWT).
- Portal health metrics (last successful scrape timestamp) are managed by the scrape orchestrator service; if absent, portals are returned without health data rather than excluded.
- All endpoints in this feature require authentication; no public anonymous access is introduced.
- The `shap_features` JSONB column on listings contains an array of objects with `feature`, `value`, and `direction` keys; the API surfaces the top 5 by absolute value.
