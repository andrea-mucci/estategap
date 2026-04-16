REGISTRY ?= ghcr.io/estategap
TAG ?= dev
GO_SERVICES := api-gateway ws-server scrape-orchestrator proxy-manager alert-engine alert-dispatcher
GO_MODULE_DIRS := libs/pkg $(addprefix services/,$(GO_SERVICES))
PYTHON_SERVICES := spider-workers pipeline ml ai-chat
GOCACHE ?= /tmp/estategap-go-cache
UV_CACHE_DIR ?= /tmp/estategap-uv-cache

.PHONY: proto test lint build-all docker-build-all

proto:
	@command -v buf >/dev/null 2>&1 || { echo "buf is required to run make proto"; exit 1; }
	buf generate

test:
	@for dir in $(GO_MODULE_DIRS); do \
		(cd $$dir && GOCACHE=$(GOCACHE) go test ./...); \
	done
	@for svc in $(PYTHON_SERVICES); do \
		(cd services/$$svc && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -x); \
	done
	@UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --project services/pipeline pytest tests/integration/test_schema -v --tb=short

lint:
	@command -v golangci-lint >/dev/null 2>&1 || { echo "golangci-lint is required to run make lint"; exit 1; }
	@command -v buf >/dev/null 2>&1 || { echo "buf is required to run make lint"; exit 1; }
	@for dir in $(GO_MODULE_DIRS); do \
		(cd $$dir && GOCACHE=$(GOCACHE) golangci-lint run ./...); \
	done
	buf lint
	@for svc in $(PYTHON_SERVICES); do \
		(cd services/$$svc && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff check . && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run mypy --strict .); \
	done
	@(cd services/pipeline && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff check src/pipeline ../../libs/common/estategap_common/models ../../tests/integration/test_schema && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run mypy --strict src/pipeline ../../libs/common/estategap_common/models ../../tests/integration/test_schema)
	@(cd frontend && npm run lint)

build-all:
	@for svc in $(GO_SERVICES); do \
		(cd services/$$svc && GOCACHE=$(GOCACHE) go build -o /tmp/estategap-$$svc ./cmd); \
	done
	@for svc in $(PYTHON_SERVICES); do \
		(cd services/$$svc && UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync); \
	done
	@(cd frontend && npm ci && npm run build)

docker-build-all:
	@for svc in $(GO_SERVICES) $(PYTHON_SERVICES); do \
		docker build -t $(REGISTRY)/$$svc:$(TAG) -f services/$$svc/Dockerfile .; \
	done
	docker build -t $(REGISTRY)/frontend:$(TAG) -f frontend/Dockerfile .
