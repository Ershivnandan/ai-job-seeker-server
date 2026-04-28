from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScrapedJob:
    external_id: str
    url: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    description: str = ""
    requirements: Optional[str] = None
    remote_type: Optional[str] = None
    posted_at: Optional[str] = None


@dataclass
class JobSearchQuery:
    keywords: str
    location: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    remote_type: Optional[str] = None
    max_results: int = 25


@dataclass
class ApplicationData:
    resume_pdf_path: str
    full_name: str
    email: str
    phone: Optional[str] = None
    cover_letter: Optional[str] = None
    additional_answers: dict = field(default_factory=dict)


@dataclass
class ApplicationResult:
    success: bool
    message: str
    screenshot_path: Optional[str] = None


class BaseScraper(ABC):
    platform_name: str = ""

    @abstractmethod
    async def login(self, username: str, password: str) -> bool:
        """Authenticate with the platform. Returns True on success."""
        ...

    @abstractmethod
    async def search_jobs(self, query: JobSearchQuery) -> list[ScrapedJob]:
        """Search for jobs matching the query."""
        ...

    @abstractmethod
    async def get_job_details(self, job_url: str) -> Optional[ScrapedJob]:
        """Get full details for a specific job listing."""
        ...

    @abstractmethod
    async def apply_to_job(self, job_url: str, data: ApplicationData) -> ApplicationResult:
        """Submit an application to a job. Returns result with success status."""
        ...

    @abstractmethod
    async def check_session(self) -> bool:
        """Check if the current session/cookies are still valid."""
        ...

    @abstractmethod
    async def close(self):
        """Clean up resources (browser, connections)."""
        ...
