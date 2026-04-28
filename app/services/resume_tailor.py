import json

from app.services.llm import get_llm_provider
from app.prompts.resume_tailoring import RESUME_TAILORING_SYSTEM, RESUME_TAILORING_USER
from app.prompts.cover_letter import COVER_LETTER_SYSTEM, COVER_LETTER_USER
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def tailor_resume(
    resume_json: dict,
    user_skills: list[str],
    job_title: str,
    job_company: str,
    job_description: str,
    required_skills: list[str] | None = None,
    matching_skills: list[str] | None = None,
    missing_skills: list[str] | None = None,
) -> dict:
    """Tailor a parsed resume for a specific job using LLM.

    Returns the tailored resume JSON with sections reordered/rephrased
    and tailoring notes documenting what changed.
    """
    llm = get_llm_provider()

    prompt = RESUME_TAILORING_USER.format(
        resume_json=json.dumps(resume_json, indent=2)[:4000],
        user_skills=", ".join(user_skills),
        job_title=job_title,
        job_company=job_company or "Unknown",
        job_description=job_description[:3000],
        required_skills=", ".join(required_skills or []),
        matching_skills=", ".join(matching_skills or []),
        missing_skills=", ".join(missing_skills or []),
    )

    messages = [
        {"role": "system", "content": RESUME_TAILORING_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    result = await llm.complete_json(messages)

    _validate_tailored_resume(result, resume_json, user_skills)

    return result


def _validate_tailored_resume(tailored: dict, original: dict, user_skills: list[str]):
    """Post-validation: ensure LLM didn't fabricate content."""
    user_skills_lower = {s.lower() for s in user_skills}
    original_skills = set()
    if isinstance(original.get("skills"), dict):
        for section_skills in original["skills"].values():
            if isinstance(section_skills, list):
                original_skills.update(s.lower() for s in section_skills)
    elif isinstance(original.get("skills"), list):
        original_skills.update(s.lower() for s in original["skills"])

    all_known_skills = user_skills_lower | original_skills

    tailored_primary = tailored.get("skills", {}).get("primary", [])
    tailored_secondary = tailored.get("skills", {}).get("secondary", [])
    all_tailored = [s.lower() for s in tailored_primary + tailored_secondary]

    fabricated = [s for s in all_tailored if s not in all_known_skills]
    if fabricated:
        logger.warning(f"LLM fabricated skills detected and removed: {fabricated}")
        tailored["skills"]["primary"] = [
            s for s in tailored_primary if s.lower() in all_known_skills
        ]
        tailored["skills"]["secondary"] = [
            s for s in tailored_secondary if s.lower() in all_known_skills
        ]
        tailored.setdefault("tailoring_notes", {})["fabrication_warning"] = (
            f"Removed fabricated skills: {fabricated}"
        )

    original_companies = set()
    for exp in original.get("experience", []):
        if isinstance(exp, dict) and exp.get("company"):
            original_companies.add(exp["company"].lower())

    for exp in tailored.get("experience", []):
        if isinstance(exp, dict) and exp.get("company"):
            if exp["company"].lower() not in original_companies:
                logger.error(f"LLM fabricated company: {exp['company']}")
                tailored.setdefault("tailoring_notes", {})["fabrication_warning"] = (
                    f"Suspicious company name: {exp['company']}"
                )


async def generate_cover_letter(
    candidate_name: str,
    user_skills: list[str],
    experience_summary: str,
    job_title: str,
    job_company: str,
    job_location: str,
    job_description: str,
    matching_skills: list[str] | None = None,
    missing_skills: list[str] | None = None,
) -> dict:
    """Generate a cover letter for a specific job application."""
    llm = get_llm_provider()

    prompt = COVER_LETTER_USER.format(
        candidate_name=candidate_name,
        user_skills=", ".join(user_skills),
        experience_summary=experience_summary[:2000],
        job_company=job_company or "Unknown",
        job_title=job_title,
        job_location=job_location or "Unknown",
        job_description=job_description[:3000],
        matching_skills=", ".join(matching_skills or []),
        missing_skills=", ".join(missing_skills or []),
    )

    messages = [
        {"role": "system", "content": COVER_LETTER_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    result = await llm.complete_json(messages)

    return {
        "cover_letter": result.get("cover_letter", ""),
        "key_points": result.get("key_points", []),
    }
