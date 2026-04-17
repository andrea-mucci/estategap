# Validation Results

Date: 2026-04-17
Feature: `029-kind-helm-validation`

## Executed

| Command | Result | Notes |
|---|---|---|
| `python -m py_compile services/spider-workers/estategap_spiders/spiders/fixture_spider.py services/spider-workers/estategap_spiders/consumer.py services/spider-workers/estategap_spiders/settings.py services/ai-chat/estategap_ai_chat/providers/fake_provider.py services/ai-chat/estategap_ai_chat/providers/__init__.py services/ai-chat/estategap_ai_chat/config.py libs/common/estategap_common/time_util.py tests/fixtures/load.py tests/fixtures/ml-models/generate.py tests/helm/conformance.py` | PASS | Syntax check for modified Python files |
| `GOCACHE=/tmp/go-build-cache go test ./libs/pkg/timeutil` | PASS | New Go time override helper and tests |
| `PYTHONPATH=/root/projects/estategap/services/ai-chat:/root/projects/estategap/libs/common:/root/projects/estategap/libs/common/proto libs/common/.venv/bin/python -m pytest services/ai-chat/tests/unit/test_providers.py` | PASS | Fake LLM provider selection verified |
| `libs/common/.venv/bin/python -m pytest libs/common/tests/test_time_util.py` | PASS | Python time override helper verified |
| `bash tests/helm/schema-test.sh` | PASS | Schema rejects invalid values |

## Blocked

| Command | Result | Notes |
|---|---|---|
| `make helm-lint` | BLOCKED | Missing Helm dependency charts in `helm/estategap/charts/` (`nats`, `cloudnative-pg`, `redis`, `kube-prometheus-stack`, `loki-stack`, `tempo`, `keda`) |
| `make helm-test` | BLOCKED | `helm-unittest` plugin is not installed; installing it requires network access |
| `tests/helm/conformance.py` | BLOCKED | Chart dependencies are missing locally; direct execution also needs a Python env with `PyYAML` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run --project tests/fixtures python tests/fixtures/ml-models/generate.py` | BLOCKED | `onnxruntime`, `numpy`, `scikit-learn`, and `skl2onnx` are not installed and cannot be fetched offline |
| Cluster-based validation (`make kind-reset`, `bash tests/helm/install-test.sh`, `bash tests/helm/upgrade-test.sh`) | BLOCKED | `kubectl` and `docker` are not available in this sandbox |

## Notes

- `helm lint` no longer fails on a nil `testMode` lookup after making the chart templates nil-safe.
- ONNX artifacts were not generated in this environment, so task `T051` remains open.
- Final acceptance validation remains open until chart dependencies and cluster tooling are available.
