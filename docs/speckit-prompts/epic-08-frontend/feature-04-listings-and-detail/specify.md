# Feature: Listings Search & Detail Pages

## /specify prompt

```
Build the listing search page with advanced filters and the listing detail page with full analysis.

## What
1. Search page (/search): filter sidebar with: country, city (autocomplete), zone (hierarchical select), property category + type, price range (dual slider), area range (dual slider), bedrooms (1-5+), deal tier (multi-select), status (active/delisted/price changed), source portal (multi-select). Results: toggle between card grid and list view. Sort dropdown (deal score, price, price/m², recency, days on market). Saved searches (CRUD). Infinite scroll pagination.

2. Detail page (/listing/[id]): photo gallery (lightbox with swipe), key stats bar (price, area, rooms, floor, deal score badge), deal score card (estimated price, confidence range, tier badge), SHAP explanation chart (horizontal bar chart of top 5 features), price history chart (line chart over time), comparable properties carousel (5 similar listings), zone statistics card, mini-map with POIs (metro, schools, parks), description section (original language + translate button using DeepL), listing metadata (published date, days on market, source portal), CRM pipeline actions (favorite/contacted/visited/offer/discard buttons), private notes textarea.

## Acceptance Criteria
- All 15+ filters work correctly and update URL params (shareable/bookmarkable)
- Results update on filter change without full page reload
- Saved search CRUD works (create, load, delete)
- Photo gallery works on mobile (swipe) and desktop (arrows + lightbox)
- SHAP chart clearly shows which factors push price up/down
- Price history chart shows all recorded price changes
- Translate button translates description to user's language
- CRM status persists and is visible on search result cards
```
