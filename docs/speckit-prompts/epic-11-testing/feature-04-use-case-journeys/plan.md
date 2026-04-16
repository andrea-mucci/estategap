# Feature: Use Case / User Journey Tests

## /plan prompt

```
Implement with these technical decisions:

## Stack
- **Orchestrator:** Python with pytest (matches API test stack, easier for backend assertions)
- **Browser automation:** Playwright (called from Python via `playwright` Python binding) for UJ tests that involve UI
- **Rationale:** Use Python to coordinate multi-service assertions (DB queries, NATS inspection, pod logs) while Playwright handles UI automation. Pure-browser tests for frontend flows live in `frontend/tests/e2e/` (previous feature).

## Directory Structure
tests/usecase/
├── conftest.py                   # Shared fixtures, cluster helpers
├── helpers/
│   ├── api.py                    # API client
│   ├── ws.py                     # WebSocket client
│   ├── browser.py                # Playwright wrapper
│   ├── cluster.py                # K8s helpers (kubectl, logs, exec)
│   ├── db.py                     # Direct DB queries for verification
│   ├── fixtures.py               # Test data injection (listings, price changes)
│   ├── time_travel.py            # NOW_OVERRIDE helpers
│   └── assertions.py             # Business-level assertions
├── uj01_onboarding_test.py
├── uj02_find_deal_test.py
├── uj03_alert_notification_test.py
├── uj04_ai_chat_to_alert_test.py
├── uj05_subscription_upgrade_test.py
├── uj06_portfolio_multi_currency_test.py
├── uj07_admin_retrain_ml_test.py
├── uj08_free_tier_delay_test.py
├── uj09_multi_country_search_test.py
├── uj10_gdpr_export_delete_test.py
├── uj11_price_drop_engagement_test.py
├── uj12_scraping_recovery_test.py
├── uj13_language_switch_test.py
├── uj14_websocket_reconnect_test.py
├── uj15_scrape_to_alert_latency_test.py
└── pytest.ini

## Test Base Class

```python
# conftest.py
@pytest.fixture(scope="class")
async def cluster():
    """Verifies cluster is deployed and seeded before tests run."""
    helper = ClusterHelper()
    assert helper.is_ready(), "Kind cluster must be deployed"
    assert helper.fixtures_loaded(), "Run `make kind-seed` first"
    yield helper

@pytest.fixture(scope="function")
async def test_context(cluster, request):
    """Per-test context with cleanup."""
    context = TestContext(
        cluster=cluster,
        test_name=request.node.name,
        start_time=datetime.now(tz=UTC),
    )
    yield context
    # Cleanup: truncate mutable tables for this test
    await context.cleanup()
    # Collect artifacts if test failed
    if request.node.rep_call.failed:
        await context.collect_failure_artifacts()
```

## Example: UJ-02 Implementation

```python
# uj02_find_deal_test.py
import pytest
from playwright.async_api import async_playwright
from helpers.api import ApiClient
from helpers.db import DbClient

