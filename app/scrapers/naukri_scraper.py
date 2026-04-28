from typing import Optional
from urllib.parse import quote_plus

from playwright.async_api import BrowserContext, Page

from app.scrapers.base_scraper import BaseScraper, ScrapedJob, JobSearchQuery, ApplicationData, ApplicationResult
from app.scrapers.browser_manager import browser_manager
from app.scrapers.session_manager import session_manager
from app.scrapers.anti_detection import random_delay, human_type, take_screenshot
from app.utils.logger import get_logger

logger = get_logger(__name__)


class NaukriScraper(BaseScraper):
    platform_name = "naukri"

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
            await page.goto("https://www.naukri.com/nlogin/login", wait_until="networkidle")
            await random_delay(1, 2)

            await human_type(page, "input[placeholder*='Email'], input[name='usernameField']", username)
            await random_delay(0.5, 1)
            await human_type(page, "input[placeholder*='password'], input[type='password']", password)
            await random_delay(0.5, 1)

            await page.click("button[type='submit'], .loginButton")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await random_delay(2, 4)

            if "naukri.com" in page.url and "login" not in page.url:
                cookies = await self._context.cookies()
                session_manager.save_cookies(self.platform_name, self.user_id, cookies)
                logger.info("Naukri login successful")
                return True

            otp_field = await page.query_selector("input[placeholder*='OTP'], input[name='otp']")
            if otp_field:
                await take_screenshot(page, f"naukri_otp_{self.user_id}")
                logger.warning("Naukri requires OTP verification")
                return False

            await take_screenshot(page, f"naukri_login_fail_{self.user_id}")
            return False

        except Exception as e:
            logger.error(f"Naukri login error: {e}")
            return False

    async def search_jobs(self, query: JobSearchQuery) -> list[ScrapedJob]:
        page = await self._get_page()
        jobs: list[ScrapedJob] = []

        try:
            keywords = query.keywords.replace(" ", "-").lower()
            location = query.location.replace(" ", "-").lower() if query.location else ""

            if location:
                url = f"https://www.naukri.com/{keywords}-jobs-in-{location}?k={quote_plus(query.keywords)}&l={quote_plus(query.location or '')}&experience=&nignbevent_src=jobsearchDeskGNB"
            else:
                url = f"https://www.naukri.com/{keywords}-jobs?k={quote_plus(query.keywords)}&nignbevent_src=jobsearchDeskGNB"

            await page.goto(url, wait_until="networkidle")
            await random_delay(2, 4)

            job_cards = await page.query_selector_all(".srp-jobtuple-wrapper, article.jobTuple")
            logger.info(f"Naukri: found {len(job_cards)} job cards")

            for card in job_cards[:query.max_results]:
                try:
                    title_el = await card.query_selector("a.title, .row1 a.title")
                    company_el = await card.query_selector("a.comp-name, .row2 .comp-dtls-wrap a")
                    location_el = await card.query_selector(".loc-wrap .locWdth, .row2 .loc-wrap span")
                    exp_el = await card.query_selector(".exp-wrap .expwdth, .row2 .exp-wrap span")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location_text = await location_el.inner_text() if location_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""

                    if not title:
                        continue

                    external_id = ""
                    if href:
                        parts = href.rstrip("/").split("/")
                        for part in reversed(parts):
                            if part and part[0].isdigit():
                                external_id = part
                                break

                    experience = await exp_el.inner_text() if exp_el else ""
                    exp_level = None
                    if experience:
                        try:
                            years = int(experience.split("-")[0].strip().split()[0])
                            if years <= 2:
                                exp_level = "entry"
                            elif years <= 5:
                                exp_level = "mid"
                            else:
                                exp_level = "senior"
                        except (ValueError, IndexError):
                            pass

                    jobs.append(ScrapedJob(
                        external_id=external_id,
                        url=href or "",
                        title=title.strip(),
                        company=company.strip(),
                        location=location_text.strip(),
                        experience_level=exp_level,
                    ))
                    await random_delay(0.2, 0.5)

                except Exception as e:
                    logger.warning(f"Error parsing Naukri job card: {e}")
                    continue

        except Exception as e:
            logger.error(f"Naukri search error: {e}")
            await take_screenshot(page, f"naukri_search_error_{self.user_id}")

        logger.info(f"Naukri: scraped {len(jobs)} jobs")
        return jobs

    async def get_job_details(self, job_url: str) -> Optional[ScrapedJob]:
        page = await self._get_page()
        try:
            await page.goto(job_url, wait_until="networkidle")
            await random_delay(2, 3)

            title_el = await page.query_selector("h1.styles_jd-header-title__rZwM1, .jd-header-title")
            company_el = await page.query_selector("a.styles_jd-header-comp-name__MvqAI, .jd-header-comp-name")
            location_el = await page.query_selector(".styles_jhc__loc__mSg10, .loc")
            desc_el = await page.query_selector(".styles_JDC__dang-inner-html__h0K4t, .job-desc")

            title = await title_el.inner_text() if title_el else ""
            company = await company_el.inner_text() if company_el else ""
            location_text = await location_el.inner_text() if location_el else ""
            description = await desc_el.inner_text() if desc_el else ""

            external_id = ""
            parts = job_url.rstrip("/").split("/")
            for part in reversed(parts):
                if part and part[0].isdigit():
                    external_id = part
                    break

            return ScrapedJob(
                external_id=external_id,
                url=job_url,
                title=title.strip(),
                company=company.strip(),
                location=location_text.strip(),
                description=description.strip(),
            )

        except Exception as e:
            logger.error(f"Naukri job detail error: {e}")
            return None

    async def apply_to_job(self, job_url: str, data: ApplicationData) -> ApplicationResult:
        page = await self._get_page()
        try:
            await page.goto(job_url, wait_until="networkidle")
            await random_delay(2, 3)

            apply_btn = await page.query_selector("button#apply-button, .apply-button-container button, button.styles_jhc__apply-button__jnvIN")
            if not apply_btn:
                return ApplicationResult(success=False, message="No Apply button found on Naukri")

            await apply_btn.click()
            await random_delay(3, 5)

            success_el = await page.query_selector(".apply-message, .chatbot_DrawerContentWrapper, .styles_jhc__applied__kUmR_")
            if success_el:
                screenshot = await take_screenshot(page, f"naukri_applied_{self.user_id}")
                return ApplicationResult(success=True, message="Application submitted", screenshot_path=screenshot)

            screenshot = await take_screenshot(page, f"naukri_apply_result_{self.user_id}")
            return ApplicationResult(success=False, message="Application status unclear", screenshot_path=screenshot)

        except Exception as e:
            logger.error(f"Naukri apply error: {e}")
            screenshot = await take_screenshot(page, f"naukri_apply_error_{self.user_id}")
            return ApplicationResult(success=False, message=str(e), screenshot_path=screenshot)

    async def check_session(self) -> bool:
        page = await self._get_page()
        try:
            await page.goto("https://www.naukri.com/mnjuser/profile", wait_until="networkidle", timeout=15000)
            return "login" not in page.url
        except Exception:
            return False

    async def close(self):
        if self._page and not self._page.is_closed():
            await self._page.close()
        if self._context:
            await self._context.close()
