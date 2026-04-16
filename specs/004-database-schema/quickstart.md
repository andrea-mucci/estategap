# Quickstart: PostgreSQL Database Schema

**Feature**: 004-database-schema  
**Date**: 2026-04-16

---

## Prerequisites

- Docker (for local PostgreSQL + PostGIS)
- Python 3.12+ with `uv` installed
- Access to `services/pipeline/` directory

---

## 1. Start Local Database

```bash
docker run -d \
  --name estategap-db \
  -e POSTGRES_USER=estategap \
  -e POSTGRES_PASSWORD=estategap \
  -e POSTGRES_DB=estategap \
  -p 5432:5432 \
  postgis/postgis:16-3.4

# Verify PostGIS is available
docker exec estategap-db psql -U estategap -d estategap -c "SELECT PostGIS_Version();"
```

---

## 2. Install Dependencies

```bash
cd services/pipeline
uv sync
```

The `pyproject.toml` for the pipeline service adds:
- `alembic>=1.13`
- `sqlalchemy>=2.0`
- `geoalchemy2>=0.14`
- `psycopg2-binary>=2.9`   # Alembic sync driver
- `asyncpg>=0.29`           # Runtime driver (already present)

---

## 3. Configure Alembic

`services/pipeline/alembic.ini`:
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://estategap:estategap@localhost:5432/estategap
```

Or use an environment variable override:
```bash
export DATABASE_URL="postgresql://estategap:estategap@localhost:5432/estategap"
```

`services/pipeline/alembic/env.py` reads `DATABASE_URL` from environment when set, falling back to `alembic.ini`.

---

## 4. Run Migrations

```bash
cd services/pipeline

# Apply all migrations
uv run alembic upgrade head

# Check current revision
uv run alembic current

# View migration history
uv run alembic history --verbose
```

Expected output after `upgrade head`:
```
INFO  [alembic.runtime.migration] Running upgrade  -> a1b2c3d4e5f6, 001_extensions
INFO  [alembic.runtime.migration] Running upgrade a1b2c3d4e5f6 -> b2c3d4e5f6a1, 002_reference_tables
INFO  [alembic.runtime.migration] Running upgrade b2c3d4e5f6a1 -> c3d4e5f6a1b2, 003_listings
INFO  [alembic.runtime.migration] Running upgrade c3d4e5f6a1b2 -> d4e5f6a1b2c3, 004_zones
INFO  [alembic.runtime.migration] Running upgrade d4e5f6a1b2c3 -> e5f6a1b2c3d4, 005_users
INFO  [alembic.runtime.migration] Running upgrade e5f6a1b2c3d4 -> f6a1b2c3d4e5, 006_alerts
INFO  [alembic.runtime.migration] Running upgrade f6a1b2c3d4e5 -> a1b2c3d4e5f7, 007_ai
INFO  [alembic.runtime.migration] Running upgrade a1b2c3d4e5f7 -> b2c3d4e5f6a2, 008_ml_models
INFO  [alembic.runtime.migration] Running upgrade b2c3d4e5f6a2 -> c3d4e5f6a1b3, 009_zone_statistics
INFO  [alembic.runtime.migration] Running upgrade c3d4e5f6a1b3 -> d4e5f6a1b2c4, 010_seed_data
```

---

## 5. Verify Seed Data

```bash
docker exec estategap-db psql -U estategap -d estategap -c "
SELECT code, name, currency FROM countries ORDER BY code;
"
# Expected: ES, FR, GB, IT, PT

docker exec estategap-db psql -U estategap -d estategap -c "
SELECT name, country_code, spider_class FROM portals ORDER BY country_code, name;
"
# Expected: 10 portals across ES, IT, PT, FR, GB
```

---

## 6. Verify Partition Pruning

```bash
docker exec estategap-db psql -U estategap -d estategap -c "
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id, city, asking_price_eur
FROM listings
WHERE country = 'ES'
  AND status = 'active'
  AND deal_tier = 1
LIMIT 10;
"
# Look for: "Seq Scan on listings_es" with "Partitions: listings_es"
# Should NOT see listings_fr, listings_it, etc.
```

---

## 7. Run Integration Tests

```bash
cd services/pipeline

# Requires Docker to be running (testcontainers will spin up its own container)
uv run pytest tests/integration/test_schema/ -v --tb=short

# Run only partition pruning tests
uv run pytest tests/integration/test_schema/test_partitioning.py -v

# Run only spatial tests
uv run pytest tests/integration/test_schema/test_spatial.py -v
```

---

## 8. Rollback (Development Only)

```bash
# Rollback one migration
uv run alembic downgrade -1

# Rollback to specific revision
uv run alembic downgrade 002_reference_tables

# Rollback all (only safe on empty tables)
uv run alembic downgrade base
```

---

## 9. Kubernetes Migration Job

In production, migrations run as a Kubernetes Job before the pipeline deployment:

```yaml
# helm/estategap/templates/migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: estategap-migrate-{{ .Release.Revision }}
spec:
  template:
    spec:
      containers:
        - name: migrate
          image: estategap/pipeline:{{ .Values.pipeline.image.tag }}
          command: ["uv", "run", "alembic", "upgrade", "head"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: estategap-db-secret
                  key: DATABASE_URL
      restartPolicy: OnFailure
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `could not load library "postgis-3.so"` | PostGIS not installed | Use `postgis/postgis:16-3.4` image |
| `function gen_random_uuid() does not exist` | pgcrypto not enabled | Run migration 001 first; don't skip |
| `relation "listings" already exists` | Partial migration state | Run `alembic current` and `alembic stamp` to fix |
| `UNIQUE constraint violation on (source, source_id)` | Duplicate portal listing | Expected behaviour; handle in pipeline dedup step |
| `ERROR: no unique index on "zone_statistics"` | View refreshed before unique index | Migration 009 creates the index; run in order |
