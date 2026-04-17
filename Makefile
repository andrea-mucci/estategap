REGISTRY ?= ghcr.io/estategap
TAG ?= dev
GO_SERVICES := api-gateway ws-server scrape-orchestrator proxy-manager alert-engine alert-dispatcher
GO_MODULE_DIRS := libs/pkg $(addprefix services/,$(GO_SERVICES))
GO_INTEGRATION_MODULE_DIRS := $(filter-out libs/pkg,$(GO_MODULE_DIRS))
PYTHON_SERVICES := spider-workers pipeline ml ai-chat
PYTHON_PROJECT_DIRS := libs/common $(addprefix services/,$(PYTHON_SERVICES))
PYTHON_INTEGRATION_DIRS := $(addprefix services/,$(PYTHON_SERVICES))
GOCACHE ?= /tmp/estategap-go-cache
UV_CACHE_DIR ?= /tmp/estategap-uv-cache
ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
GO_COVERAGE_CHECK := $(ROOT_DIR)/scripts/check-go-coverage.sh

include mk/kind.mk

.PHONY: proto test test-unit test-integration coverage update-contracts lint build-all docker-build-all

proto:
	@command -v buf >/dev/null 2>&1 || { echo "buf is required to run make proto"; exit 1; }
	buf generate

test: test-unit test-integration

test-unit:
	@for dir in $(GO_MODULE_DIRS); do \
		echo "==> $$dir"; \
		(cd $$dir && GOCACHE=$(GOCACHE) go test -race -coverprofile=coverage.out -covermode=atomic -tags '!integration' ./...); \
		COVERAGE_THRESHOLD=$${COVERAGE_THRESHOLD:-80} $(GO_COVERAGE_CHECK) "$$dir/coverage.out"; \
	done
	@for dir in $(PYTHON_PROJECT_DIRS); do \
		echo "==> $$dir"; \
		(cd $$dir && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -m "not integration and not slow"); \
	done
	@(cd frontend && npm run test)

test-integration:
	@for dir in $(GO_INTEGRATION_MODULE_DIRS); do \
		echo "==> $$dir"; \
		(cd $$dir && GOCACHE=$(GOCACHE) go test -race -tags integration ./...); \
	done
	@for dir in $(PYTHON_INTEGRATION_DIRS); do \
		echo "==> $$dir"; \
		(cd $$dir && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -m integration); \
	done
	@UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --project services/pipeline pytest tests/integration/cross_service/
	@UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --project services/pipeline pytest tests/integration/test_pipeline_e2e.py

coverage:
	@for dir in $(GO_MODULE_DIRS); do \
		echo "==> $$dir"; \
		(cd $$dir && if [ ! -f coverage.out ]; then GOCACHE=$(GOCACHE) go test -coverprofile=coverage.out -covermode=atomic -tags '!integration' ./...; fi && go tool cover -html=coverage.out -o coverage.html); \
	done
	@for dir in $(PYTHON_PROJECT_DIRS); do \
		echo "==> $$dir"; \
		(cd $$dir && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest --cov-report=html -m "not integration and not slow"); \
	done
	@(cd frontend && npm run test:coverage)

update-contracts:
	@(cd frontend && npm run generate-api-types)

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
