from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import AsyncAPIClient, AuthTokens


ROOT = Path(__file__).resolve().parents[3]
USERS_FIXTURE = ROOT / "tests" / "fixtures" / "users.json"


@dataclass(slots=True)
class TestUser:
    tier: str
    email: str
    password: str
    allowed_countries: list[str]
    access_token: str | None = None
    refresh_token: str | None = None

    @property
    def tokens(self) -> AuthTokens:
        assert self.access_token, f"user {self.email} has no access token"
        assert self.refresh_token, f"user {self.email} has no refresh token"
        return AuthTokens(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=0,
        )


@dataclass(slots=True)
class SeededIDs:
    listing_ids_by_country: dict[str, list[str]]
    zone_ids_by_country: dict[str, list[str]]
    portal_ids: list[str]
    country_codes: list[str]


def load_test_users(default_password: str = "secret") -> dict[str, TestUser]:
    raw_users = json.loads(USERS_FIXTURE.read_text(encoding="utf-8"))
    users = {
        str(item["subscription_tier"]).lower(): TestUser(
            tier=str(item["subscription_tier"]).lower(),
            email=str(item["email"]),
            password=default_password,
            allowed_countries=[str(code) for code in item.get("allowed_countries", [])],
        )
        for item in raw_users
    }
    users["admin"] = TestUser(
        tier="admin",
        email="admin@estategap.com",
        password="secret12345",
        allowed_countries=["ES", "IT", "FR", "PT", "GB"],
    )
    return users


async def login_user(
    client: AsyncAPIClient,
    *,
    email: str,
    password: str,
) -> AuthTokens:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    payload = response.json()
    return AuthTokens(
        access_token=str(payload["access_token"]),
        refresh_token=str(payload["refresh_token"]),
        expires_in=int(payload.get("expires_in", 0)),
    )


async def ensure_admin_user(client: AsyncAPIClient, admin: TestUser) -> None:
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    if login_response.status_code == 200:
        payload = login_response.json()
        admin.access_token = str(payload["access_token"])
        admin.refresh_token = str(payload["refresh_token"])
        return

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": admin.email,
            "password": admin.password,
            "display_name": "EstateGap Admin",
        },
    )
    if register_response.status_code not in (201, 409):
        register_response.raise_for_status()

    tokens = await login_user(client, email=admin.email, password=admin.password)
    admin.access_token = tokens.access_token
    admin.refresh_token = tokens.refresh_token


async def resolve_listing_ids(client: AsyncAPIClient) -> SeededIDs:
    countries_response = await client.get("/api/v1/countries")
    countries_response.raise_for_status()
    countries_payload = countries_response.json()
    country_codes = [str(item["code"]) for item in countries_payload]

    portals_response = await client.get("/api/v1/portals")
    portals_response.raise_for_status()
    portals_payload = portals_response.json()
    portal_ids = [str(item["id"]) for item in portals_payload]

    listing_ids_by_country: dict[str, list[str]] = {}
    zone_ids_by_country: dict[str, list[str]] = {}

    for country in country_codes:
        listings_response = await client.get(
            "/api/v1/listings",
            params={"country": country, "limit": 10},
        )
        listings_response.raise_for_status()
        listings_payload = listings_response.json()
        listing_ids_by_country[country] = [
            str(item["id"]) for item in listings_payload.get("data", [])
        ]

        zones_response = await client.get(
            "/api/v1/zones",
            params={"country": country, "limit": 10},
        )
        zones_response.raise_for_status()
        zones_payload = zones_response.json()
        zone_ids_by_country[country] = [
            str(item["id"]) for item in zones_payload.get("data", [])
        ]

    return SeededIDs(
        listing_ids_by_country=listing_ids_by_country,
        zone_ids_by_country=zone_ids_by_country,
        portal_ids=portal_ids,
        country_codes=country_codes,
    )


async def resolve_zone_ids(client: AsyncAPIClient) -> dict[str, list[str]]:
    return (await resolve_listing_ids(client)).zone_ids_by_country


def build_unique_email(test_run_id: str, label: str) -> str:
    safe_label = "".join(char for char in label.lower() if char.isalnum())[:16]
    return f"{safe_label}-{test_run_id}@example.test"


def prefixed_name(test_run_id: str, label: str) -> str:
    return f"{test_run_id}-{label}"


def require_items(items: list[Any], label: str) -> list[Any]:
    assert items, f"expected at least one {label}"
    return items
