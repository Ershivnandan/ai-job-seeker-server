from app.scrapers.base_scraper import BaseScraper
from app.scrapers.linkedin_scraper import LinkedInScraper
from app.scrapers.indeed_scraper import IndeedScraper
from app.scrapers.naukri_scraper import NaukriScraper


SCRAPER_MAP = {
    "linkedin": LinkedInScraper,
    "indeed": IndeedScraper,
    "naukri": NaukriScraper,
}


def get_scraper(platform_name: str, user_id: str) -> BaseScraper:
    scraper_cls = SCRAPER_MAP.get(platform_name.lower())
    if not scraper_cls:
        raise ValueError(f"Unknown platform: {platform_name}. Supported: {list(SCRAPER_MAP.keys())}")
    return scraper_cls(user_id=user_id)
