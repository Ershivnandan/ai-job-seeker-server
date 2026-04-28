import asyncio
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.config import settings
from app.scrapers.anti_detection import apply_stealth, get_random_viewport, get_random_user_agent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        if self._browser and self._browser.is_connected():
            return

        async with self._lock:
            if self._browser and self._browser.is_connected():
                return

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            logger.info("Browser launched")

    async def new_context(
        self,
        cookies_path: Optional[str] = None,
    ) -> BrowserContext:
        await self._ensure_browser()

        viewport = get_random_viewport()
        user_agent = get_random_user_agent()

        context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="Asia/Kolkata",
            proxy={"server": settings.PROXY_URL} if settings.PROXY_URL else None,
        )

        if cookies_path:
            try:
                import json
                with open(cookies_path, "r") as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                logger.info(f"Loaded {len(cookies)} cookies from {cookies_path}")
            except (FileNotFoundError, json.JSONDecodeError):
                logger.warning(f"Could not load cookies from {cookies_path}")

        return context

    async def new_page(self, context: BrowserContext) -> Page:
        page = await context.new_page()
        await apply_stealth(page)
        return page

    async def save_cookies(self, context: BrowserContext, cookies_path: str):
        import json, os
        cookies = await context.cookies()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        with open(cookies_path, "w") as f:
            json.dump(cookies, f)
        logger.info(f"Saved {len(cookies)} cookies to {cookies_path}")

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser closed")


browser_manager = BrowserManager()
