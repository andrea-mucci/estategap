# Feature: Repository & Tooling Setup

## /specify prompt

```
Build the monorepo foundation for the EstateGap platform.

## What
A monorepo with the following structure:
- services/ directory with subdirectories for each microservice: api-gateway (Go), ws-server (Go), scrape-orchestrator (Go), proxy-manager (Go), alert-engine (Go), alert-dispatcher (Go), spider-workers (Python), pipeline (Python), ml (Python), ai-chat (Python)
- frontend/ directory for the Next.js application
- proto/ directory for shared Protobuf definitions with buf configuration
- helm/estategap/ for Helm charts
- libs/ for shared code: Go pkg/ (logger, config, NATS wrapper, gRPC helpers) and Python libs/common/ (Pydantic models, NATS wrapper, DB session, logging)
- Root Makefile with targets: proto (generate), test, lint, build-all, docker-build-all

## Why
All services must be buildable, testable, and deployable from a single repository. Shared contracts (Protobuf) and models (Pydantic/Go structs) ensure consistency. CI pipelines must validate all services on every PR.

## Users
- Developers working on the platform
- CI/CD pipeline

## Acceptance Criteria
- `tree -L 3` matches the defined structure
- Go workspace (`go.work`) links all Go services. `go build ./...` succeeds.
- Python services use uv. `uv sync` succeeds in each service. `ruff check` and `mypy` pass.
- `buf generate` produces Go and Python stubs from proto/ definitions.
- Multi-stage Dockerfiles for all services: Go images < 20MB, Python < 200MB, Frontend < 100MB.
- GitHub Actions CI: lint + test + build for Go, Python, and Frontend. All pass on empty codebase.
```
