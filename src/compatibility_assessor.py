"""Assess compatibility between a resume and job description using the Claude API."""

import json
import logging

import click

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_COMPATIBILITY
from .llm_client import call_llm, normalize_response
from .models import CompatibilityAssessment, JDAnalysis
from .prompts import COMPATIBILITY_ASSESSMENT_SYSTEM, COMPATIBILITY_ASSESSMENT_USER

logger = logging.getLogger(__name__)


def assess_compatibility(
    resume_text: str, jd_analysis: JDAnalysis, model: str = DEFAULT_MODEL
) -> CompatibilityAssessment:
    """Score how well a resume matches a JD analysis.

    Returns a CompatibilityAssessment with match_score, strong_matches,
    addressable_gaps, missing, recommendation, and proceed (bool).
    """
    logger.info("Assessing resume-JD compatibility")

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_COMPATIBILITY,
        system=COMPATIBILITY_ASSESSMENT_SYSTEM,
        user_content=COMPATIBILITY_ASSESSMENT_USER.format(
            resume_text=resume_text,
            jd_analysis=json.dumps(jd_analysis.to_dict(), indent=2),
        ),
        purpose="compatibility assessment",
    )

    try:
        data = parse_json_response(response_text)
    except Exception:
        logger.warning(
            "Failed to parse compatibility response. Raw LLM output:\n%s", response_text
        )
        raise
    data = normalize_response(data, schema="compatibility")
    result = CompatibilityAssessment.from_dict(data)
    logger.info(
        "Compatibility score: %d%% (proceed=%s)", result.match_score, result.proceed
    )
    return result


def display_assessment(assessment: CompatibilityAssessment) -> None:
    """Display the compatibility assessment as a formatted terminal report."""
    score = assessment.match_score

    # Score bar
    filled = score // 5
    bar = "\u2588" * filled + "\u2591" * (20 - filled)

    click.echo("\n" + "=" * 50)
    click.echo("  Compatibility Assessment")
    click.echo("=" * 50)

    # Color the score
    if score >= 70:
        color = "green"
    elif score >= 50:
        color = "yellow"
    elif score >= 30:
        color = "red"
    else:
        color = "bright_red"
    click.echo(
        f"\n  Match Score: [{bar}] {click.style(f'{score}%', fg=color, bold=True)}"
    )

    # Strong matches
    if assessment.strong_matches:
        click.echo(click.style("\n  Strong Matches:", fg="green", bold=True))
        for item in assessment.strong_matches:
            click.echo(f"    + {item}")

    # Addressable gaps
    if assessment.addressable_gaps:
        click.echo(
            click.style(
                "\n  Addressable Gaps (transferable experience):",
                fg="yellow",
                bold=True,
            )
        )
        for item in assessment.addressable_gaps:
            click.echo(f"    ~ {item}")

    # Missing
    if assessment.missing:
        click.echo(click.style("\n  Missing:", fg="red", bold=True))
        for item in assessment.missing:
            click.echo(f"    - {item}")

    # Recommendation
    if assessment.recommendation:
        click.echo(f"\n  Recommendation: {assessment.recommendation}")

    click.echo("")
