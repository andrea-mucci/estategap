# Frontend Contract Fixtures

These fixtures capture representative API responses used by frontend tests and MSW handlers.

Update this directory whenever the response schema in `services/api-gateway/openapi.yaml` changes.

Use `make update-contracts` to regenerate frontend API types before adjusting these fixtures.

The committed JSON files in this directory are the source of truth for mock responses used in unit and contract-style frontend tests.
