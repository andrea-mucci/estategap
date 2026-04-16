# Makefile Targets Contract

**Branch**: `001-monorepo-foundation` | **Date**: 2026-04-16

## Root Makefile Targets

| Target | Description | Command(s) |
|--------|-------------|------------|
| `proto` | Generate Go and Python stubs from proto files | `buf generate` |
| `test` | Run all tests across Go workspace and Python services | `go test ./...` (from workspace root) + `uv run pytest` in each Python service |
| `lint` | Run all linters | `golangci-lint run ./...` + `ruff check` + `mypy --strict` per Python service |
| `build-all` | Compile all Go binaries and install Python deps | `go build ./...` + `uv sync` per Python service + `npm run build` in frontend |
| `docker-build-all` | Build all Docker images | `docker build` for every service + frontend |

## Makefile Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REGISTRY` | `ghcr.io/estategap` | Docker registry prefix |
| `TAG` | `dev` | Image tag |
| `PYTHON_SERVICES` | `spider-workers pipeline ml ai-chat` | List for looping |
| `GO_SERVICES` | `api-gateway ws-server scrape-orchestrator proxy-manager alert-engine alert-dispatcher` | List for looping |

## CI Workflow Triggers

| Workflow | Trigger Paths | Jobs |
|----------|--------------|------|
| `ci-go.yml` | `services/**/*.go`, `libs/pkg/**`, `proto/**`, `.github/workflows/ci-go.yml` | lint, test, build |
| `ci-python.yml` | `services/spider-workers/**`, `services/pipeline/**`, `services/ml/**`, `services/ai-chat/**`, `libs/common/**`, `.github/workflows/ci-python.yml` | ruff, mypy, pytest |
| `ci-frontend.yml` | `frontend/**`, `.github/workflows/ci-frontend.yml` | eslint, tsc, next-build |
| `ci-proto.yml` | `proto/**`, `.github/workflows/ci-proto.yml` | buf-lint, buf-generate+diff |
