import http from "k6/http";
import { check, fail } from "k6";

export const options = {
  scenarios: {
    pipeline_publish: {
      executor: "per-vu-iterations",
      vus: 100,
      iterations: 500,
      maxDuration: "5m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
  },
};

const publishUrl = __ENV.KAFKA_HTTP_PUBLISH_URL;

export default function () {
  if (!publishUrl) {
    fail("KAFKA_HTTP_PUBLISH_URL is required for pipeline.js");
  }

  const response = http.post(
    publishUrl,
    JSON.stringify({
      topic: "estategap.raw-listings",
      key: "ES",
      message: {
        id: `${__VU}-${__ITER}`,
        country: "ES",
        price: 250000,
        source: "load-test",
      },
    }),
    {
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  check(response, {
    "pipeline publish accepted": (res) => res.status >= 200 && res.status < 300,
  });
}
