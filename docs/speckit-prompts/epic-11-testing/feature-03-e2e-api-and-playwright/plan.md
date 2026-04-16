# Feature: E2E Test Suite (API + Playwright)

## /plan prompt

```
Implement with these technical decisions:

## Stack
- **API tests:** Python with `pytest` + `httpx` + `websockets` library
- **Browser tests:** Playwright (TypeScript) — more mature than Python variant, better tooling
- **Test runner orchestration:** Makefile + bash scripts
- **Cluster target:** local kind (via `make kind-deploy`) or CI kind

## Directory Structure
tests/e2e/
├── api/                          # REST API tests (Python)
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_listings.py
│   ├── test_zones.py
│   ├── test_alerts.py
│   ├── test_subscriptions.py
│   ├── test_rate_limiting.py
│   └── fixtures/
├── websocket/                    # WebSocket tests (Python)
│   ├── conftest.py
│   ├── test_chat_protocol.py
│   ├── test_notifications.py
│   └── test_reconnection.py
├── concurrency/                  # Concurrency tests (Python)
│   ├── test_concurrent_search.py
│   └── test_concurrent_chat.py
├── helpers/
│   ├── client.py                 # API client wrapper with auth helpers
│   ├── ws_client.py              # WebSocket test client
│   ├── fixtures.py               # Test data loaders
│   └── assertions.py             # Custom assertions
└── pytest.ini

frontend/tests/e2e/
├── playwright.config.ts
├── fixtures/
│   ├── users.ts
│   └── auth.ts
├── pages/                        # Page Object Model
│   ├── LandingPage.ts
│   ├── LoginPage.ts
│   ├── ChatPage.ts
│   ├── SearchPage.ts
│   ├── ListingDetailPage.ts
│   ├── DashboardPage.ts
│   └── AdminPage.ts
├── specs/
│   ├── auth.spec.ts
│   ├── ai-chat.spec.ts
│   ├── search.spec.ts
│   ├── listing-detail.spec.ts
│   ├── dashboard.spec.ts
│   ├── map.spec.ts
│   ├── alerts.spec.ts
│   ├── subscription.spec.ts
│   ├── admin.spec.ts
│   ├── responsive.spec.ts
│   └── accessibility.spec.ts
├── visual/
│   ├── baselines/
│   └── visual-regression.spec.ts
└── utils/
    ├── mock-stripe.ts
    ├── mock-google-oauth.ts
    └── mock-voice.ts

## API Test Infrastructure

conftest.py pattern:
```python
@pytest.fixture(scope="session")
def api_base_url():
    return os.getenv("API_BASE_URL", "http://localhost:8080")

@pytest.fixture(scope="session")
def test_users():
    """Pre-loaded test users per subscription tier."""
    return {
        "free": {"email": "test-free@estategap.test", "password": "..."},
        "basic": {"email": "test-basic@estategap.test", "password": "..."},
        "pro": {"email": "test-pro@estategap.test", "password": "..."},
        "admin": {"email": "test-admin@estategap.test", "password": "..."},
    }

@pytest.fixture
async def authed_client(api_base_url, test_users, request):
    """Authenticated HTTP client for a specific tier."""
    tier = request.param if hasattr(request, "param") else "pro"
    user = test_users[tier]

    async with httpx.AsyncClient(base_url=api_base_url) as client:
        login = await client.post("/api/v1/auth/login", json=user)
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client
```

## Rate Limiting Test
```python
@pytest.mark.parametrize("tier,limit", [
    ("free", 30),
    ("basic", 120),
    ("pro", 300),
])
async def test_rate_limit_per_tier(tier, limit, test_users):
    async with httpx.AsyncClient(base_url="http://localhost:8080") as client:
        # Login
        login = await client.post("/api/v1/auth/login", json=test_users[tier])
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        # Burst requests
        responses = []
        for i in range(limit + 5):
            r = await client.get("/api/v1/listings")
            responses.append(r.status_code)

        # First `limit` succeed, rest return 429
        assert responses[:limit].count(200) == limit
        assert responses[limit] == 429

        # Verify Retry-After header
        r429 = await client.get("/api/v1/listings")
        assert "Retry-After" in r429.headers
