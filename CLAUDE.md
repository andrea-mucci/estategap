# estategap Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-16

## Active Technologies
- Go 1.23, Python 3.12, TypeScript 5.x / Node 22 + go.work (multi-module workspace), uv (Python pkg manager), buf (proto codegen), golangci-lint, ruff, mypy, Next.js 15 (002-monorepo-foundation)
- N/A (foundation only — no runtime data layer) (002-monorepo-foundation)
- Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend) + Go — chi, pgx, slog, viper, nats.go, grpc; Python — Pydantic v2, asyncpg, structlog, nats-py, LightGBM, Scrapy, Playwright, LiteLLM, FastAPI; Frontend — Next.js 15, Tailwind CSS 4, shadcn/ui, TanStack Query, Zustand (002-monorepo-foundation)

- Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend) (001-monorepo-foundation)

## Project Structure

```text
src/
tests/
```

## Commands

cd src && pytest && ruff check .

## Code Style

Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend): Follow standard conventions

## Recent Changes
- 002-monorepo-foundation: Added Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend) + Go — chi, pgx, slog, viper, nats.go, grpc; Python — Pydantic v2, asyncpg, structlog, nats-py, LightGBM, Scrapy, Playwright, LiteLLM, FastAPI; Frontend — Next.js 15, Tailwind CSS 4, shadcn/ui, TanStack Query, Zustand
- 002-monorepo-foundation: Added Go 1.23, Python 3.12, TypeScript 5.x / Node 22 + go.work (multi-module workspace), uv (Python pkg manager), buf (proto codegen), golangci-lint, ruff, mypy, Next.js 15

- 001-monorepo-foundation: Added Go 1.23 (Go services + shared libs), Python 3.12 (Python services + shared libs), TypeScript 5.x / Node 22 (Frontend)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
