from app.services.llm import get_llm_provider
from app.prompts.skill_extraction import SKILL_EXTRACTION_SYSTEM, SKILL_EXTRACTION_USER
from app.utils.logger import get_logger

logger = get_logger(__name__)

SKILL_NORMALIZATION = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "react.js": "React",
    "reactjs": "React",
    "react js": "React",
    "vue.js": "Vue",
    "vuejs": "Vue",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "express.js": "Express",
    "expressjs": "Express",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "gcp": "Google Cloud",
    "google cloud platform": "Google Cloud",
    "tf": "TensorFlow",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "py": "Python",
    "python": "Python",
    "cpp": "C++",
    "c++": "C++",
    "csharp": "C#",
    "c#": "C#",
    "golang": "Go",
    "go": "Go",
}


def normalize_skill_name(name: str) -> str:
    return SKILL_NORMALIZATION.get(name.lower().strip(), name.strip())


async def extract_skills(
    resume_text: str,
    skills_section: str = "",
    experience_text: str = "",
) -> list[dict]:
    llm = get_llm_provider()

    prompt = SKILL_EXTRACTION_USER.format(
        resume_text=resume_text[:6000],
        skills_section=skills_section[:2000] if skills_section else "Not available",
        experience_text=experience_text[:3000] if experience_text else "Not available",
    )

    messages = [
        {"role": "system", "content": SKILL_EXTRACTION_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    logger.info("Sending resume to LLM for skill extraction")
    result = await llm.complete_json(messages)

    skills = result.get("skills", [])
    logger.info(f"LLM extracted {len(skills)} skills")

    normalized = []
    seen = set()
    for skill in skills:
        name = normalize_skill_name(skill.get("name", ""))
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        normalized.append({
            "name": name,
            "category": skill.get("category", "other"),
            "proficiency": skill.get("proficiency", "intermediate"),
            "years_used": skill.get("years_used"),
            "confidence": min(max(skill.get("confidence", 0.5), 0.0), 1.0),
        })

    logger.info(f"After normalization and dedup: {len(normalized)} skills")
    return normalized
