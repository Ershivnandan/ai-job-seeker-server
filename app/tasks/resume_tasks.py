import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.resume import Resume
from app.models.skill import Skill
from app.services.resume_parser import parse_pdf
from app.services.skill_extractor import extract_skills
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _parse_resume(resume_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Resume).where(Resume.id == uuid.UUID(resume_id)))
        resume = result.scalar_one_or_none()
        if not resume:
            logger.error(f"Resume {resume_id} not found")
            return

        resume.parse_status = "parsing"
        await db.commit()

        try:
            parsed = parse_pdf(resume.file_path)

            resume.parsed_text = parsed.raw_text
            resume.parsed_json = {
                "sections": parsed.sections,
                "structured": parsed.structured,
            }
            resume.parse_status = "completed"
            await db.commit()

            logger.info(f"Resume {resume_id} parsed successfully")
        except Exception as e:
            logger.error(f"Failed to parse resume {resume_id}: {e}")
            resume.parse_status = "failed"
            await db.commit()
            raise


async def _extract_skills(resume_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Resume).where(Resume.id == uuid.UUID(resume_id)))
        resume = result.scalar_one_or_none()
        if not resume or not resume.parsed_json:
            logger.error(f"Resume {resume_id} not found or not parsed")
            return

        parsed_json = resume.parsed_json
        sections = parsed_json.get("sections", {})
        structured = parsed_json.get("structured", {})

        skills_section = sections.get("skills", "")
        experience_entries = structured.get("experience", [])
        experience_text = "\n".join(
            f"{e.get('header', '')}\n" + "\n".join(f"- {b}" for b in e.get("bullets", []))
            for e in experience_entries
        )

        try:
            extracted = await extract_skills(
                resume_text=resume.parsed_text or "",
                skills_section=skills_section,
                experience_text=experience_text,
            )

            for skill_data in extracted:
                existing = await db.execute(
                    select(Skill).where(
                        Skill.user_id == resume.user_id,
                        Skill.name == skill_data["name"],
                        Skill.category == skill_data["category"],
                    )
                )
                existing_skill = existing.scalar_one_or_none()

                if existing_skill:
                    existing_skill.proficiency = skill_data["proficiency"]
                    existing_skill.years_used = skill_data["years_used"]
                    existing_skill.confidence = skill_data["confidence"]
                    existing_skill.resume_id = resume.id
                else:
                    skill = Skill(
                        user_id=resume.user_id,
                        resume_id=resume.id,
                        name=skill_data["name"],
                        category=skill_data["category"],
                        proficiency=skill_data["proficiency"],
                        years_used=skill_data["years_used"],
                        source="extracted",
                        confidence=skill_data["confidence"],
                    )
                    db.add(skill)

            await db.commit()
            logger.info(f"Stored {len(extracted)} skills for resume {resume_id}")
        except Exception as e:
            logger.error(f"Skill extraction failed for resume {resume_id}: {e}")
            raise


@celery_app.task(name="app.tasks.resume_tasks.parse_resume", bind=True, max_retries=2)
def parse_resume(self, resume_id: str):
    logger.info(f"Task: parsing resume {resume_id}")
    try:
        _run_async(_parse_resume(resume_id))
        extract_skills_task.delay(resume_id)
    except Exception as exc:
        logger.error(f"Parse task failed: {exc}")
        self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.tasks.resume_tasks.extract_skills_task", bind=True, max_retries=2)
def extract_skills_task(self, resume_id: str):
    logger.info(f"Task: extracting skills from resume {resume_id}")
    try:
        _run_async(_extract_skills(resume_id))
    except Exception as exc:
        logger.error(f"Skill extraction task failed: {exc}")
        self.retry(exc=exc, countdown=30)
