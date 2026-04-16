# Feature: Dashboard & Interactive Map

## /specify prompt

```
Build the main dashboard with analytics cards, trend charts, and an interactive property map.

## What
1. Dashboard page (/dashboard): summary cards (total listings, new today, Tier 1 deals today, recent price drops — per country with tabs). Trend charts (Recharts): price/m² over time by zone (line chart), listing volume over time (bar chart), deal frequency distribution (histogram). Country filter as top-level tabs.
2. Interactive Map (MapLibre GL JS): listings plotted as color-coded markers by deal tier (green=T1, blue=T2, gray=T3, red=T4). Clustering at zoom levels < 12. Popup on click shows mini listing card (photo, price, score, address). Zone polygon overlay (togglable). Custom zone drawing tool (draw polygon → save as named zone). Pan/zoom across all active countries. Heatmap layer option (deal density).

## Acceptance Criteria
- Dashboard loads in < 3s. Cards show correct real-time data.
- Charts are interactive (hover tooltips, click to filter).
- Map renders 50k+ markers without lag (via clustering).
- Marker popup shows correct listing data.
- Custom zone drawn and saved successfully.
- Map works on mobile (touch gestures).
```
