import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.tasks.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.resume import Resume
from app.models.skill import Skill
from app.models.job import Job
from app.models.job_application import JobApplication
from app.models.resume_variant import ResumeVariant
from app.services.resume_tailor import tailor_resume, generate_cover_letter
from app.services.latex_generator import generate_and_compile
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _tailor_and_compile(application_id: str, template_name: str = "resume_classic"):
    """Full tailoring pipeline for a single application."""
    async with AsyncSessionLocal() as db:
        app_result = await db.execute(
            select(JobApplication).where(JobApplication.id == uuid.UUID(application_id))
        )
        application = app_result.scalar_one_or_none()
        if not application:
            logger.error(f"Application {application_id} not found")
            return

        application.status = "tailoring"
        await db.commit()

        user_result = await db.execute(select(User).where(User.id == application.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            logger.error(f"User not found for application {application_id}")
            application.status = "failed"
            application.error_log = "User not found"
            await db.commit()
            return

        resume_result = await db.execute(
            select(Resume).where(
                Resume.user_id == user.id,
                Resume.is_primary == True,
                Resume.parse_status == "completed",
            )
        )
        resume = resume_result.scalar_one_or_none()
        if not resume:
            resume_result = await db.execute(
                select(Resume)
                .where(Resume.user_id == user.id, Resume.parse_status == "completed")
                .order_by(Resume.created_at.desc())
                .limit(1)
            )
            resume = resume_result.scalar_one_or_none()

        if not resume or not resume.parsed_json:
            logger.error(f"No parsed resume found for user {user.id}")
            application.status = "failed"
            application.error_log = "No parsed resume available"
            await db.commit()
            return

        job_result = await db.execute(select(Job).where(Job.id == application.job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            logger.error(f"Job not found for application {application_id}")
            application.status = "failed"
            application.error_log = "Job not found"
            await db.commit()
            return

        skills_result = await db.execute(
            select(Skill).where(Skill.user_id == user.id)
        )
        user_skills = [s.name for s in skills_result.scalars().all()]

        match_details = application.match_details or {}
        required_skills = match_details.get("required_skills", [])
        matching_skills = match_details.get("matching_skills", [])
        missing_skills = match_details.get("missing_skills", [])

        try:
            tailored = await tailor_resume(
                resume_json=resume.parsed_json.get("structured", resume.parsed_json),
                user_skills=user_skills,
                job_title=job.title,
                job_company=job.company or "",
                job_description=job.description or "",
                required_skills=required_skills,
                matching_skills=matching_skills,
                missing_skills=missing_skills,
            )
            logger.info(f"Resume tailored for application {application_id}")
        except Exception as e:
            logger.error(f"Tailoring failed for application {application_id}: {e}")
            application.status = "failed"
            application.error_log = f"Tailoring failed: {str(e)}"
            await db.commit()
            return

        user_info = {
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone or "",
            "location": user.location or "",
            "linkedin_url": user.linkedin_url or "",
            "github_url": user.github_url or "",
            "portfolio_url": user.portfolio_url or "",
        }

        try:
            output_filename = f"resume_{user.id}_{application.id}.pdf"
            latex_source, pdf_path = generate_and_compile(
                tailored_resume=tailored,
                user_info=user_info,
                template_name=template_name,
                output_filename=output_filename,
            )
            logger.info(f"LaTeX generated for application {application_id}, PDF: {pdf_path}")
        except Exception as e:
            logger.error(f"LaTeX generation failed for application {application_id}: {e}")
            application.status = "failed"
            application.error_log = f"LaTeX generation failed: {str(e)}"
            await db.commit()
            return

        existing_variant = await db.execute(
            select(ResumeVariant).where(ResumeVariant.application_id == application.id)
        )
        variant = existing_variant.scalar_one_or_none()

        if variant:
            variant.latex_source = latex_source
            variant.compiled_pdf_path = pdf_path
            variant.tailoring_notes = tailored.get("tailoring_notes", {})
            variant.status = "compiled" if pdf_path else "generated"
        else:
            variant = ResumeVariant(
                resume_id=resume.id,
                application_id=application.id,
                user_id=user.id,
                latex_source=latex_source,
                compiled_pdf_path=pdf_path,
                tailoring_notes=tailored.get("tailoring_notes", {}),
                status="compiled" if pdf_path else "generated",
            )
            db.add(variant)

        try:
            experience_entries = resume.parsed_json.get("structured", {}).get("experience", [])
            experience_summary = "\n".join(
                f"{e.get('header', '')}" for e in experience_entries[:3]
            )

            cover_result = await generate_cover_letter(
                candidate_name=user.full_name,
                user_skills=user_skills,
                experience_summary=experience_summary,
                job_title=job.title,
                job_company=job.company or "",
                job_location=job.location or "",
                job_description=job.description or "",
                matching_skills=matching_skills,
                missing_skills=missing_skills,
            )
            application.cover_letter = cover_result.get("cover_letter", "")
            logger.info(f"Cover letter generated for application {application_id}")
        except Exception as e:
            logger.warning(f"Cover letter generation failed (non-fatal): {e}")

        application.status = "ready_to_apply"
        await db.commit()
        logger.info(f"Application {application_id} is ready for review")


@celery_app.task(name="app.tasks.tailoring_tasks.tailor_application", bind=True, max_retries=2)
def tailor_application(self, application_id: str, template_name: str = "resume_classic"):
    logger.info(f"Task: tailoring application {application_id} with template {template_name}")
    try:
        _run_async(_tailor_and_compile(application_id, template_name))
    except Exception as exc:
        logger.error(f"Tailoring task failed: {exc}")
        self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.tasks.tailoring_tasks.batch_tailor", bind=True)
def batch_tailor(self, application_ids: list[str], template_name: str = "resume_classic"):
    logger.info(f"Task: batch tailoring {len(application_ids)} applications")
    for app_id in application_ids:
        tailor_application.delay(app_id, template_name)
