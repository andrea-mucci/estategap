import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    search_load: {
      executor: "ramping-vus",
      stages: [
        { duration: "30s", target: 1000 },
        { duration: "5m", target: 1000 },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<300"],
    http_req_failed: ["rate<0.01"],
  },
};

const baseUrl = (__ENV.API_BASE_URL || "http://localhost:8080").replace(/\/$/, "");
const filters = [
  "country=ES&status=active&limit=20",
  "country=FR&status=active&sort_by=deal_score&sort_dir=desc&limit=20",
  "country=IT&status=active&min_price_eur=150000&max_price_eur=500000&limit=20",
  "country=PT&status=active&min_area_m2=60&max_area_m2=180&limit=20",
];

export default function () {
  const query = filters[Math.floor(Math.random() * filters.length)];
  const response = http.get(`${baseUrl}/api/v1/listings?${query}`);

  check(response, {
    "search returns 200": (res) => res.status === 200,
  });
}

