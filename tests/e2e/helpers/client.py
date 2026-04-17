from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    expires_in: int


class AsyncAPIClient:
    """Small convenience wrapper around httpx.AsyncClient for authenticated E2E calls."""

    def __init__(
        self,
        *,
        base_url: str,
        tier: str,
        access_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.tier = tier
        self._access_token = access_token
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            follow_redirects=False,
            timeout=timeout,
        )

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def close(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}))
        return await self._client.request(method, path, headers=headers, **kwargs)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, json: Any | None = None, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, json=json, **kwargs)

    async def put(self, path: str, json: Any | None = None, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, json=json, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

    async def patch(self, path: str, json: Any | None = None, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", path, json=json, **kwargs)

    def with_token(self, access_token: str) -> "AsyncAPIClient":
        return AsyncAPIClient(
            base_url=self.base_url,
            tier=self.tier,
            access_token=access_token,
        )
