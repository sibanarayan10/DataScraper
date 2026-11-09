"""Hybrid fetching engine combining fast HTTP requests (httpx) and headless browser (Playwright)."""

import asyncio
import time
from typing import Optional
import httpx
from playwright.async_api import Browser, async_playwright

from config import DEFAULT_USER_AGENT, REQUEST_TIMEOUT_SECONDS
from models import FetchResponse


class HybridFetcher:
    """Manages web page fetching via both HTTP requests and Playwright."""

    def __init__(self, use_playwright: bool = False, headless: bool = True):
        self.use_playwright = use_playwright
        self.headless = headless
        self._pw_instance = None
        self._browser: Optional[Browser] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        # Setup httpx client
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            verify=False,  # Avoid SSL failure halts during exploratory crawling
        )

        # Setup Playwright if requested
        if self.use_playwright:
            self._pw_instance = await async_playwright().start()
            self._browser = await self._pw_instance.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
        if self._browser:
            await self._browser.close()
        if self._pw_instance:
            await self._pw_instance.stop()

    async def fetch_http(self, url: str) -> FetchResponse:
        """Fetch page using httpx async client."""
        start = time.perf_counter()
        try:
            assert self._client is not None
            resp = await self._client.get(url)
            elapsed = time.perf_counter() - start
            return FetchResponse(
                url=str(resp.url),
                status_code=resp.status_code,
                html=resp.text,
                elapsed_seconds=round(elapsed, 3),
                fetched_via="httpx",
            )
        except Exception as e:
            elapsed = time.perf_counter() - start
            return FetchResponse(
                url=url,
                status_code=0,
                html="",
                elapsed_seconds=round(elapsed, 3),
                error=str(e),
                fetched_via="httpx",
            )

    async def fetch_browser(self, url: str, wait_selector: Optional[str] = None) -> FetchResponse:
        """Fetch page using headless Chromium to execute client-side JavaScript."""
        if not self._browser:
            return await self.fetch_http(url)

        start = time.perf_counter()
        page = None
        try:
            context = await self._browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            # Navigate and wait until network is mostly idle
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=REQUEST_TIMEOUT_SECONDS * 1000,
            )

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=5000)
                except Exception:
                    pass

            # Brief pause for client-side hydration
            await asyncio.sleep(1.0)

            content = await page.content()
            status = response.status if response else 200
            elapsed = time.perf_counter() - start

            await context.close()
            return FetchResponse(
                url=page.url,
                status_code=status,
                html=content,
                elapsed_seconds=round(elapsed, 3),
                fetched_via="playwright",
            )
        except Exception as e:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            elapsed = time.perf_counter() - start
            return FetchResponse(
                url=url,
                status_code=0,
                html="",
                elapsed_seconds=round(elapsed, 3),
                error=str(e),
                fetched_via="playwright",
            )

    async def fetch(self, url: str, force_browser: bool = False) -> FetchResponse:
        """Fetch entry point: uses browser if forced or configured, else uses fast HTTP."""
        if force_browser or self.use_playwright:
            return await self.fetch_browser(url)
        return await self.fetch_http(url)
