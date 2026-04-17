# Contract: pytest.ini for tests/usecase/

**File**: `tests/usecase/pytest.ini`

```ini
[pytest]
asyncio_mode = auto
markers =
    usecase: end-to-end user journey tests
    browser: journey tests that require Playwright browser
    slow: journey tests that use time travel or wait for K8s operations
    api: API-only journey tests (no browser, no time travel)
testpaths =
    .
python_files = uj*_test.py
python_classes = TestUJ*
python_functions = test_*
timeout = 300
log_cli = true
log_cli_level = INFO
```

## Marker Combinations

| Journey | Markers |
|---------|---------|
| UJ-01 | usecase, browser |
| UJ-02 | usecase, browser |
| UJ-03 | usecase, api |
| UJ-04 | usecase, api |
| UJ-05 | usecase, browser |
| UJ-06 | usecase, browser |
| UJ-07 | usecase, browser, slow |
| UJ-08 | usecase, api, slow |
| UJ-09 | usecase, api |
| UJ-10 | usecase, browser |
| UJ-11 | usecase, api |
| UJ-12 | usecase, api, slow |
| UJ-13 | usecase, browser |
| UJ-14 | usecase, browser |
| UJ-15 | usecase, api |

## Useful Invocations

```bash
# All journeys
pytest -v

# Fast subset (CI on PRs)
pytest -m "usecase and not slow" -v

# Browser journeys only
pytest -m "browser" -v

# Single journey
pytest uj03_alert_notification_test.py -v

# With headful browser
PLAYWRIGHT_HEADLESS=false pytest -m "browser" -v -s
```
