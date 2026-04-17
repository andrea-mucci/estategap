from __future__ import annotations

from typing import Any

import httpx


def _json_body(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    assert isinstance(payload, dict), f"expected object response, got {payload!r}"
    return payload


def assert_error_shape(
    response: httpx.Response,
    status_code: int,
    error_code: str | None = None,
    *,
    message_contains: str | None = None,
) -> dict[str, Any]:
    payload = _json_body(response)
    assert response.status_code == status_code, payload
    assert isinstance(payload.get("error"), str) and payload["error"], payload
    if error_code is not None:
        assert payload.get("code") == error_code, payload
    if "details" in payload and payload["details"] is not None:
        assert isinstance(payload["details"], (dict, list)), payload
    if "request_id" in payload and payload["request_id"] is not None:
        assert isinstance(payload["request_id"], str), payload
    if message_contains:
        assert message_contains.lower() in payload["error"].lower(), payload
    return payload


def assert_pagination(response: httpx.Response) -> dict[str, Any]:
    payload = _json_body(response)
    assert "data" in payload, payload
    assert isinstance(payload["data"], list), payload
    assert isinstance(payload.get("pagination"), dict), payload
    assert isinstance(payload.get("meta"), dict), payload
    assert "total_count" in payload["meta"], payload
    return payload


def assert_rate_limit_headers(response: httpx.Response) -> int:
    header = response.headers.get("Retry-After")
    assert header is not None, response.headers
    retry_after = int(header)
    assert retry_after > 0, response.headers
    return retry_after


def assert_envelope_type(message: dict[str, Any], expected_type: str) -> dict[str, Any]:
    assert message.get("type") == expected_type, message
    payload = message.get("payload")
    assert isinstance(payload, dict), message
    return payload
