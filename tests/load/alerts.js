import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    alerts_burst: {
      executor: "per-vu-iterations",
      vus: 100,
      iterations: 100,
      maxDuration: "5m",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

const targetUrl =
  __ENV.ALERTS_TRIGGER_URL || "http://localhost:8080/api/v1/internal/alerts/trigger";

export default function () {
  const response = http.post(
    targetUrl,
    JSON.stringify({
      trigger: "load-test",
      batch: __ITER,
      user_id: `00000000-0000-0000-0000-${String(__VU).padStart(12, "0")}`,
    }),
    {
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  check(response, {
    "alert trigger accepted": (res) => res.status >= 200 && res.status < 300,
  });
}

