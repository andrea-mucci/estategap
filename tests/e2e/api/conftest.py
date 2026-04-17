from __future__ import annotations

import os
import uuid
from typing import AsyncIterator, Callable

import pytest
import pytest_asyncio

from tests.e2e.helpers.client import AsyncAPIClient
from tests.e2e.helpers.fixtures import (
    SeededIDs,
    TestUser,
    ensure_admin_user,
    load_test_users,
    login_user,
    resolve_listing_ids,
)


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://localhost:8080").rstrip("/")


@pytest.fixture(scope="session")
def test_run_id() -> str:
    return os.getenv("TEST_RUN_ID", f"test-run-{uuid.uuid4().hex[:10]}")


@pytest_asyncio.fixture(scope="session")
async def test_users(api_base_url: str) -> dict[str, TestUser]:
    seed_client = AsyncAPIClient(base_url=api_base_url, tier="seed")
    users = load_test_users()
    try:
        for tier, user in users.items():
            if tier == "admin":
                await ensure_admin_user(seed_client, user)
                continue
            tokens = await login_user(seed_client, email=user.email, password=user.password)
            user.access_token = tokens.access_token
            user.refresh_token = tokens.refresh_token
    finally:
        await seed_client.close()
    return users


@pytest_asyncio.fixture(scope="session")
async def seeded_ids(api_base_url: str, test_users: dict[str, TestUser]) -> SeededIDs:
    user = test_users["global"]
    client = AsyncAPIClient(
        base_url=api_base_url,
        tier=user.tier,
        access_token=user.access_token,
    )
    try:
        return await resolve_listing_ids(client)
    finally:
        await client.close()


@pytest_asyncio.fixture
async def authed_client(
    api_base_url: str,
    test_users: dict[str, TestUser],
) -> AsyncIterator[Callable[[str], AsyncAPIClient]]:
    clients: list[AsyncAPIClient] = []

    def factory(tier: str) -> AsyncAPIClient:
        user = test_users[tier]
        client = AsyncAPIClient(
            base_url=api_base_url,
            tier=tier,
            access_token=user.access_token,
        )
        clients.append(client)
        return client

    try:
        yield factory
    finally:
        for client in clients:
            await client.close()
