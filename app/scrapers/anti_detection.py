import random
from playwright.async_api import Page

from app.utils.logger import get_logger

logger = get_logger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def get_random_viewport() -> dict:
    return random.choice(VIEWPORTS)


async def apply_stealth(page: Page):
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);

        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        window.chrome = { runtime: {} };
    """)


async def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    delay = random.uniform(min_seconds, max_seconds)
    import asyncio
    await asyncio.sleep(delay)


async def human_type(page: Page, selector: str, text: str, delay_range: tuple = (50, 150)):
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char, delay=random.randint(*delay_range))


async def take_screenshot(page: Page, name: str) -> str:
    import os
    from app.config import settings
    path = os.path.join(settings.STORAGE_PATH, "screenshots", f"{name}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    await page.screenshot(path=path, full_page=False)
    logger.info(f"Screenshot saved: {path}")
    return path
