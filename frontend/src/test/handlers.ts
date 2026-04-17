import { http, HttpResponse } from "msw";

import type { components } from "@/types/api";

import alertRuleResponse from "../../../tests/contracts/frontend/POST_alert_rules.json";
import listingsResponse from "../../../tests/contracts/frontend/GET_listings.json";
import zonesResponse from "../../../tests/contracts/frontend/GET_zones.json";

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080").replace(
  /\/$/,
  "",
);

export const handlers = [
  http.get(`${apiBaseUrl}/api/v1/listings`, () =>
    HttpResponse.json(listingsResponse as components["schemas"]["ListingsResponse"]),
  ),
  http.get(`${apiBaseUrl}/api/v1/zones`, () =>
    HttpResponse.json(zonesResponse as components["schemas"]["ZoneListResponse"]),
  ),
  http.post(`${apiBaseUrl}/api/v1/alerts/rules`, () =>
    HttpResponse.json(alertRuleResponse as components["schemas"]["AlertRule"], { status: 201 }),
  ),
];
