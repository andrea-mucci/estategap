# K6 Load Tests

This directory holds the production-hardening load scenarios used by the staging job and by manual runs.

## Scripts

- `search.js`: listing search traffic with country, zone, price, and area filters
- `chat.js`: WebSocket chat sessions with sustained message throughput
- `alerts.js`: alert dispatch burst traffic
- `pipeline.js`: publish load to the ingestion pipeline through an HTTP-to-NATS bridge

## Required environment variables

- `API_BASE_URL`: base URL for the HTTP API, for example `https://staging.estategap.com`
- `WS_URL`: full WebSocket URL for chat, for example `wss://staging.estategap.com/chat`
- `ALERTS_TRIGGER_URL`: HTTP endpoint that triggers alert dispatch load
- `NATS_HTTP_PUBLISH_URL`: HTTP endpoint that accepts publish requests for the `listings.ingested` subject

## Optional environment variables

- `K6_PROMETHEUS_RW_URL`: when set by the Helm job, k6 publishes metrics through the Prometheus remote-write output

## Manual runs

```bash
k6 run tests/load/search.js
k6 run tests/load/chat.js
k6 run tests/load/alerts.js
k6 run tests/load/pipeline.js
```

The pipeline scenario uses an HTTP publish bridge so the default `grafana/k6` image can run the workload without a custom `xk6` build.

