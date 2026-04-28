from typing import Optional
from urllib.parse import quote_plus

from playwright.async_api import BrowserContext, Page

from app.scrapers.base_scraper import BaseScraper, ScrapedJob, JobSearchQuery, ApplicationData, ApplicationResult
from app.scrapers.browser_manager import browser_manager
from app.scrapers.session_manager import session_manager
from app.scrapers.anti_detection import random_delay, human_type, take_screenshot
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LinkedInScraper(BaseScraper):
    platform_name = "linkedin"

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def _get_page(self) -> Page:
        if self._page and not self._page.is_closed():
            return self._page

        cookies_path = session_manager.get_cookies_path(self.platform_name, self.user_id)
        self._context = await browser_manager.new_context(
            cookies_path=cookies_path if session_manager.has_session(self.platform_name, self.user_id) else None,
        )
        self._page = await browser_manager.new_page(self._context)
        return self._page

    async def login(self, username: str, password: str) -> bool:
        page = await self._get_page()
        try:
            await page.goto("https://www.linkedin.com/login", wait_until="networkidle")
            await random_delay(1, 2)

            await human_type(page, "#username", username)
            await random_delay(0.5, 1)
            await human_type(page, "#password", password)
            await random_delay(0.5, 1)

            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle", timeout=30000)
            await random_delay(2, 4)

            if "/feed" in page.url or "/mynetwork" in page.url:
                cookies = await self._context.cookies()
                session_manager.save_cookies(self.platform_name, self.user_id, cookies)
                logger.info("LinkedIn login successful")
                return True

            if "checkpoint" in page.url or "challenge" in page.url:
                await take_screenshot(page, f"linkedin_2fa_{self.user_id}")
                logger.warning("LinkedIn requires 2FA/verification")
                return False

            await take_screenshot(page, f"linkedin_login_fail_{self.user_id}")
            logger.error(f"LinkedIn login failed, landed on: {page.url}")
            return False

        except Exception as e:
            logger.error(f"LinkedIn login error: {e}")
            await take_screenshot(page, f"linkedin_login_error_{self.user_id}")
            return False

    async def search_jobs(self, query: JobSearchQuery) -> list[ScrapedJob]:
        page = await self._get_page()
        jobs: list[ScrapedJob] = []

        try:
            keywords = quote_plus(query.keywords)
            location = quote_plus(query.location or "")
            url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&f_TPR=r604800"

            if query.remote_type == "remote":
                url += "&f_WT=2"
            elif query.remote_type == "hybrid":
                url += "&f_WT=1"

            await page.goto(url, wait_until="networkidle")
            await random_delay(2, 4)

            for scroll in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await random_delay(1, 2)

            job_cards = await page.query_selector_all(".job-card-container, .jobs-search-results__list-item")
            logger.info(f"LinkedIn: found {len(job_cards)} job cards")

            for card in job_cards[:query.max_results]:
                try:
                    title_el = await card.query_selector(".job-card-list__title, .job-card-container__link")
                    company_el = await card.query_selector(".job-card-container__primary-description, .artdeco-entity-lockup__subtitle")
                    location_el = await card.query_selector(".job-card-container__metadata-wrapper, .artdeco-entity-lockup__caption")
                    link_el = await card.query_selector("a[href*='/jobs/view/']")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location_text = await location_el.inner_text() if location_el else ""
                    href = await link_el.get_attribute("href") if link_el else ""

                    if not title or not href:
                        continue

                    external_id = ""
                    if "/view/" in href:
                        external_id = href.split("/view/")[1].split("/")[0].split("?")[0]

                    job_url = f"https://www.linkedin.com/jobs/view/{external_id}/" if external_id else href

                    jobs.append(ScrapedJob(
                        external_id=external_id,
                        url=job_url,
                        title=title.strip(),
                        company=company.strip(),
                        location=location_text.strip(),
                    ))
                    await random_delay(0.3, 0.8)

                except Exception as e:
                    logger.warning(f"Error parsing LinkedIn job card: {e}")
                    continue

        except Exception as e:
            logger.error(f"LinkedIn search error: {e}")
            await take_screenshot(page, f"linkedin_search_error_{self.user_id}")

        logger.info(f"LinkedIn: scraped {len(jobs)} jobs")
        return jobs

    async def get_job_details(self, job_url: str) -> Optional[ScrapedJob]:
        page = await self._get_page()
        try:
            await page.goto(job_url, wait_until="networkidle")
            await random_delay(2, 3)

            title_el = await page.query_selector(".job-details-jobs-unified-top-card__job-title, h1.t-24")
            company_el = await page.query_selector(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name")
            location_el = await page.query_selector(".job-details-jobs-unified-top-card__primary-description-container, .jobs-unified-top-card__bullet")
            desc_el = await page.query_selector(".jobs-description__content, .jobs-box__html-content")

            title = await title_el.inner_text() if title_el else ""
            company = await company_el.inner_text() if company_el else ""
            location_text = await location_el.inner_text() if location_el else ""
            description = await desc_el.inner_text() if desc_el else ""

            external_id = ""
            if "/view/" in job_url:
                external_id = job_url.split("/view/")[1].split("/")[0].split("?")[0]

            return ScrapedJob(
                external_id=external_id,
                url=job_url,
                title=title.strip(),
                company=company.strip(),
                location=location_text.strip(),
                description=description.strip(),
            )

        except Exception as e:
            logger.error(f"LinkedIn job detail error: {e}")
            await take_screenshot(page, f"linkedin_detail_error_{self.user_id}")
            return None

    async def apply_to_job(self, job_url: str, data: ApplicationData) -> ApplicationResult:
        page = await self._get_page()
        try:
            await page.goto(job_url, wait_until="networkidle")
            await random_delay(2, 3)

            easy_apply_btn = await page.query_selector("button.jobs-apply-button, button[aria-label*='Easy Apply']")
            if not easy_apply_btn:
                return ApplicationResult(success=False, message="No Easy Apply button found")

            await easy_apply_btn.click()
            await random_delay(2, 3)

            for step in range(10):
                submit_btn = await page.query_selector("button[aria-label='Submit application'], button[aria-label='Review']")
                if submit_btn:
                    label = await submit_btn.get_attribute("aria-label") or ""
                    if "Submit" in label:
                        await submit_btn.click()
                        await random_delay(2, 3)
                        screenshot = await take_screenshot(page, f"linkedin_applied_{self.user_id}")
                        return ApplicationResult(success=True, message="Application submitted", screenshot_path=screenshot)
                    else:
                        await submit_btn.click()
                        await random_delay(1, 2)
                        continue

                next_btn = await page.query_selector("button[aria-label='Continue to next step']")
                if next_btn:
                    await next_btn.click()
                    await random_delay(1, 2)
                    continue

                break

            screenshot = await take_screenshot(page, f"linkedin_apply_stuck_{self.user_id}")
            return ApplicationResult(success=False, message="Got stuck in application flow", screenshot_path=screenshot)

        except Exception as e:
            logger.error(f"LinkedIn apply error: {e}")
            screenshot = await take_screenshot(page, f"linkedin_apply_error_{self.user_id}")
            return ApplicationResult(success=False, message=str(e), screenshot_path=screenshot)

    async def check_session(self) -> bool:
        page = await self._get_page()
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="networkidle", timeout=15000)
            return "/feed" in page.url
        except Exception:
            return False

    async def close(self):
        if self._page and not self._page.is_closed():
            await self._page.close()
        if self._context:
            await self._context.close()
