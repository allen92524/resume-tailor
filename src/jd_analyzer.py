"""Analyze job descriptions using the Claude API."""

import logging

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_JD_ANALYSIS
from .llm_client import call_llm
from .models import JDAnalysis
from .prompts import (
    JD_ANALYSIS_SYSTEM,
    JD_ANALYSIS_USER,
    JD_ANALYSIS_WITH_REFERENCE_USER,
)

logger = logging.getLogger(__name__)


def analyze_jd(
    jd_text: str, reference_text: str | None = None, model: str = DEFAULT_MODEL
) -> JDAnalysis:
    """Send a job description to Claude and return structured analysis.

    Returns a JDAnalysis with keys: job_title, company, required_skills,
    preferred_skills, key_responsibilities, keywords, experience_level,
    industry, culture_signals.  When *reference_text* is provided the
    response also includes style_insights.
    """
    logger.info("Analyzing job description (%d chars)", len(jd_text))

    if reference_text:
        logger.info(
            "Including reference resume (%d chars) for style analysis",
            len(reference_text),
        )
        user_content = JD_ANALYSIS_WITH_REFERENCE_USER.format(
            jd_text=jd_text,
            reference_text=reference_text,
        )
    else:
        user_content = JD_ANALYSIS_USER.format(jd_text=jd_text)

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_JD_ANALYSIS,
        system=JD_ANALYSIS_SYSTEM,
        user_content=user_content,
    )

    data = parse_json_response(response_text)
    result = JDAnalysis.from_dict(data)
    logger.info(
        "JD analysis complete: role=%s, company=%s", result.job_title, result.company
    )
    return result


def collect_jd_text() -> str:
    """Interactively collect job description text from the user.

    Accepts either a file path or pasted text (end with END on its own line).
    Auto-detects file paths starting with / or ~.
    """
    from .resume_parser import _looks_like_file_path, read_resume_from_file

    logger.info("Collecting job description text from user")
    print("\nProvide the job description: paste content below, or enter a file path.")
    print("Supported file formats: .txt, .md, .docx, .pdf")
    print("When pasting, type END on its own line to finish.\n")

    while True:
        lines: list[str] = []
        try:
            first_line = input()
        except EOFError:
            return ""

        if _looks_like_file_path(first_line):
            try:
                return read_resume_from_file(first_line.strip())
            except (FileNotFoundError, ValueError) as e:
                logger.warning("Failed to read JD file: %s", e)
                print(f"\nError: {e}")
                print("Please try again.\n")
                continue

        lines.append(first_line)

        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "END":
                break
            lines.append(line)

        result = "\n".join(lines).strip()
        if result:
            logger.info("JD text collected: %d chars", len(result))
            return result

        print("No content received. Please try again.\n")
