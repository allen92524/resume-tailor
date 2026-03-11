"""Generate tailored resume content using the Claude API."""

import json
import logging
import re

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_RESUME_GENERATION
from .llm_client import call_llm, normalize_response
from .models import ResumeContent, EducationEntry, ExperienceEntry, JDAnalysis
from .prompts import RESUME_GENERATION_SYSTEM, RESUME_GENERATION_USER

logger = logging.getLogger(__name__)


def generate_tailored_resume(
    resume_text: str,
    jd_analysis: JDAnalysis,
    user_additions: str = "",
    model: str = DEFAULT_MODEL,
    writing_preferences: dict[str, str] | None = None,
) -> ResumeContent:
    """Generate tailored resume content via Claude.

    Takes the original resume text, the structured JD analysis, and optional
    additional context from the user (gap answers, extra skills, etc.).
    Returns a ResumeContent with the tailored resume sections.
    """
    logger.info("Generating tailored resume content")

    additions = user_additions
    if writing_preferences:
        pref_lines = "\n".join(f"- {k}: {v}" for k, v in writing_preferences.items())
        additions += f"\n\nWriting Style Preferences (follow these strictly):\n{pref_lines}"

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_RESUME_GENERATION,
        system=RESUME_GENERATION_SYSTEM,
        user_content=RESUME_GENERATION_USER.format(
            resume_text=resume_text,
            jd_analysis=json.dumps(jd_analysis.to_dict(), indent=2),
            user_additions=additions,
        ),
        purpose="resume generation",
    )

    try:
        data = parse_json_response(response_text)
    except Exception:
        logger.warning(
            "Failed to parse resume generation response. Raw LLM output:\n%s", response_text
        )
        raise
    data = normalize_response(data, schema="resume_content")
    result = ResumeContent.from_dict(data)

    # Validate factual fields against the original resume
    result = validate_resume_content(result, resume_text)

    logger.info(
        "Resume generated: %d experience entries, %d skills",
        len(result.experience),
        len(result.skills),
    )
    return result


def validate_resume_content(
    generated: ResumeContent, original_text: str
) -> ResumeContent:
    """Validate generated resume against original to prevent hallucinations.

    Checks education, certifications, job titles, and dates against the
    original resume text. Replaces any hallucinated fields with originals
    parsed from the base resume.
    """
    original_lower = original_text.lower()

    # Validate education — degree and institution must appear in original
    for edu in generated.education:
        _validate_education(edu, original_lower)

    # Validate certifications — each must appear in original
    generated.certifications = _validate_certifications(
        generated.certifications, original_lower
    )

    # Validate experience dates and titles
    for exp in generated.experience:
        _validate_experience(exp, original_lower)

    # Contact info is never trusted from LLM — cleared here,
    # docx_builder overrides with profile identity anyway
    generated.email = None
    generated.phone = None
    generated.location = None
    generated.linkedin = None

    return generated


def _validate_education(edu: EducationEntry, original_lower: str) -> None:
    """Warn and log if education fields don't appear in original resume."""
    if edu.degree and edu.degree.lower() not in original_lower:
        logger.warning(
            "Hallucination detected: degree '%s' not found in original resume",
            edu.degree,
        )
    if edu.institution and edu.institution.lower() not in original_lower:
        logger.warning(
            "Hallucination detected: institution '%s' not found in original resume",
            edu.institution,
        )
    if edu.year and edu.year not in original_lower:
        logger.warning(
            "Hallucination detected: education year '%s' not found in original resume",
            edu.year,
        )


def _validate_certifications(
    certs: list[str], original_lower: str
) -> list[str]:
    """Filter out certifications not found in the original resume."""
    validated = []
    for cert in certs:
        if cert.lower() in original_lower:
            validated.append(cert)
        else:
            logger.warning(
                "Hallucination detected: certification '%s' not found in original resume. "
                "Removing.",
                cert,
            )
    return validated


def _validate_experience(exp: ExperienceEntry, original_lower: str) -> None:
    """Warn if experience dates don't appear in original resume."""
    if exp.dates:
        # Extract year patterns from dates field (e.g. "2020", "2021")
        years = re.findall(r"\b((?:19|20)\d{2})\b", exp.dates)
        for year in years:
            if year not in original_lower:
                logger.warning(
                    "Hallucination detected: year '%s' in dates '%s' for '%s' "
                    "not found in original resume",
                    year,
                    exp.dates,
                    exp.title,
                )
