"""Generate tailored resume content using the Claude API."""

import json
import logging

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_RESUME_GENERATION
from .llm_client import call_llm
from .models import ResumeContent, JDAnalysis
from .prompts import RESUME_GENERATION_SYSTEM, RESUME_GENERATION_USER

logger = logging.getLogger(__name__)


def generate_tailored_resume(
    resume_text: str,
    jd_analysis: JDAnalysis,
    user_additions: str = "",
    model: str = DEFAULT_MODEL,
) -> ResumeContent:
    """Generate tailored resume content via Claude.

    Takes the original resume text, the structured JD analysis, and optional
    additional context from the user (gap answers, extra skills, etc.).
    Returns a ResumeContent with the tailored resume sections.
    """
    logger.info("Generating tailored resume content")

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_RESUME_GENERATION,
        system=RESUME_GENERATION_SYSTEM,
        user_content=RESUME_GENERATION_USER.format(
            resume_text=resume_text,
            jd_analysis=json.dumps(jd_analysis.to_dict(), indent=2),
            user_additions=user_additions,
        ),
    )

    data = parse_json_response(response_text)
    result = ResumeContent.from_dict(data)
    logger.info(
        "Resume generated: %d experience entries, %d skills",
        len(result.experience),
        len(result.skills),
    )
    return result
