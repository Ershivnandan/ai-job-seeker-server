import json

from app.scrapers.base_scraper import ApplicationData
from app.services.llm import get_llm_provider
from app.prompts.form_filling import (
    FORM_FILLING_SYSTEM,
    FORM_FILLING_USER,
    COVER_LETTER_FIELD_SYSTEM,
    COVER_LETTER_FIELD_USER,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def prepare_application_data(
    user_info: dict,
    user_skills: list[str],
    job_title: str,
    job_company: str,
    resume_pdf_path: str | None,
    cover_letter: str | None = None,
    screening_questions: list[dict] | None = None,
) -> ApplicationData:
    """Build ApplicationData from user profile, optionally answering screening questions via LLM."""
    additional_answers = {}

    if screening_questions:
        try:
            answers = await answer_screening_questions(
                candidate_name=user_info["full_name"],
                candidate_email=user_info["email"],
                candidate_phone=user_info.get("phone", ""),
                candidate_location=user_info.get("location", ""),
                years_experience=user_info.get("years_experience", "Not specified"),
                user_skills=user_skills,
                current_role=user_info.get("current_role", ""),
                job_title=job_title,
                job_company=job_company,
                questions=screening_questions,
            )
            additional_answers = answers
        except Exception as e:
            logger.warning(f"Failed to answer screening questions: {e}")

    return ApplicationData(
        resume_pdf_path=resume_pdf_path or "",
        full_name=user_info["full_name"],
        email=user_info["email"],
        phone=user_info.get("phone"),
        cover_letter=cover_letter,
        additional_answers=additional_answers,
    )


async def answer_screening_questions(
    candidate_name: str,
    candidate_email: str,
    candidate_phone: str,
    candidate_location: str,
    years_experience: str | int,
    user_skills: list[str],
    current_role: str,
    job_title: str,
    job_company: str,
    questions: list[dict],
) -> dict:
    """Use LLM to answer screening questions on job application forms."""
    llm = get_llm_provider()

    questions_json = json.dumps(questions, indent=2)

    prompt = FORM_FILLING_USER.format(
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone or "Not provided",
        candidate_location=candidate_location or "Not provided",
        years_experience=years_experience or "Not specified",
        user_skills=", ".join(user_skills[:30]),
        current_role=current_role or "Not specified",
        job_title=job_title,
        job_company=job_company,
        questions_json=questions_json,
    )

    messages = [
        {"role": "system", "content": FORM_FILLING_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    result = await llm.complete_json(messages)
    return result.get("answers", [])


async def generate_brief_cover_message(
    candidate_name: str,
    matching_skills: list[str],
    job_title: str,
    job_company: str,
) -> str:
    """Generate a short cover message for application form text fields."""
    llm = get_llm_provider()

    prompt = COVER_LETTER_FIELD_USER.format(
        candidate_name=candidate_name,
        matching_skills=", ".join(matching_skills[:10]),
        job_title=job_title,
        job_company=job_company,
    )

    messages = [
        {"role": "system", "content": COVER_LETTER_FIELD_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    result = await llm.complete_json(messages)
    return result.get("message", "")
