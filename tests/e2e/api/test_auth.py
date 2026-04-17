from __future__ import annotations

import uuid

import pytest

from tests.e2e.helpers.assertions import assert_error_shape
from tests.e2e.helpers.client import AsyncAPIClient
from tests.e2e.helpers.fixtures import build_unique_email


pytestmark = [pytest.mark.api]


async def _register_user(client: AsyncAPIClient, email: str, password: str, name: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": name,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    return payload


@pytest.mark.asyncio
async def test_register_login_refresh_profile_export_logout_and_delete(
    api_base_url: str,
    test_run_id: str,
) -> None:
    client = AsyncAPIClient(base_url=api_base_url, tier="guest")
    email = build_unique_email(test_run_id, "auth")
    password = "secret12345"
    try:
        registered = await _register_user(client, email, password, "Auth E2E User")
        access_token = registered["access_token"]
        refresh_token = registered["refresh_token"]

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200, login_response.text
        login_payload = login_response.json()
        assert login_payload["user"]["email"] == email

        auth_client = AsyncAPIClient(
            base_url=api_base_url,
            tier="user",
            access_token=access_token,
        )
        try:
            me_response = await auth_client.get("/api/v1/auth/me")
            assert me_response.status_code == 200, me_response.text
            assert me_response.json()["email"] == email

            patch_response = await auth_client.patch(
                "/api/v1/auth/me",
                json={"preferred_currency": "USD", "onboarding_completed": True},
            )
            assert patch_response.status_code == 200, patch_response.text
            assert patch_response.json()["preferred_currency"] == "USD"

            export_response = await auth_client.get("/api/v1/me/export")
            assert export_response.status_code == 200, export_response.text
            assert export_response.headers["content-disposition"].startswith("attachment;")

            refresh_response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            assert refresh_response.status_code == 200, refresh_response.text
            refreshed = refresh_response.json()
            assert refreshed["access_token"] != access_token

            logout_response = await auth_client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": refresh_token},
            )
            assert logout_response.status_code == 204, logout_response.text

            revoked_response = await auth_client.get("/api/v1/auth/me")
            assert_error_shape(revoked_response, 401, message_contains="invalid token")

            delete_client = AsyncAPIClient(
                base_url=api_base_url,
                tier="user",
                access_token=refreshed["access_token"],
            )
            try:
                delete_response = await delete_client.delete(
                    "/api/v1/me",
                    json={"confirm": "delete my account"},
                )
                assert delete_response.status_code == 202, delete_response.text
            finally:
                await delete_client.close()
        finally:
            await auth_client.close()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_auth_rejects_duplicates_invalid_payloads_and_missing_tokens(
    api_base_url: str,
    test_run_id: str,
) -> None:
    client = AsyncAPIClient(base_url=api_base_url, tier="guest")
    email = build_unique_email(test_run_id, "dup")
    try:
        await _register_user(client, email, "secret12345", "Duplicate User")

        duplicate_response = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "secret12345"},
        )
        assert_error_shape(duplicate_response, 409, message_contains="email already")

        invalid_email = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "short"},
        )
        assert_error_shape(invalid_email, 422, message_contains="invalid email or password")

        bad_login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrong-password"},
        )
        assert_error_shape(bad_login, 401, message_contains="invalid credentials")

        invalid_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": str(uuid.uuid4())},
        )
        assert_error_shape(invalid_refresh, 401, message_contains="invalid refresh token")

        missing_auth = await client.get("/api/v1/auth/me")
        assert_error_shape(missing_auth, 401, message_contains="missing bearer token")

        invalid_signature = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert_error_shape(invalid_signature, 401, message_contains="invalid token")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_google_oauth_redirect_and_invalid_state(api_base_url: str) -> None:
    client = AsyncAPIClient(base_url=api_base_url, tier="guest")
    try:
        redirect_response = await client.get("/api/v1/auth/google")
        if redirect_response.status_code == 503:
            pytest.skip("OAuth client is not configured in this local environment")
        assert redirect_response.status_code == 302, redirect_response.text
        assert "accounts.google.com" in redirect_response.headers["location"]

        invalid_state_response = await client.get(
            "/api/v1/auth/google/callback",
            params={"code": "fixture-code", "state": "invalid-state"},
        )
        assert_error_shape(invalid_state_response, 400, message_contains="invalid oauth state")
    finally:
        await client.close()