@pytest.mark.asyncio
@pytest.mark.usecase
class TestUJ02FindDeal:
    """UJ-02: Find a Tier 1 Deal via Search"""

    async def test_find_tier1_deal(self, test_context):
        """
        Given: Pro user logged in, 50 Tier 1 deals in Madrid fixture
        When: User searches with filters and clicks top result
        Then: Detail page shows all expected sections with correct data
        """
        # --- Given ---
        api = ApiClient.login("test-pro@estategap.test", "TestPass123!")

        # Verify fixture expectations
        db = DbClient.connect()
        tier1_count = await db.count_listings(country="ES", city="Madrid", tier=1, status="active")
        assert tier1_count >= 20, f"Fixture should have ≥ 20 Tier 1 Madrid listings, found {tier1_count}"

        # --- When ---
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()

            # Inject auth cookie
            await page.context.add_cookies([{
                "name": "session",
                "value": api.session_token,
                "domain": "localhost",
                "path": "/"
            }])

            start = time.time()

            # Navigate to search with filters
            await page.goto("http://localhost:3000/search?country=ES&city=Madrid&deal_tier=1")
            await page.wait_for_selector('[data-testid="listing-card"]')

            # Verify sort order
            cards = page.locator('[data-testid="listing-card"]')
            count = await cards.count()
            assert count >= 20

            # Get deal_scores from cards (in display order)
            scores = []
            for i in range(min(count, 10)):
                score_text = await cards.nth(i).locator('[data-testid="deal-score"]').text_content()
                scores.append(float(score_text.strip().replace("%", "")))

            # Scores should be descending
            assert scores == sorted(scores, reverse=True), f"Results not sorted by deal_score: {scores}"

            # Click top result
            top_listing_id = await cards.nth(0).get_attribute('data-listing-id')
            await cards.nth(0).click()
            await page.wait_for_url(f"**/listing/{top_listing_id}")

            # --- Then ---
            detail_load_time = time.time() - start
            assert detail_load_time < 5, f"Detail page took {detail_load_time}s (should be < 5s)"

            # All sections present
            await page.wait_for_selector('[data-testid="photo-gallery"]')
            await page.wait_for_selector('[data-testid="key-stats"]')
            await page.wait_for_selector('[data-testid="deal-score-card"]')
            await page.wait_for_selector('[data-testid="shap-chart"]')
            await page.wait_for_selector('[data-testid="price-history"]')
            await page.wait_for_selector('[data-testid="comparables"]')
            await page.wait_for_selector('[data-testid="mini-map"]')

            # Deal score ≥ 70 (Tier 1 threshold)
            deal_score_text = await page.locator('[data-testid="deal-score-value"]').text_content()
            deal_score = float(deal_score_text.replace("%", ""))
            assert deal_score >= 70, f"Tier 1 should have score ≥ 70, got {deal_score}"

            # SHAP chart has 5 factors
            shap_bars = page.locator('[data-testid="shap-factor"]')
            assert await shap_bars.count() == 5

            # Confidence range displayed
            confidence = await page.locator('[data-testid="confidence-range"]').text_content()
            assert "€" in confidence and " - " in confidence

            # 5 comparables
            comps = page.locator('[data-testid="comparable-card"]')
            assert await comps.count() == 5

            # Verify comparables are in Madrid and similar size
            listing = await api.get_listing(top_listing_id)
            comp_ids = await page.locator('[data-testid="comparable-card"]').evaluate_all(
                "(els) => els.map(e => e.dataset.listingId)"
            )
            for comp_id in comp_ids:
                comp = await api.get_listing(comp_id)
                assert comp["city"] == listing["city"]
                assert abs(comp["built_area_m2"] - listing["built_area_m2"]) / listing["built_area_m2"] < 0.2

            await browser.close()
```

## Example: UJ-03 Implementation (Multi-Service)

```python
# uj03_alert_notification_test.py
@pytest.mark.asyncio
@pytest.mark.usecase
class TestUJ03AlertNotification:
    """UJ-03: Create Alert Rule and Receive Notification via All Channels"""

    async def test_alert_multi_channel(self, test_context):
        # --- Given ---
        api = ApiClient.login("test-pro@estategap.test", "TestPass123!")

        # Create alert rule
        rule = await api.create_alert_rule({
            "name": "UJ-03 Test",
            "countries": ["ES"],
            "zones": [chamberí_zone_id],
            "filters": {
                "property_type": "flat",
                "max_price": 600000,
            },
            "min_deal_tier": 2,
            "channels": ["email", "telegram", "websocket"],
            "frequency": "instant",
        })
        assert rule["is_active"] == True

        # Connect WebSocket (in separate task)
        ws_client = WSClient(api.session_token)
        ws_messages = []

        async def collect_ws():
            async for msg in ws_client:
                ws_messages.append(msg)

        ws_task = asyncio.create_task(collect_ws())

        # Email spy: api-gateway in test mode logs email sends to Redis instead of SES
        email_spy = EmailSpy()

        # Telegram spy: ws-server in test mode logs Telegram sends to Redis instead of Bot API
        telegram_spy = TelegramSpy()

        # --- When ---
        # Inject a matching listing into the pipeline
        listing = {
            "source": "test-fixture",
            "source_id": "uj03-test-listing",
            "country": "ES",
            "city": "Madrid",
            "zone_id": chamberí_zone_id,
            "address": "Calle Test 42",
            "location": {"lat": 40.434, "lng": -3.697},
            "asking_price": 450000,
            "built_area_m2": 85,
            "bedrooms": 2,
            "bathrooms": 2,
            "property_type": "flat",
            "property_category": "residential",
            "published_at": datetime.now(tz=UTC).isoformat(),
        }

        # Publish raw listing to NATS (triggers full pipeline)
        nats = NATSClient.connect()
        await nats.publish("raw.listings.es", json.dumps(listing).encode())

        # Wait up to 60s for all 3 channels to fire
        start = time.time()
        deadline = start + 60

        while time.time() < deadline:
            email_hit = await email_spy.received_for(user=api.user["email"])
            telegram_hit = await telegram_spy.received_for(user=api.user["telegram_chat_id"])
            ws_hit = any(m["type"] == "deal_alert" for m in ws_messages)

            if email_hit and telegram_hit and ws_hit:
                break
            await asyncio.sleep(1)

        latency = time.time() - start

        # --- Then ---
        assert email_hit, "Email alert not received within 60s"
        assert telegram_hit, "Telegram alert not received within 60s"
        assert ws_hit, "WebSocket alert not received within 60s"
        assert latency < 60, f"End-to-end latency {latency}s exceeded 60s target"

        # Verify alert_log entries in DB
        db = DbClient.connect()
        alert_log_entries = await db.fetch("""
            SELECT channel, status FROM alert_log
            WHERE rule_id = $1 AND listing_id = (SELECT id FROM listings WHERE source_id = $2)
        """, rule["id"], "uj03-test-listing")

        channels_fired = {entry["channel"] for entry in alert_log_entries}
        assert channels_fired == {"email", "telegram", "websocket"}

        ws_task.cancel()
