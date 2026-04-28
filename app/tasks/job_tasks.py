import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.job import Job, JobSkill
from app.models.job_platform import JobPlatform, PlatformCredential
from app.models.skill import Skill
from app.scrapers.base_scraper import JobSearchQuery
from app.scrapers.factory import get_scraper
from app.services.encryption_service import encryption_service
from app.services.job_matcher import quick_skill_overlap, deep_match
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _search_jobs_on_platform(
    user_id: str,
    platform_name: str,
    keywords: str,
    location: str | None,
    max_results: int,
) -> list[str]:
    """Search and store jobs from a single platform. Returns list of stored job IDs."""
    async with AsyncSessionLocal() as db:
        platform_result = await db.execute(
            select(JobPlatform).where(JobPlatform.name == platform_name)
        )
        platform = platform_result.scalar_one_or_none()
        if not platform:
            logger.error(f"Platform '{platform_name}' not found in database")
            return []

        cred_result = await db.execute(
            select(PlatformCredential).where(
                PlatformCredential.user_id == uuid.UUID(user_id),
                PlatformCredential.platform_id == platform.id,
            )
        )
        credential = cred_result.scalar_one_or_none()

        scraper = get_scraper(platform_name, user_id)
        try:
            if credential and credential.encrypted_password:
                password = encryption_service.decrypt(credential.encrypted_password)
                logged_in = await scraper.login(credential.username, password)
                if not logged_in:
                    logger.warning(f"Login failed for {platform_name}, searching without auth")

            query = JobSearchQuery(
                keywords=keywords,
                location=location,
                max_results=max_results,
            )
            scraped_jobs = await scraper.search_jobs(query)
            logger.info(f"Scraped {len(scraped_jobs)} jobs from {platform_name}")

            stored_ids = []
            for sj in scraped_jobs:
                existing = await db.execute(
                    select(Job).where(
                        Job.platform_id == platform.id,
                        Job.external_id == sj.external_id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                if sj.description and len(sj.description) < 50:
                    detail = await scraper.get_job_details(sj.url)
                    if detail:
                        sj.description = detail.description
                        sj.requirements = detail.requirements

                job = Job(
                    platform_id=platform.id,
                    external_id=sj.external_id,
                    url=sj.url,
                    title=sj.title,
                    company=sj.company,
                    location=sj.location,
                    salary_min=sj.salary_min,
                    salary_max=sj.salary_max,
                    salary_currency=sj.salary_currency,
                    job_type=sj.job_type,
                    experience_level=sj.experience_level,
                    description=sj.description or "No description available",
                    requirements=sj.requirements,
                    remote_type=sj.remote_type,
                )
                db.add(job)
                await db.flush()
                stored_ids.append(str(job.id))

            await db.commit()
            logger.info(f"Stored {len(stored_ids)} new jobs from {platform_name}")
            return stored_ids

        finally:
            await scraper.close()


async def _match_jobs_for_user(user_id: str, job_ids: list[str]):
    """Score each job against the user's skills using quick filter + LLM deep match."""
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = user_result.scalar_one_or_none()
        if not user:
            return

        skills_result = await db.execute(
            select(Skill).where(Skill.user_id == user.id)
        )
        user_skills = [s.name for s in skills_result.scalars().all()]
        if not user_skills:
            logger.warning(f"User {user_id} has no skills, skipping matching")
            return

        for job_id in job_ids:
            job_result = await db.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
            job = job_result.scalar_one_or_none()
            if not job:
                continue

            overlap = quick_skill_overlap(user_skills, job.description)
            if overlap < 0.1:
                logger.debug(f"Job {job.title} at {job.company}: overlap {overlap:.2f} < threshold, skipping deep match")
                continue

            try:
                match_result = await deep_match(
                    user_skills=user_skills,
                    experience_years=user.years_experience,
                    preferred_roles=user.preferred_roles or [],
                    preferred_locations=user.preferred_locations or [],
                    job_title=job.title,
                    job_company=job.company or "",
                    job_location=job.location or "",
                    job_description=job.description,
                )

                job.parsed_skills = {
                    "required": match_result.get("required_skills", []),
                    "matching": match_result.get("matching_skills", []),
                    "missing": match_result.get("missing_skills", []),
                }

                for skill_name in match_result.get("required_skills", []):
                    existing = await db.execute(
                        select(JobSkill).where(
                            JobSkill.job_id == job.id,
                            JobSkill.skill_name == skill_name,
                        )
                    )
                    if not existing.scalar_one_or_none():
                        is_required = skill_name not in match_result.get("missing_skills", [])
                        db.add(JobSkill(
                            job_id=job.id,
                            skill_name=skill_name,
                            is_required=True,
                            importance=0.8 if is_required else 0.5,
                        ))

                from app.models.job_application import JobApplication
                app_result = await db.execute(
                    select(JobApplication).where(
                        JobApplication.user_id == user.id,
                        JobApplication.job_id == job.id,
                    )
                )
                existing_app = app_result.scalar_one_or_none()
                if existing_app:
                    existing_app.match_score = match_result["overall_score"]
                    existing_app.match_details = match_result

                await db.commit()
                logger.info(f"Job '{job.title}' at {job.company}: score {match_result['overall_score']:.2f}")

            except Exception as e:
                logger.error(f"Deep match failed for job {job_id}: {e}")
                continue


@celery_app.task(name="app.tasks.job_tasks.search_jobs", bind=True, max_retries=1)
def search_jobs(
    self,
    user_id: str,
    keywords: str,
    location: str | None,
    platforms: list[str],
    max_results: int = 25,
):
    logger.info(f"Task: searching jobs for user {user_id} on {platforms}")
    all_job_ids = []

    for platform_name in platforms:
        try:
            job_ids = _run_async(
                _search_jobs_on_platform(user_id, platform_name, keywords, location, max_results)
            )
            all_job_ids.extend(job_ids)
        except Exception as e:
            logger.error(f"Search failed on {platform_name}: {e}")

    if all_job_ids:
        match_jobs.delay(user_id, all_job_ids)

    return {"jobs_found": len(all_job_ids), "platforms": platforms}


@celery_app.task(name="app.tasks.job_tasks.match_jobs", bind=True, max_retries=1)
def match_jobs(self, user_id: str, job_ids: list[str]):
    logger.info(f"Task: matching {len(job_ids)} jobs for user {user_id}")
    try:
        _run_async(_match_jobs_for_user(user_id, job_ids))
    except Exception as e:
        logger.error(f"Matching task failed: {e}")
        self.retry(exc=e, countdown=60)
