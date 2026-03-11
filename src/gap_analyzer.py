"""Analyze gaps between a resume and job description using the Claude API."""

import json
import logging

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_GAP_ANALYSIS
from .llm_client import call_llm, is_ollama_model, normalize_response
from .models import GapAnalysis, JDAnalysis
from .prompts import GAP_ANALYSIS_SYSTEM, GAP_ANALYSIS_USER

logger = logging.getLogger(__name__)


def analyze_gaps(
    resume_text: str, jd_analysis: JDAnalysis, model: str = DEFAULT_MODEL
) -> GapAnalysis:
    """Compare resume against JD analysis to find gaps and strengths.

    Returns a GapAnalysis with 'gaps' (list of GapEntry) and
    'strengths' (list of strings).
    """
    logger.info("Running gap analysis")

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_GAP_ANALYSIS,
        system=GAP_ANALYSIS_SYSTEM,
        user_content=GAP_ANALYSIS_USER.format(
            resume_text=resume_text,
            jd_analysis=json.dumps(jd_analysis.to_dict(), indent=2),
        ),
        purpose="gap analysis",
    )

    try:
        data = parse_json_response(response_text)
    except Exception:
        logger.warning("Failed to parse gap analysis response. Raw LLM output:\n%s", response_text)
        raise
    if is_ollama_model(model):
        logger.debug("Raw gap analysis response from Ollama: %s", data)
    data = normalize_response(data, schema="gap_analysis")
    result = GapAnalysis.from_dict(data)
    logger.info(
        "Gap analysis complete: %d gaps, %d strengths",
        len(result.gaps),
        len(result.strengths),
    )
    return result