```

## Helpers

### ClusterHelper
```python
class ClusterHelper:
    def is_ready(self) -> bool:
        """Check all expected deployments are ready."""
        result = subprocess.run(
            ["kubectl", "get", "deployments", "-A", "-o", "json"],
            capture_output=True, text=True
        )
        deployments = json.loads(result.stdout)
        for dep in deployments["items"]:
            if not dep["metadata"]["namespace"].startswith("estategap-"):
                continue
            spec_replicas = dep["spec"]["replicas"]
            ready = dep["status"].get("readyReplicas", 0)
            if ready != spec_replicas:
                return False
        return True

    def get_pod_logs(self, namespace: str, selector: str) -> str:
        return subprocess.run(
            ["kubectl", "logs", "-n", namespace, "-l", selector, "--tail=1000"],
            capture_output=True, text=True
        ).stdout

    def exec_in_pod(self, namespace: str, pod: str, cmd: list[str]) -> str:
        return subprocess.run(
            ["kubectl", "exec", "-n", namespace, pod, "--"] + cmd,
            capture_output=True, text=True
        ).stdout
```

### TimeTravel
```python
class TimeTravel:
    """Set NOW_OVERRIDE in services via ConfigMap update + pod restart."""
    @staticmethod
    async def set_time(timestamp: datetime):
        iso = timestamp.isoformat()
        subprocess.run([
            "kubectl", "patch", "configmap", "estategap-runtime",
            "-n", "estategap-system",
            "--type", "merge",
            "-p", json.dumps({"data": {"NOW_OVERRIDE": iso}})
        ])
        # Restart affected deployments
        for deployment in ["api-gateway", "alert-engine"]:
            subprocess.run([
                "kubectl", "rollout", "restart", f"deployment/{deployment}",
                "-n", "estategap-gateway"
            ])
            subprocess.run([
                "kubectl", "rollout", "status", f"deployment/{deployment}",
                "-n", "estategap-gateway",
                "--timeout=2m"
            ])

    @staticmethod
    async def advance_hours(hours: int):
        current = await TimeTravel.get_time()
        await TimeTravel.set_time(current + timedelta(hours=hours))
```

### Failure Artifact Collection
```python
class TestContext:
    async def collect_failure_artifacts(self):
        """Called automatically when test fails."""
        artifact_dir = Path(f"test-artifacts/{self.test_name}")
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Pod logs
        for ns in ["estategap-gateway", "estategap-scraping", "estategap-pipeline",
                   "estategap-intelligence", "estategap-notifications", "estategap-system"]:
            logs = self.cluster.get_pod_logs(ns, "")
            (artifact_dir / f"logs-{ns}.txt").write_text(logs)

        # DB snapshot
        dump = self.cluster.exec_in_pod(
            "estategap-system", "postgres-primary-0",
            ["pg_dump", "-U", "estategap", "estategap"]
        )
        (artifact_dir / "db-snapshot.sql").write_text(dump)

        # NATS stream state
        streams = self.cluster.exec_in_pod(
            "estategap-system", "nats-0",
            ["nats", "stream", "ls", "--json"]
        )
        (artifact_dir / "nats-streams.json").write_text(streams)
```

## Performance Assertions

Each UJ test records latency and compares against baseline:

```python
from statistics import mean

BASELINES = {
    "uj02_search_to_detail": 3.0,  # seconds
    "uj03_alert_latency": 15.0,
    "uj04_ai_to_alert": 30.0,
    # ...
}

def assert_within_baseline(test_name: str, actual: float):
    baseline = BASELINES[test_name]
    if actual > baseline * 1.2:
        pytest.fail(f"{test_name} took {actual}s, baseline {baseline}s (>20% regression)")
    elif actual > baseline:
        warnings.warn(f"{test_name} took {actual}s, baseline {baseline}s (small regression)")
```

## Makefile & CI

```make
test-usecase: kind-deploy kind-seed
    cd tests/usecase && pytest -v --junitxml=../../reports/usecase.xml

test-usecase-uj: kind-deploy kind-seed
    # Run single journey: make test-usecase-uj UJ=02
    cd tests/usecase && pytest -v uj$(UJ)_*.py
```

## Documentation

File `docs/test-scenarios.md`:
- Purpose of use case tests
- Given/When/Then for each of the 15 journeys
- How to run locally
- How to debug failures
- How to add a new journey
```
