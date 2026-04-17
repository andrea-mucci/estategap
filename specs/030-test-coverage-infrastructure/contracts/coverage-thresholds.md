# Contract: Coverage Thresholds

**Version**: 1.0  
**Owner**: Engineering Standards  
**Consumers**: CI workflows, `.codecov.yml`, pytest configs, vitest config

## Purpose

Defines the minimum acceptable coverage for each service/module. Encoded in service configuration files — CI reads them automatically.

## Thresholds

| Layer | Service/Module | Statement % | Branch % | Enforced By |
|-------|---------------|-------------|---------|-------------|
| Go | libs/pkg | 80% | — | `scripts/check-go-coverage.sh` |
| Go | api-gateway | 80% | — | `scripts/check-go-coverage.sh` |
| Go | ws-server | 80% | — | `scripts/check-go-coverage.sh` |
| Go | alert-engine | 80% | — | `scripts/check-go-coverage.sh` |
| Go | alert-dispatcher | 80% | — | `scripts/check-go-coverage.sh` |
| Go | scrape-orchestrator | 80% | — | `scripts/check-go-coverage.sh` |
| Go | proxy-manager | 80% | — | `scripts/check-go-coverage.sh` |
| Python | spider-workers | 80% | 80% | `--cov-fail-under=80` in pyproject.toml |
| Python | pipeline | 80% | 80% | `--cov-fail-under=80` in pyproject.toml |
| Python | ml | 80% | 80% | `--cov-fail-under=80` in pyproject.toml |
| Python | ai-chat | 80% | 80% | `--cov-fail-under=80` in pyproject.toml |
| Python | libs/common | 80% | 80% | `--cov-fail-under=80` in pyproject.toml |
| Frontend | frontend | 70% | 70% | `vitest.config.ts` thresholds |

## Per-Service Override Mechanism

To set a stricter threshold for a specific service, modify only that service's config:
- **Go**: Update `COVERAGE_THRESHOLD` in `scripts/check-go-coverage.sh` via service-level override variable.
- **Python**: Set `--cov-fail-under=<N>` in the service's `pyproject.toml`.
- **Frontend**: Modify `coverage.thresholds` in `vitest.config.ts`.

## Codecov PR Comment Format

Codecov posts a PR comment when coverage changes, showing:
- Overall coverage delta (+ or -)
- Per-file coverage diff table
- Files with coverage drops highlighted

Configured via `.codecov.yml` at repository root:
```yaml
comment:
  layout: "diff, files"
  behavior: default
  require_changes: false
```

## Amendment Policy

Threshold reductions require explicit justification in the PR description. Threshold increases are always welcome.
