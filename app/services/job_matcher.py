from app.services.llm import get_llm_provider
from app.prompts.job_matching import JOB_MATCHING_SYSTEM, JOB_MATCHING_USER
from app.utils.logger import get_logger

logger = get_logger(__name__)

SCORE_WEIGHTS = {
    "skill_match": 0.4,
    "experience_match": 0.25,
    "role_fit": 0.25,
    "location_match": 0.1,
}


def quick_skill_overlap(user_skills: list[str], job_description: str) -> float:
    if not user_skills or not job_description:
        return 0.0

    job_lower = job_description.lower()
    matches = sum(1 for skill in user_skills if skill.lower() in job_lower)
    return matches / len(user_skills) if user_skills else 0.0


async def deep_match(
    user_skills: list[str],
    experience_years: int,
    preferred_roles: list[str],
    preferred_locations: list[str],
    job_title: str,
    job_company: str,
    job_location: str,
    job_description: str,
) -> dict:
    llm = get_llm_provider()

    prompt = JOB_MATCHING_USER.format(
        user_skills=", ".join(user_skills),
        experience_years=experience_years or "Unknown",
        preferred_roles=", ".join(preferred_roles) if preferred_roles else "Any",
        preferred_locations=", ".join(preferred_locations) if preferred_locations else "Any",
        job_title=job_title,
        job_company=job_company or "Unknown",
        job_location=job_location or "Unknown",
        job_description=job_description[:3000],
    )

    messages = [
        {"role": "system", "content": JOB_MATCHING_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    result = await llm.complete_json(messages)

    skill_match = min(max(result.get("skill_match", 0.0), 0.0), 1.0)
    experience_match = min(max(result.get("experience_match", 0.0), 0.0), 1.0)
    role_fit = min(max(result.get("role_fit", 0.0), 0.0), 1.0)
    location_match = min(max(result.get("location_match", 0.0), 0.0), 1.0)

    overall_score = (
        skill_match * SCORE_WEIGHTS["skill_match"]
        + experience_match * SCORE_WEIGHTS["experience_match"]
        + role_fit * SCORE_WEIGHTS["role_fit"]
        + location_match * SCORE_WEIGHTS["location_match"]
    )

    return {
        "overall_score": round(overall_score, 3),
        "skill_match": skill_match,
        "experience_match": experience_match,
        "role_fit": role_fit,
        "location_match": location_match,
        "required_skills": result.get("required_skills", []),
        "matching_skills": result.get("matching_skills", []),
        "missing_skills": result.get("missing_skills", []),
        "summary": result.get("summary", ""),
    }
