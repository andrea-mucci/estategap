"""Playwright fallback for heavily protected pages."""

from __future__ import annotations

from urllib.parse import urlparse

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


def _playwright_proxy(proxy_url: str) -> dict[str, str] | None:
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    proxy: dict[str, str] = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy


async def fetch_with_browser(url: str, proxy_url: str) -> str:
    """Fetch page HTML with a headless Chromium browser."""

    browser = None
    context = None
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                proxy=_playwright_proxy(proxy_url),
            )
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await stealth_async(context)
            except TypeError:
                await stealth_async(page)
            await page.goto(url, wait_until="networkidle")
            return await page.content()
        finally:
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()
