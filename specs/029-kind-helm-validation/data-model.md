# Data Model: Kind Cluster & Helm Validation

**Feature**: 029-kind-helm-validation  
**Phase**: 1 — Design  
**Date**: 2026-04-17

---

This feature is infrastructure/tooling, not a data-layer feature. There are no new database tables, gRPC message types, or application data models introduced. The "data" in scope is:

1. **Configuration files** (kind cluster YAML, Helm values, JSON Schema)
2. **Fixture datasets** (static JSON/ONNX files consumed by seed loader)
3. **Make cache state** (hash digests for image change detection)

---

## 1. Kind Cluster Configuration

**File**: `tests/kind/cluster.yaml`

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: estategap
nodes:
  - role: control-plane
    image: kindest/node:v1.30.0
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
      - containerPort: 30080   # api-gateway NodePort
        hostPort: 8080
        protocol: TCP
      - containerPort: 30081   # ws-server NodePort
        hostPort: 8081
        protocol: TCP
      - containerPort: 30090   # Prometheus NodePort
        hostPort: 9090
        protocol: TCP
      - containerPort: 30300   # Grafana NodePort
        hostPort: 3001
        protocol: TCP
      - containerPort: 30003   # frontend NodePort
        hostPort: 3000
        protocol: TCP
      - containerPort: 30432   # PostgreSQL NodePort (debug only)
        hostPort: 5432
        protocol: TCP
  - role: worker
  - role: worker
containerdConfigPatches:
  - |-
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5001"]
      endpoint = ["http://localhost:5001"]
```

---

## 2. Fixture Dataset Schema

### `tests/fixtures/users.json`

Array of 5 user objects, one per subscription tier:

```json
[
  {
    "id": "uuid",
    "email": "free@test.estategap.com",
    "password_hash": "$2b$12$...",   // bcrypt of "testpass123"
    "subscription_tier": "free",
    "country": "ES",
    "created_at": "2026-01-01T00:00:00Z"
  }
  // ... basic, pro, global, api
]
```

**Subscription tiers**: `free`, `basic`, `pro`, `global`, `api`

### `tests/fixtures/listings/<country>.json`

200 listings per country (ES, IT, FR, PT, GB) = 1,000 total. Each listing:

```json
{
  "id": "uuid",
  "source_id": "portal-specific-id",
  "portal": "idealista",
  "country": "ES",
  "property_type": "residential",
  "operation": "sale",
  "price_original": 350000,
  "price_currency": "EUR",
  "price_eur": 350000,
  "area_m2": 85.0,
  "bedrooms": 3,
  "bathrooms": 2,
  "location": {"type": "Point", "coordinates": [-3.7038, 40.4168]},
  "zone_id": "uuid-of-madrid-zone",
  "address": "Calle Gran Vía 1, Madrid",
  "deal_score": 0.72,
  "status": "active",
  "listed_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-04-01T10:00:00Z"
}
```

### `tests/fixtures/zones/<country>.json`

Zone polygons for major cities. Keys: `city`, `country`, `polygon_wkt` (WKT MULTIPOLYGON).

Cities covered:
- ES: Madrid, Barcelona
- IT: Rome, Milan
- FR: Paris
- PT: Lisbon
- GB: London

### `tests/fixtures/alerts.json`

10 alert rule objects:

```json
{
  "id": "uuid",
  "user_id": "uuid-of-pro-user",
  "name": "Madrid Apartments < 400k",
  "country": "ES",
  "filters": {
    "property_type": "residential",
    "max_price_eur": 400000,
    "zone_id": "uuid-madrid"
  },
  "channels": ["email"],
  "active": true,
  "created_at": "2026-02-01T00:00:00Z"
}
```

### `tests/fixtures/ml-models/<country>.onnx`

Minimal stub ONNX models (5 files: es.onnx, it.onnx, fr.onnx, pt.onnx, gb.onnx). Generated using `sklearn` → `skl2onnx` with a single-feature linear regression as placeholder. Sufficient for pipeline testing (model loads, produces a float score).

### `tests/fixtures/conversations/`

Sample conversation JSON files. Each file: `{conversation_id, user_id, messages: [{role, content, ts}]}`.

### `tests/fixtures/html-samples/<portal>/`

Static HTML files captured from portals for spider unit tests. One subdirectory per portal:
- `idealista/` — ES/IT listings page, detail page
- `seloger/` — FR listings page
- `rightmove/` — GB listings page, detail page
- `immobiliare/` — IT listings page

---

## 3. Make Cache State

**Directory**: `.make-cache/`

One file per service: `.make-cache/<service>.digest`  
Contents: `sha256:<hex>` of the combined hash of `services/<svc>/Dockerfile` + all files in `services/<svc>/`.

This directory is listed in `.gitignore` (not committed).

---

## 4. Helm values-test.yaml Shape

```yaml
cluster:
  environment: test
  domain: localhost
  certIssuer: ""        # no TLS in kind

