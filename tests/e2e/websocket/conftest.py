from __future__ import annotations

import os
from typing import Callable

import pytest

from tests.e2e.helpers.fixtures import TestUser
from tests.e2e.helpers.ws_client import WSTestClient


pytest_plugins = ["tests.e2e.api.conftest"]


@pytest.fixture(scope="session")
def ws_base_url() -> str:
    return os.getenv("WS_BASE_URL", "ws://localhost:8081").rstrip("/")


@pytest.fixture(scope="session")
def ws_token(test_users: dict[str, TestUser]) -> Callable[[str], str]:
    def getter(tier: str) -> str:
        token = test_users[tier].access_token
        assert token, f"missing token for tier {tier}"
        return token

    return getter


@pytest.fixture
def ws_client(ws_base_url: str, ws_token: Callable[[str], str]) -> Callable[[str], WSTestClient]:
    def factory(tier: str) -> WSTestClient:
        return WSTestClient(f"{ws_base_url.rstrip('/')}/ws/chat?token={ws_token(tier)}")

    return factory
