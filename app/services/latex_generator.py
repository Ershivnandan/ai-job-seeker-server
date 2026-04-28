import os
import shutil
import subprocess
import tempfile
import uuid

from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
GENERATED_DIR = os.path.join(settings.STORAGE_PATH, "generated")


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        autoescape=False,
    )


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters."""
    if not text:
        return ""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _escape_resume_data(data: dict) -> dict:
    """Recursively escape all string values in resume data for LaTeX."""
    if isinstance(data, str):
        return _escape_latex(data)
    elif isinstance(data, list):
        return [_escape_resume_data(item) for item in data]
    elif isinstance(data, dict):
        return {k: _escape_resume_data(v) for k, v in data.items()}
    return data


def generate_latex(
    tailored_resume: dict,
    user_info: dict,
    template_name: str = "resume_classic",
) -> str:
    """Render a tailored resume into LaTeX source using a Jinja2 template.

    Args:
        tailored_resume: The LLM-tailored resume JSON
        user_info: User profile data (name, email, phone, location, urls)
        template_name: Which template to use (resume_classic, resume_modern, resume_minimal)

    Returns:
        LaTeX source string
    """
    env = _get_jinja_env()
    template = env.get_template(f"{template_name}.tex")

    escaped_resume = _escape_resume_data(tailored_resume)
    escaped_user = _escape_resume_data(user_info)

    context = {
        "name": escaped_user.get("full_name", ""),
        "email": escaped_user.get("email", ""),
        "phone": escaped_user.get("phone", ""),
        "location": escaped_user.get("location", ""),
        "linkedin": escaped_user.get("linkedin_url", ""),
        "github": escaped_user.get("github_url", ""),
        "portfolio": escaped_user.get("portfolio_url", ""),
        "summary": escaped_resume.get("summary", ""),
        "skills_primary": escaped_resume.get("skills", {}).get("primary", []),
        "skills_secondary": escaped_resume.get("skills", {}).get("secondary", []),
        "experience": escaped_resume.get("experience", []),
        "education": escaped_resume.get("education", []),
        "projects": escaped_resume.get("projects", []),
        "certifications": escaped_resume.get("certifications", []),
    }

    return template.render(**context)


def compile_latex(latex_source: str, output_filename: str | None = None) -> str | None:
    """Compile LaTeX source to PDF using pdflatex.

    Args:
        latex_source: The LaTeX source code
        output_filename: Optional filename for the output PDF

    Returns:
        Path to compiled PDF, or None if compilation failed
    """
    os.makedirs(GENERATED_DIR, exist_ok=True)

    if not output_filename:
        output_filename = f"resume_{uuid.uuid4().hex[:8]}.pdf"

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_source)

        for _ in range(2):
            try:
                result = subprocess.run(
                    [
                        "pdflatex",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-output-directory", tmpdir,
                        tex_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except FileNotFoundError:
                logger.error("pdflatex not found — is texlive installed?")
                return None
            except subprocess.TimeoutExpired:
                logger.error("pdflatex compilation timed out")
                return None

        pdf_path = os.path.join(tmpdir, "resume.pdf")
        if not os.path.exists(pdf_path):
            log_path = os.path.join(tmpdir, "resume.log")
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    log_tail = f.read()[-2000:]
                logger.error(f"LaTeX compilation failed. Log tail:\n{log_tail}")
            return None

        final_path = os.path.join(GENERATED_DIR, output_filename)
        shutil.copy2(pdf_path, final_path)
        logger.info(f"PDF compiled successfully: {final_path}")
        return final_path


def generate_and_compile(
    tailored_resume: dict,
    user_info: dict,
    template_name: str = "resume_classic",
    output_filename: str | None = None,
) -> tuple[str, str | None]:
    """Generate LaTeX from tailored resume and compile to PDF.

    Returns:
        Tuple of (latex_source, pdf_path_or_none)
    """
    latex_source = generate_latex(tailored_resume, user_info, template_name)
    pdf_path = compile_latex(latex_source, output_filename)
    return latex_source, pdf_path