```

## WebSocket Test Client
```python
class WSTestClient:
    def __init__(self, url: str, token: str):
        self.url = f"{url}?token={token}"
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.received: list[dict] = []

    async def __aenter__(self):
        self.ws = await websockets.connect(self.url)
        return self

    async def send_chat(self, text: str, session_id: str | None = None):
        await self.ws.send(json.dumps({
            "type": "chat_message",
            "session_id": session_id,
            "payload": {"text": text}
        }))

    async def collect_messages(self, until_type: str, timeout: float = 30):
        """Collect messages until one with the specified type arrives."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=5))
            self.received.append(msg)
            if msg["type"] == until_type:
                return self.received
        raise TimeoutError(f"Never received message of type {until_type}")
```

## Test Data Reset
- Before test suite: `tests/fixtures/load.py --reset`
- Between test classes: `pytest` fixture with `scope="class"` that truncates mutable tables (alert_log, ai_conversations, ai_messages, user_actions)
- Static tables (users, listings, zones) remain loaded

## Playwright Configuration
```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './specs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: [['html'], ['junit', { outputFile: 'results.xml' }]],
  use: {
    baseURL: process.env.FRONTEND_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'mobile-chrome', use: { ...devices['Pixel 7'] } },
  ],
})
```

## Page Object Model Example
```typescript
// pages/ChatPage.ts
export class ChatPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/')
  }

  async sendMessage(text: string) {
    await this.page.fill('[data-testid="chat-input"]', text)
    await this.page.click('[data-testid="chat-send"]')
  }

  async waitForAssistantResponse() {
    await this.page.waitForSelector('[data-testid="assistant-message"]:last-child[data-complete="true"]', { timeout: 30000 })
  }

  async clickChip(label: string) {
    await this.page.click(`[data-testid="chip"]:has-text("${label}")`)
  }

  async confirmCriteria() {
    await this.page.click('[data-testid="confirm-search"]')
  }

  async getResultCount(): Promise<number> {
    const count = await this.page.locator('[data-testid="listing-card"]').count()
    return count
  }
}
```

## data-testid Convention
- Every interactive element in the frontend gets a `data-testid` attribute
- Convention: `<component-name>-<element-purpose>` (e.g., `chat-input`, `listing-card-favorite`, `alert-form-submit`)
- Linter rule prevents shipping components without data-testid on key elements

## Mock Setup for Tests
- **Stripe:** Frontend detects `ESTATEGAP_TEST_MODE` and uses Stripe test publishable key with test cards. Backend accepts test webhook signatures.
- **Google OAuth:** Playwright intercepts OAuth redirect → responds with mock user info
- **Voice input:** Playwright injects `window.SpeechRecognition` mock that returns preset transcriptions
- **LLM:** Backend uses FakeLLMProvider in test mode (covered in epic 7 tests)

## Visual Regression
- Baseline screenshots stored in `frontend/tests/e2e/visual/baselines/`
- Updated via `pnpm test:visual --update-snapshots`
- Reviewed in PR diff (GitHub shows image comparison)
- Key pages:
  ```typescript
  test('home page visual', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveScreenshot('home.png', { maxDiffPixelRatio: 0.01 })
  })
  ```

## Concurrency Tests
```python
@pytest.mark.asyncio
async def test_100_concurrent_chat_sessions():
    tokens = await create_100_test_users()

    async def chat_session(token: str):
        async with WSTestClient(WS_URL, token) as ws:
            await ws.send_chat("apartment in Madrid")
            msgs = await ws.collect_messages("criteria_summary", timeout=60)
            assert len(msgs) > 0

    # Run 100 sessions concurrently
    results = await asyncio.gather(
        *[chat_session(t) for t in tokens],
        return_exceptions=True
    )

    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"Errors: {errors}"
```

## Makefile Targets
```make
test-e2e-api:
  cd tests/e2e/api && pytest -v --junitxml=../../../reports/e2e-api.xml

test-e2e-ws:
  cd tests/e2e/websocket && pytest -v

test-e2e-browser:
  cd frontend && pnpm playwright test

test-e2e: kind-deploy kind-seed
  $(MAKE) test-e2e-api
  $(MAKE) test-e2e-ws
  $(MAKE) test-e2e-browser
```

## CI Workflow
```yaml
# .github/workflows/ci-e2e.yml
name: E2E Tests
on: [pull_request]
jobs:
  e2e:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - uses: actions/checkout@v4
      - uses: helm/kind-action@v1
        with:
          cluster_name: estategap
          config: tests/kind/cluster.yaml
      - run: make kind-build kind-load kind-deploy kind-seed
      - run: make test-e2e SHARD=${{ matrix.shard }}/4
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: e2e-artifacts-${{ matrix.shard }}
          path: |
            reports/
            frontend/test-results/
            /tmp/pod-logs/
```

## Artifact Collection on Failure
- Bash script `tests/e2e/collect-artifacts.sh` that runs in trap on test failure:
  - `kubectl logs` for all pods in estategap-* namespaces
  - `kubectl describe pod` for failed pods
  - PostgreSQL dump
  - NATS stream state
- Playwright auto-captures screenshot, video, trace
```
