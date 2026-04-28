import re
from dataclasses import dataclass, field

import fitz  # PyMuPDF

from app.utils.logger import get_logger

logger = get_logger(__name__)

SECTION_PATTERNS = {
    "summary": r"(?i)^(?:professional\s+)?(?:summary|profile|objective|about\s+me)",
    "experience": r"(?i)^(?:work\s+)?(?:experience|employment|work\s+history|professional\s+experience)",
    "education": r"(?i)^(?:education|academic|qualifications|degrees)",
    "skills": r"(?i)^(?:technical\s+)?(?:skills|technologies|competencies|tech\s+stack|expertise)",
    "projects": r"(?i)^(?:projects|personal\s+projects|key\s+projects|notable\s+projects)",
    "certifications": r"(?i)^(?:certifications?|licenses?|credentials|professional\s+development)",
    "awards": r"(?i)^(?:awards?|honors?|achievements?|recognition)",
    "publications": r"(?i)^(?:publications?|papers?|research)",
    "languages": r"(?i)^(?:languages?|linguistic)",
    "interests": r"(?i)^(?:interests?|hobbies|activities)",
}


@dataclass
class ParsedResume:
    raw_text: str
    sections: dict[str, str] = field(default_factory=dict)
    structured: dict = field(default_factory=dict)


def _detect_section(line: str) -> str | None:
    cleaned = line.strip().rstrip(":")
    if not cleaned or len(cleaned) > 80:
        return None
    for section_name, pattern in SECTION_PATTERNS.items():
        if re.match(pattern, cleaned):
            return section_name
    return None


def _parse_experience_entries(text: str) -> list[dict]:
    entries = []
    lines = text.strip().split("\n")
    current_entry = None

    date_pattern = re.compile(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)"
        r"[\s,]*\d{4}\s*[-–—to]+\s*(?:Present|Current|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)"
        r"[\s,]*\d{4})",
        re.IGNORECASE,
    )

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if date_pattern.search(line):
            if current_entry:
                entries.append(current_entry)
            current_entry = {"header": line, "bullets": []}
        elif line.startswith(("•", "-", "–", "▪", "●", "*", "◦")) and current_entry:
            current_entry["bullets"].append(line.lstrip("•-–▪●*◦ ").strip())
        elif current_entry:
            if not current_entry["bullets"]:
                current_entry["header"] += " " + line
            else:
                current_entry["bullets"].append(line)

    if current_entry:
        entries.append(current_entry)

    return entries


def _extract_skills_list(text: str) -> list[str]:
    skills = []
    for line in text.strip().split("\n"):
        line = line.strip().lstrip("•-–▪●*◦ ").strip()
        if not line:
            continue
        parts = re.split(r"[,;|/]|\s{2,}", line)
        for part in parts:
            part = part.strip().rstrip(".")
            if part and len(part) < 60:
                skills.append(part)
    return skills


def parse_pdf(file_path: str) -> ParsedResume:
    logger.info(f"Parsing PDF: {file_path}")

    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text("text") + "\n"
    doc.close()

    if len(full_text.strip()) < 50:
        logger.warning("PyMuPDF extracted very little text, trying pdfplumber fallback")
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as e:
            logger.error(f"pdfplumber fallback failed: {e}")

    lines = full_text.split("\n")
    sections: dict[str, list[str]] = {}
    current_section = "header"
    sections[current_section] = []

    for line in lines:
        detected = _detect_section(line)
        if detected:
            current_section = detected
            sections.setdefault(current_section, [])
        else:
            sections.setdefault(current_section, []).append(line)

    section_texts = {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}

    structured = {}

    if "experience" in section_texts:
        structured["experience"] = _parse_experience_entries(section_texts["experience"])

    if "skills" in section_texts:
        structured["skills_list"] = _extract_skills_list(section_texts["skills"])

    if "header" in section_texts:
        structured["header"] = section_texts["header"]

    if "summary" in section_texts:
        structured["summary"] = section_texts["summary"]

    if "education" in section_texts:
        structured["education"] = section_texts["education"]

    if "projects" in section_texts:
        structured["projects"] = section_texts["projects"]

    if "certifications" in section_texts:
        structured["certifications"] = section_texts["certifications"]

    logger.info(f"Parsed {len(section_texts)} sections: {list(section_texts.keys())}")

    return ParsedResume(
        raw_text=full_text,
        sections=section_texts,
        structured=structured,
    )