global:
  testMode: true         # picked up by configmap.yaml template
  imageRegistry: "localhost:5001"
  imagePullSecrets: []

# Disable heavy infra for local dev
prometheus:
  enabled: false
loki:
  enabled: false
tempo:
  enabled: false
keda:
  enabled: false

nats:
  replicas: 1
  config:
    cluster:
      replicas: 1
    jetstream:
      fileStore:
        pvc:
          size: 1Gi

postgresql:
  instances: 1
  storage:
    size: 5Gi

minio:
  storage:
    size: 1Gi

redis:
  architecture: standalone    # no sentinel for kind

# All services: single replica, no HPA
services:
  api-gateway:
    replicaCount: 1
    image:
      tag: dev
    hpa:
      enabled: false
  ws-server:
    replicaCount: 1
    image:
      tag: dev
    hpa:
      enabled: false
  # ... (all 10 services follow same pattern)

# Test mode flags
testMode:
  enabled: true
  nowOverride: ""          # set to Unix timestamp to freeze time
  stripeWebhookSecret: "whsec_test_fake"
  fixtureMinIOBucket: "fixtures"
  fakeLLMProvider: true
  scheduleOverride: "*/30 * * * * *"   # every 30s for scraping
```

---

## 5. values.schema.json Top-Level Structure

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EstateGap Helm Values",
  "type": "object",
  "properties": {
    "global": { "$ref": "#/$defs/global" },
    "cluster": { "$ref": "#/$defs/cluster" },
    "testMode": { "$ref": "#/$defs/testMode" },
    "nats": { "$ref": "#/$defs/nats" },
    "postgresql": { "$ref": "#/$defs/postgresql" },
    "redis": { "$ref": "#/$defs/redis" },
    "minio": { "$ref": "#/$defs/minio" },
    "cnpg": { "$ref": "#/$defs/cnpg" },
    "prometheus": { "$ref": "#/$defs/observabilityComponent" },
    "loki": { "$ref": "#/$defs/observabilityComponent" },
    "tempo": { "$ref": "#/$defs/observabilityComponent" },
    "keda": { "$ref": "#/$defs/observabilityComponent" },
    "services": { "$ref": "#/$defs/services" },
    "ingress": { "$ref": "#/$defs/ingress" },
    "argocd": { "$ref": "#/$defs/argocd" },
    "gdpr": { "$ref": "#/$defs/gdpr" },
    "loadTests": { "$ref": "#/$defs/loadTests" }
  },
  "additionalProperties": false,
  "$defs": { ... }
}
```

Each `$defs` entry specifies `type`, `description`, `default`, and nested properties with constraints.

---

## 6. helm-unittest Test File Structure

Each test file follows this pattern:

```yaml
suite: <suite-name>
templates:
  - templates/<template-file>.yaml
tests:
  - it: <description>
    set:
      <override values>
    asserts:
      - <assertion type>: ...
```

Test case inventory (≥25 cases across 8 files):

| File | Test Cases |
|------|-----------|
| `api-gateway_test.yaml` | 4: correct image tag; replica count from values; env var DATABASE_URL present; test mode env var injected |
| `autoscaling_test.yaml` | 3: HPA created when enabled; HPA not created when disabled; min/max replicas from values |
| `ingress_test.yaml` | 3: host matches cluster.domain; api-gateway path routed; ws-server path routed |
| `network-policies_test.yaml` | 4: api-gateway allows ingress from ingress-ns; db egress restricted to db-ns; cross-service isolation; NATS egress allowed |
| `secrets_test.yaml` | 3: SealedSecret kind used (not plain Secret); expected keys present; no plaintext values |
| `postgres_test.yaml` | 3: instances count from values; storage size from values; PostGIS plugin enabled |
| `nats_test.yaml` | 3: replica count from values; JetStream enabled; storage size from values |
| `feature-flags_test.yaml` | 4: prometheus disabled when enabled=false; loki disabled; keda disabled; testMode ConfigMap key set when testMode.enabled=true |

**Total**: 27 test cases (exceeds 20 minimum)
