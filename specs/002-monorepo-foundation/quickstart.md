# Developer Quickstart: EstateGap Monorepo

**Feature**: 002-monorepo-foundation  
**Updated**: 2026-04-16

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Go | 1.23+ | https://go.dev/dl/ |
| Python | 3.12+ | via pyenv or system |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| buf | latest | `brew install bufbuild/buf/buf` or https://buf.build/docs/installation |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Node.js | 22+ | https://nodejs.org or `nvm install 22` |
| golangci-lint | latest | `brew install golangci-lint` or https://golangci-lint.run/usage/install/ |

---

## First-time Setup

```bash
# Clone
git clone https://github.com/estategap/estategap.git
cd estategap

# 1. Generate proto stubs (required before Go build)
make proto

# 2. Build all Go services + install Python deps + build frontend
make build-all

# 3. Run all tests
make test

# 4. Run all linters
make lint
```

Total setup time: ~3 minutes on a standard machine.

---

## Working with Go Services

```bash
# Build a specific Go service
cd services/api-gateway
go build ./cmd

# Run tests for one service
go test ./...

# Run tests across the whole workspace
cd /path/to/estategap
go test ./...

# Add a new dependency to a service
cd services/api-gateway
go get github.com/some/pkg

# Use the shared libs/pkg in a service
# In go.mod, libs/pkg is available via go.work — no replace needed.
# Import: import "github.com/estategap/libs/logger"
```

---

## Working with Python Services

```bash
# Install deps for one service
cd services/pipeline
uv sync

# Run linting
uv run ruff check .
uv run mypy --strict .

# Run tests
uv run pytest

# Add a new dependency
uv add some-package

# libs/common is available automatically via uv.lock's path reference
# Import: from estategap_common.models.listing import Listing
```

---

## Working with Proto Files

```bash
# Edit a .proto file
vim proto/estategap/v1/listings.proto

# Regenerate stubs (always commit the output)
make proto

# Lint protos
buf lint

# Check for breaking changes against main
buf breaking --against '.git#branch=main'
```

**Rule**: Always commit generated stubs alongside `.proto` changes. The CI `ci-proto.yml` workflow will fail if you don't.

---

## Working with the Frontend

```bash
cd frontend

# Install deps
npm ci

# Dev server
npm run dev      # http://localhost:3000

# Type check
npx tsc --noEmit

# Lint
npm run lint

# Production build
npm run build
```

---

## Docker Builds

```bash
# Build all images
make docker-build-all

# Build a specific service image
docker build -t estategap/api-gateway:dev services/api-gateway/

# Verify image sizes
docker images | grep estategap
```

Expected sizes: Go services < 20 MB, Python services < 200 MB, frontend < 100 MB.

---

## Adding a New Service

### Go service

1. `mkdir -p services/my-service/{cmd,internal/{handler,middleware,config,grpc}}`
2. `cd services/my-service && go mod init github.com/estategap/services/my-service`
3. Create `cmd/main.go` with minimal `main()`.
4. Add `./services/my-service` to `go.work` (in the `use` block).
5. Copy Dockerfile from an existing Go service and update the binary name.
6. Add the service name to `ci-go.yml` matrix.

### Python service

1. `mkdir -p services/my-service`
2. `cd services/my-service && uv init --name estategap-my-service`
3. Add `estategap-common` path dep: `uv add --editable ../../libs/common`
4. Create `main.py` with minimal async `main()`.
5. Copy Dockerfile from an existing Python service.
6. Add the service name to `ci-python.yml` matrix.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `go build` fails: cannot find module | Run `make proto` first (generates `libs/pkg/proto/`) |
| `uv sync` fails: resolution error | Check `pyproject.toml` for conflicting version constraints |
| `buf generate` fails: plugin not found | Use remote plugins in `buf.gen.yaml` (no local install needed) |
| CI `ci-proto.yml` fails: diff detected | Run `make proto` and commit the updated stubs |
| Go image > 20 MB | Ensure `CGO_ENABLED=0` and distroless base; check for unnecessary files in build context |
| `mypy --strict` errors on empty service | Add `py.typed` marker and ensure `__init__.py` is present |
