# Developer Quickstart: EstateGap Monorepo

**Branch**: `001-monorepo-foundation` | **Date**: 2026-04-16

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Go | 1.23+ | https://go.dev/dl/ |
| Python | 3.12+ | https://python.org or `pyenv install 3.12` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| buf | latest | `brew install bufbuild/buf/buf` or https://buf.build/docs/installation |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Node.js | 22+ | `nvm install 22` or https://nodejs.org |
| golangci-lint | latest | `brew install golangci-lint` |

## Clone and Bootstrap

```bash
git clone git@github.com:estategap/estategap.git
cd estategap

# Generate proto stubs (required before Go build)
make proto

# Build everything
make build-all

# Run all tests
make test

# Run all linters
make lint
```

## Working with Go Services

```bash
# Build a specific Go service
cd services/api-gateway
go build ./cmd/...

# Run tests for a specific service
go test ./...

# Run all Go tests from workspace root
cd /path/to/estategap
go test ./...

# Lint
golangci-lint run ./...
```

All Go services are linked in `go.work`. You never need to `go get` the shared `libs/pkg` — it resolves locally.

## Working with Python Services

```bash
# Setup a specific Python service
cd services/pipeline
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run mypy --strict .

# Run the service
uv run python main.py
```

The `libs/common` package is declared as a local path dependency in each service's `pyproject.toml`:
```toml
[tool.uv.sources]
estategap-common = { path = "../../libs/common", editable = true }
```

## Working with Proto

```bash
# Regenerate all stubs after a .proto change
make proto
# Equivalent to: buf generate

# Lint proto files
buf lint proto/

# Check for breaking changes against main
buf breaking proto/ --against '.git#branch=main'
```

Generated stubs land in:
- `libs/pkg/proto/` — Go stubs (imported as `github.com/estategap/libs/proto/v1`)
- `libs/common/estategap_common/proto/` — Python stubs

**Always commit generated stubs** alongside `.proto` changes. CI will fail if there's a diff.

## Working with the Frontend

```bash
cd frontend
npm install
npm run dev     # development server at localhost:3000
npm run build   # production build (Next.js standalone)
npm run lint    # eslint
npx tsc --noEmit  # type check
```

## Building Docker Images

```bash
# Build all images
make docker-build-all

# Build a specific service
docker build -t ghcr.io/estategap/api-gateway:dev services/api-gateway/
docker build -t ghcr.io/estategap/pipeline:dev services/pipeline/

# Inspect image sizes
docker images | grep estategap
```

Expected sizes:
- Go services: < 20 MB (distroless static)
- Python services: < 200 MB (python:3.12-slim)
- Frontend: < 100 MB (node:22-alpine with standalone)

## Environment Variables

All services configure themselves from environment variables only (12-factor). Each service directory contains a `.env.example` file listing required variables. Copy to `.env` for local development:

```bash
cp services/api-gateway/.env.example services/api-gateway/.env
```

Common variables across all services:

| Variable | Description |
|----------|-------------|
| `NATS_URL` | NATS JetStream URL, e.g. `nats://localhost:4222` |
| `LOG_LEVEL` | `debug`, `info`, `warn`, `error` |
| `SERVICE_ENV` | `development`, `staging`, `production` |

## Running CI Locally

```bash
# Simulate ci-go.yml
golangci-lint run ./...
go test ./...
go build ./...

# Simulate ci-python.yml (repeat for each service)
cd services/pipeline
uv run ruff check .
uv run mypy --strict .
uv run pytest

# Simulate ci-proto.yml
buf lint proto/
buf generate
git diff --exit-code  # should be empty
```

## Adding a New Go Service

1. Create `services/<name>/` directory.
2. Run `go mod init github.com/estategap/services/<name>` inside it.
3. Create `cmd/main.go` with a minimal `main()`.
4. Add `use ./services/<name>` to `go.work`.
5. Add a `Dockerfile` following the existing Go multi-stage pattern.
6. Add the service name to `GO_SERVICES` in the root `Makefile`.

## Adding a New Python Service

1. Create `services/<name>/` directory.
2. Run `uv init` inside it to create `pyproject.toml`.
3. Add `estategap-common` as a path dependency.
4. Create `main.py` with a minimal entrypoint.
5. Add a `Dockerfile` following the existing Python multi-stage pattern.
6. Add the service name to `PYTHON_SERVICES` in the root `Makefile`.
