import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.job import Job
from app.models.job_platform import JobPlatform, PlatformCredential
from app.models.job_application import JobApplication
from app.models.resume_variant import ResumeVariant
from app.models.skill import Skill
from app.scrapers.factory import get_scraper
from app.scrapers.base_scraper import ApplicationData
from app.services.encryption_service import encryption_service
from app.agents.application_agent import prepare_application_data
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def apply_to_single_job(application_id: str) -> dict:
    """Orchestrate the full auto-apply flow for a single application.

    Returns a status dict with success, message, and optional screenshot_path.
    """
    async with AsyncSessionLocal() as db:
        app_result = await db.execute(
            select(JobApplication).where(JobApplication.id == uuid.UUID(application_id))
        )
        application = app_result.scalar_one_or_none()
        if not application:
            return {"success": False, "message": "Application not found"}

        application.status = "applying"
        await db.commit()

        user_result = await db.execute(select(User).where(User.id == application.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return await _fail_application(db, application, "User not found")

        job_result = await db.execute(select(Job).where(Job.id == application.job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            return await _fail_application(db, application, "Job not found")

        platform_result = await db.execute(
            select(JobPlatform).where(JobPlatform.id == job.platform_id)
        )
        platform = platform_result.scalar_one_or_none()
        if not platform:
            return await _fail_application(db, application, "Job platform not found")

        cred_result = await db.execute(
            select(PlatformCredential).where(
                PlatformCredential.user_id == user.id,
                PlatformCredential.platform_id == platform.id,
            )
        )
        credential = cred_result.scalar_one_or_none()

        variant_result = await db.execute(
            select(ResumeVariant).where(
                ResumeVariant.application_id == application.id,
                ResumeVariant.user_id == user.id,
            )
        )
        variant = variant_result.scalar_one_or_none()

        resume_pdf_path = variant.compiled_pdf_path if variant else None

        skills_result = await db.execute(
            select(Skill).where(Skill.user_id == user.id)
        )
        user_skills = [s.name for s in skills_result.scalars().all()]

        match_details = application.match_details or {}
        matching_skills = match_details.get("matching_skills", [])

        user_info = {
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "location": user.location,
            "years_experience": user.years_experience,
            "current_role": (user.preferred_roles or [""])[0] if user.preferred_roles else "",
        }

        app_data = await prepare_application_data(
            user_info=user_info,
            user_skills=user_skills,
            job_title=job.title,
            job_company=job.company or "",
            resume_pdf_path=resume_pdf_path,
            cover_letter=application.cover_letter,
        )

        scraper = get_scraper(platform.name, str(user.id))
        try:
            if credential and credential.encrypted_password:
                password = encryption_service.decrypt(credential.encrypted_password)
                logged_in = await scraper.login(credential.username, password)
                if not logged_in:
                    return await _fail_application(
                        db, application,
                        f"Login failed for {platform.name}. Check credentials.",
                        retryable=True,
                    )
            elif not credential:
                logger.warning(f"No credentials for {platform.name}, attempting without auth")

            result = await scraper.apply_to_job(job.url, app_data)

            if result.success:
                application.status = "applied"
                application.applied_at = datetime.now(timezone.utc)
                application.error_log = None
                await db.commit()
                logger.info(f"Successfully applied to {job.title} at {job.company}")
                return {
                    "success": True,
                    "message": result.message,
                    "screenshot_path": result.screenshot_path,
                }
            else:
                return await _fail_application(
                    db, application,
                    f"Apply failed: {result.message}",
                    screenshot_path=result.screenshot_path,
                    retryable=True,
                )

        except Exception as e:
            logger.error(f"Auto-apply error for application {application_id}: {e}")
            return await _fail_application(
                db, application,
                f"Unexpected error: {str(e)}",
                retryable=True,
            )
        finally:
            await scraper.close()


async def _fail_application(
    db: AsyncSession,
    application: JobApplication,
    error_message: str,
    screenshot_path: str | None = None,
    retryable: bool = False,
) -> dict:
    """Mark application as failed and log the error."""
    application.retry_count = (application.retry_count or 0) + 1

    if retryable and application.retry_count < application.max_retries:
        application.status = "approved"
        application.error_log = f"[Attempt {application.retry_count}] {error_message}"
        logger.warning(
            f"Application {application.id} failed (attempt {application.retry_count}/{application.max_retries}): {error_message}"
        )
    else:
        application.status = "failed"
        application.error_log = error_message
        logger.error(f"Application {application.id} permanently failed: {error_message}")

    await db.commit()

    return {
        "success": False,
        "message": error_message,
        "screenshot_path": screenshot_path,
        "retryable": retryable and application.retry_count < application.max_retries,
    }
