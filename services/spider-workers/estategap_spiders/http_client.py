"""Async HTTP helpers with retry and anti-bot heuristics."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar

import httpx
import structlog

from .config import Config


LOGGER = structlog.get_logger(__name__)
P = ParamSpec("P")
R = TypeVar("R")


class PermanentFailureError(RuntimeError):
    """Raised when a retried operation cannot recover."""


class ParseError(RuntimeError):
    """Raised when portal content cannot be parsed."""


def retry(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    backoff: float = 2.0,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Retry async operations with exponential backoff."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            delay = base_delay
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except PermanentFailureError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt >= max_attempts:
                        break
                    LOGGER.warning(
                        "retrying_request",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff
            message = str(last_error) if last_error is not None else "operation failed"
            raise PermanentFailureError(message) from last_error

        return wrapper

    return decorator


class HttpClient:
    """Randomised, rate-limited HTTP client for scraping."""

    USER_AGENTS: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Redmi Note 12) AppleWebKit/537.36 Chrome/123.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36 Edg/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 Chrome/123.0 Safari/537.36 Edg/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/537.36 Chrome/119.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/119.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; OnePlus 11) AppleWebKit/537.36 Chrome/119.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 Chrome/118.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; Pixel 6 Pro) AppleWebKit/537.36 Chrome/118.0 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 16_7 like Mac OS X) AppleWebKit/605.1.15 Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 Chrome/118.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) AppleWebKit/537.36 Chrome/118.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12.7; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Windows NT 10.0; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12.6; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Linux; Android 14; Pixel Fold) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; SM-F956B) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; CPH2581) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Nothing A065) AppleWebKit/537.36 Chrome/123.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Mi 13) AppleWebKit/537.36 Chrome/123.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; Nokia X30) AppleWebKit/537.36 Chrome/122.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36 OPR/109.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 Chrome/124.0 Safari/537.36 OPR/109.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36 OPR/109.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36 Vivaldi/6.7",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 Chrome/123.0 Safari/537.36 Vivaldi/6.7",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36 Vivaldi/6.7",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36 Brave/124",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 Chrome/124.0 Safari/537.36 Brave/124",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36 Brave/124",
    ]

    def __init__(self, proxy_url: str, config: Config) -> None:
        self._config = config
        self._rng = random.Random(config.user_agent_seed)
        self._semaphore = asyncio.Semaphore(config.max_concurrent_per_portal)
        self._client = httpx.AsyncClient(
            proxy=proxy_url or None,
            timeout=config.request_timeout_seconds,
            follow_redirects=True,
        )

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        async with self._semaphore:
            delay = self._rng.uniform(self._config.request_min_delay, self._config.request_max_delay)
            await asyncio.sleep(delay)
            return await self._perform_request(method, url, **kwargs)

    @retry()
    async def _perform_request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("User-Agent", self._rng.choice(self.USER_AGENTS))
        started = perf_counter()
        response = await self._client.request(method, url, headers=headers, **kwargs)
        elapsed_ms = int((perf_counter() - started) * 1000)
        LOGGER.debug(
            "http_request_completed",
            method=method,
            url=url,
            status_code=response.status_code,
            latency_ms=elapsed_ms,
        )
        if response.status_code >= 500:
            raise httpx.HTTPStatusError(
                f"server error {response.status_code}",
                request=response.request,
                response=response,
            )
        return response

    def is_blocked(self, response: httpx.Response) -> bool:
        body = response.text.lower()
        markers = ("captcha", "robot", "challenge", "access denied", "forbidden")
        return response.status_code in {403, 429} or any(marker in body for marker in markers)

    async def close(self) -> None:
        await self._client.aclose()
