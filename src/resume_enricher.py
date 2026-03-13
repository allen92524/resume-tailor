"""Enrich resumes by gathering missing information from the candidate."""

import json
import logging

import click

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_ENRICH, MAX_TOKENS_IMPROVE_ENRICHED
from .llm_client import call_llm, normalize_response
from .models import EnrichmentAnalysis
from .prompts import (
    RESUME_ENRICH_SYSTEM,
    RESUME_ENRICH_USER,
    RESUME_IMPROVE_ENRICHED_SYSTEM,
    RESUME_IMPROVE_ENRICHED_USER,
)

logger = logging.getLogger(__name__)


def enrich_resume(resume_text: str, model: str = DEFAULT_MODEL) -> EnrichmentAnalysis:
    """Analyze a resume to detect profession and identify information gaps.

    Returns an EnrichmentAnalysis with detected profession, strengths,
    and targeted questions about missing details.
    """
    logger.info("Enriching resume (%d chars)", len(resume_text))

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_ENRICH,
        system=RESUME_ENRICH_SYSTEM,
        user_content=RESUME_ENRICH_USER.format(resume_text=resume_text),
        purpose="resume enrichment",
    )

    try:
        data = parse_json_response(response_text)
    except Exception:
        logger.warning(
            "Failed to parse enrichment response. Raw LLM output:\n%s",
            response_text,
        )
        raise

    data = normalize_response(data, schema="resume_enrich")
    result = EnrichmentAnalysis.from_dict(data)
    logger.info(
        "Enrichment complete: profession=%s, %d questions",
        result.detected_profession,
        len(result.questions),
    )
    return result


def display_enrichment(enrichment: EnrichmentAnalysis) -> None:
    """Display enrichment analysis as a formatted terminal report."""
    click.echo("\n" + "=" * 50)
    click.echo("  Resume Analysis")
    click.echo("=" * 50)

    # Detected profession
    profession = enrichment.detected_profession or "Unknown"
    industry = enrichment.detected_industry or ""
    label = f"{profession} ({industry})" if industry else profession
    click.echo(f"\n  Detected: {click.style(label, fg='cyan', bold=True)}")

    # Strengths
    if enrichment.strengths:
        click.echo(click.style("\n  Strengths:", fg="green", bold=True))
        for item in enrichment.strengths:
            click.echo(f"    + {item}")

    # Question count
    n = len(enrichment.questions)
    if n:
        click.echo(
            f"\n  Found {click.style(str(n), bold=True)} areas where "
            f"additional details would strengthen your resume."
        )

    click.echo("")


def improve_resume_with_enrichment(
    resume_text: str,
    enrichment: EnrichmentAnalysis,
    answers: dict[str, str],
    model: str = DEFAULT_MODEL,
) -> str:
    """Improve a resume using real enrichment data from the candidate.

    Takes the original resume, the enrichment analysis, and a dict mapping
    question text to the candidate's answers. Returns the improved resume
    as plain text with no placeholders.
    """
    logger.info("Improving resume with %d enrichment answers", len(answers))

    # Build enrichment JSON pairing questions with answers
    enrichment_entries = []
    for q in enrichment.questions:
        answer = answers.get(q.question)
        if answer:
            enrichment_entries.append(
                {
                    "role": q.role,
                    "bullet_text": q.bullet_text,
                    "question": q.question,
                    "answer": answer,
                }
            )

    enrichment_json = json.dumps(enrichment_entries, indent=2)

    text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_IMPROVE_ENRICHED,
        system=RESUME_IMPROVE_ENRICHED_SYSTEM,
        user_content=RESUME_IMPROVE_ENRICHED_USER.format(
            resume_text=resume_text,
            enrichment_json=enrichment_json,
        ),
        purpose="resume improve (enriched)",
    )

    logger.info("Resume improved with enrichment: %d chars", len(text))
    return text.strip()
