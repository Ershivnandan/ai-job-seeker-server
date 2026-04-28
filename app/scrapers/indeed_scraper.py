from typing import Optional
from urllib.parse import quote_plus

from playwright.async_api import BrowserContext, Page

from app.scrapers.base_scraper import BaseScraper, ScrapedJob, JobSearchQuery, ApplicationData, ApplicationResult
from app.scrapers.browser_manager import browser_manager
from app.scrapers.session_manager import session_manager
from app.scrapers.anti_detection import random_delay, take_screenshot
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IndeedScraper(BaseScraper):
    platform_name = "indeed"

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
            await page.goto("https://secure.indeed.com/auth", wait_until="networkidle")
            await random_delay(1, 2)

            email_input = await page.query_selector("input[name='__email'], input[type='email']")
            if email_input:
                await email_input.fill(username)
                await random_delay(0.5, 1)

                submit = await page.query_selector("button[type='submit']")
                if submit:
                    await submit.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await random_delay(1, 2)

            pass_input = await page.query_selector("input[name='__password'], input[type='password']")
            if pass_input:
                await pass_input.fill(password)
                await random_delay(0.5, 1)

                submit = await page.query_selector("button[type='submit']")
                if submit:
                    await submit.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await random_delay(2, 3)

            if "indeed.com" in page.url and "auth" not in page.url:
                cookies = await self._context.cookies()
                session_manager.save_cookies(self.platform_name, self.user_id, cookies)
                logger.info("Indeed login successful")
                return True

            await take_screenshot(page, f"indeed_login_fail_{self.user_id}")
            return False

        except Exception as e:
            logger.error(f"Indeed login error: {e}")
            return False

    async def search_jobs(self, query: JobSearchQuery) -> list[ScrapedJob]:
        page = await self._get_page()
        jobs: list[ScrapedJob] = []

        try:
            keywords = quote_plus(query.keywords)
            location = quote_plus(query.location or "")
            url = f"https://www.indeed.com/jobs?q={keywords}&l={location}&fromage=7&sort=date"

            if query.remote_type == "remote":
                url += "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11"

            await page.goto(url, wait_until="networkidle")
            await random_delay(2, 4)

            job_cards = await page.query_selector_all(".job_seen_beacon, .jobsearch-ResultsList .result")
            logger.info(f"Indeed: found {len(job_cards)} job cards")

            for card in job_cards[:query.max_results]:
                try:
                    title_el = await card.query_selector("h2.jobTitle a, .jobTitle span")
                    company_el = await card.query_selector("[data-testid='company-name'], .companyName")
                    location_el = await card.query_selector("[data-testid='text-location'], .companyLocation")
                    link_el = await card.query_selector("h2.jobTitle a, a.jcs-JobTitle")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location_text = await location_el.inner_text() if location_el else ""
                    href = await link_el.get_attribute("href") if link_el else ""

                    if not title:
                        continue

                    job_url = href if href.startswith("http") else f"https://www.indeed.com{href}"

                    external_id = ""
                    if "jk=" in job_url:
                        external_id = job_url.split("jk=")[1].split("&")[0]
                    elif "vjk=" in job_url:
                        external_id = job_url.split("vjk=")[1].split("&")[0]

                    jobs.append(ScrapedJob(
                        external_id=external_id,
                        url=job_url,
                        title=title.strip(),
                        company=company.strip(),
                        location=location_text.strip(),
                    ))
                    await random_delay(0.2, 0.5)

                except Exception as e:
                    logger.warning(f"Error parsing Indeed job card: {e}")
                    continue

        except Exception as e:
            logger.error(f"Indeed search error: {e}")
            await take_screenshot(page, f"indeed_search_error_{self.user_id}")

        logger.info(f"Indeed: scraped {len(jobs)} jobs")
        return jobs

    async def get_job_details(self, job_url: str) -> Optional[ScrapedJob]:
        page = await self._get_page()
        try:
            await page.goto(job_url, wait_until="networkidle")
            await random_delay(2, 3)

            title_el = await page.query_selector("h1.jobsearch-JobInfoHeader-title, .jobsearch-JobInfoHeader-title")
            company_el = await page.query_selector("[data-testid='inlineHeader-companyName'], .jobsearch-InlineCompanyRating-companyHeader")
            location_el = await page.query_selector("[data-testid='inlineHeader-companyLocation'], .jobsearch-JobInfoHeader-subtitle > div:nth-child(2)")
            desc_el = await page.query_selector("#jobDescriptionText, .jobsearch-jobDescriptionText")

            title = await title_el.inner_text() if title_el else ""
            company = await company_el.inner_text() if company_el else ""
            location_text = await location_el.inner_text() if location_el else ""
            description = await desc_el.inner_text() if desc_el else ""

            external_id = ""
            if "jk=" in job_url:
                external_id = job_url.split("jk=")[1].split("&")[0]

            return ScrapedJob(
                external_id=external_id,
                url=job_url,
                title=title.strip(),
                company=company.strip(),
                location=location_text.strip(),
                description=description.strip(),
            )

        except Exception as e:
            logger.error(f"Indeed job detail error: {e}")
            return None

    async def apply_to_job(self, job_url: str, data: ApplicationData) -> ApplicationResult:
        page = await self._get_page()
        try:
            await page.goto(job_url, wait_until="networkidle")
            await random_delay(2, 3)

            apply_btn = await page.query_selector("button[id*='indeedApply'], .jobsearch-IndeedApplyButton-newDesign")
            if not apply_btn:
                return ApplicationResult(success=False, message="No Indeed Apply button found")

            await apply_btn.click()
            await random_delay(3, 5)

            pages = self._context.pages
            apply_page = pages[-1] if len(pages) > 1 else page

            for step in range(10):
                continue_btn = await apply_page.query_selector("button[id='ia-continue'], button.ia-continueButton")
                submit_btn = await apply_page.query_selector("button[id*='submit'], button.ia-submitButton")

                if submit_btn:
                    await submit_btn.click()
                    await random_delay(2, 3)
                    screenshot = await take_screenshot(apply_page, f"indeed_applied_{self.user_id}")
                    return ApplicationResult(success=True, message="Application submitted", screenshot_path=screenshot)

                if continue_btn:
                    await continue_btn.click()
                    await random_delay(1, 2)
                    continue

                break

            screenshot = await take_screenshot(apply_page, f"indeed_apply_stuck_{self.user_id}")
            return ApplicationResult(success=False, message="Got stuck in application flow", screenshot_path=screenshot)

        except Exception as e:
            logger.error(f"Indeed apply error: {e}")
            screenshot = await take_screenshot(page, f"indeed_apply_error_{self.user_id}")
            return ApplicationResult(success=False, message=str(e), screenshot_path=screenshot)

    async def check_session(self) -> bool:
        page = await self._get_page()
        try:
            await page.goto("https://www.indeed.com/", wait_until="networkidle", timeout=15000)
            nav_account = await page.query_selector("[data-gnav-element-name='Account']")
            return nav_account is not None
        except Exception:
            return False

    async def close(self):
        if self._page and not self._page.is_closed():
            await self._page.close()
        if self._context:
            await self._context.close()
