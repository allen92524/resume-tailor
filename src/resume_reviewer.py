"""Review and improve resumes using the Claude API."""

import json
import logging
import re

import click

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_REVIEW, MAX_TOKENS_IMPROVE
from .llm_client import call_llm, normalize_response
from .models import ResumeReview
from .prompts import (
    RESUME_REVIEW_SYSTEM,
    RESUME_REVIEW_USER,
    RESUME_IMPROVE_SYSTEM,
    RESUME_IMPROVE_USER,
)

logger = logging.getLogger(__name__)

# Matches placeholder brackets like [X%], [Y%], [number], [N], [X], etc.
PLACEHOLDER_RE = re.compile(r"\[([^\]]*(?:X|Y|N|number)[^\]]*)\]", re.IGNORECASE)


def review_resume(resume_text: str, model: str = DEFAULT_MODEL) -> ResumeReview:
    """Send resume to Claude for quality review.

    Returns a ResumeReview with overall_score, strengths, weaknesses,
    missing_keywords, and improved_bullets.
    """
    logger.info("Reviewing resume (%d chars)", len(resume_text))

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_REVIEW,
        system=RESUME_REVIEW_SYSTEM,
        user_content=RESUME_REVIEW_USER.format(resume_text=resume_text),
    )

    try:
        data = parse_json_response(response_text)
    except Exception:
        logger.warning(
            "Failed to parse resume review response. Raw LLM output:\n%s", response_text
        )
        raise
    data = normalize_response(data, schema="resume_review")
    result = ResumeReview.from_dict(data)
    logger.info("Review complete: score=%d/100", result.overall_score)
    return result


def improve_resume(
    resume_text: str,
    review: ResumeReview,
    skipped_placeholders: list[str] | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Send resume + review to Claude to get an improved version.

    Returns the improved resume as plain text.  *skipped_placeholders* lists
    descriptions of metrics the user explicitly declined; the prompt tells
    Claude not to re-add placeholders for those.
    """
    logger.info("Improving resume based on review")

    prompt = RESUME_IMPROVE_USER.format(
        resume_text=resume_text,
        review_json=json.dumps(review.to_dict(), indent=2),
    )

    if skipped_placeholders:
        skip_list = "\n".join(f"- {desc}" for desc in skipped_placeholders)
        prompt += (
            "\n\nSKIPPED METRICS — the user explicitly declined these placeholders. "
            "Do NOT add placeholder brackets or metrics for any of the following. "
            "Write clean sentences with no metric at all for these:\n" + skip_list
        )

    text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_IMPROVE,
        system=RESUME_IMPROVE_SYSTEM,
        user_content=prompt,
    )

    logger.info("Resume improved: %d chars", len(text))
    return text.strip()


def _remove_placeholder_clause(text: str, start: int, end: int) -> str:
    """Remove a placeholder and its surrounding metric clause from text.

    Removes the placeholder at text[start:end] along with preceding prepositions
    (e.g. 'by', 'to') and following metric descriptors (e.g. 'reduction', 'more').
    Cleans up punctuation artifacts locally around the removal site.
    """
    before = text[:start]
    after = text[end:]

    # Remove preceding preposition ("by ", "to ", "from ", "of ", "up to ")
    before = re.sub(r"\s+(?:by|to|from|of|up to)\s*$", "", before)

    # Remove following metric descriptors
    after = re.sub(
        r"^\s*(?:reduction|improvement|increase|decrease|faster|slower"
        r"|more efficiently|more quickly|more)\b\s*",
        " ",
        after,
    )

    text = before + after
    # Clean up double spaces, orphaned commas, comma-before-period
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\s+\.", ".", text)
    return text.strip()


def resolve_resume_placeholders(text: str) -> str:
    """Scan resume text for placeholder brackets and prompt the user to resolve each.

    Finds patterns like [X%], [number], [Y%], [X], etc. For each one, prompts
    the user to enter a real value or type 'skip' to remove the metric clause.
    Returns the text with all placeholders resolved.
    """
    matches = list(PLACEHOLDER_RE.finditer(text))
    if not matches:
        return text

    click.echo(
        click.style(
            "\nThe improved resume contains placeholder metrics that need to be filled in.",
            fg="yellow",
            bold=True,
        )
    )

    # Show all lines containing placeholders for context
    click.echo("\nPlaceholders found:")
    seen_lines: set[str] = set()
    for match in matches:
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end].strip()
        if line not in seen_lines:
            click.echo(f"  {line}")
            seen_lines.add(line)

    click.echo("")

    # Re-search for each placeholder fresh to avoid stale indices after text modifications
    while True:
        match = PLACEHOLDER_RE.search(text)
        if not match:
            break

        placeholder = match.group(0)  # e.g. "[X%]"
        inner = match.group(1)  # e.g. "X%"

        # Show a snippet after the placeholder for context
        after_snippet = text[match.end() : match.end() + 40].strip().split("\n")[0]
        if len(after_snippet) > 30:
            after_snippet = after_snippet[:30].rsplit(" ", 1)[0]
        context_label = (
            f"{placeholder} {after_snippet}" if after_snippet else placeholder
        )

        value = click.prompt(
            f"  {context_label} → (enter a value, or 'skip')",
            default="skip",
            show_default=False,
        ).strip()

        if value.lower() == "skip":
            text = _remove_placeholder_clause(text, match.start(), match.end())
        else:
            # Strip trailing % to avoid double "%%"
            value = value.rstrip("%")
            suffix = "%" if "%" in inner else ""
            text = text[: match.start()] + value + suffix + text[match.end() :]

    return text


def display_review(review: ResumeReview) -> None:
    """Display the resume review as a formatted terminal report."""
    score = review.overall_score

    # Score bar
    filled = score // 5
    bar = "\u2588" * filled + "\u2591" * (20 - filled)

    click.echo("\n" + "=" * 50)
    click.echo("  Resume Review")
    click.echo("=" * 50)

    # Color the score
    if score >= 80:
        color = "green"
    elif score >= 60:
        color = "yellow"
    elif score >= 40:
        color = "red"
    else:
        color = "bright_red"
    click.echo(
        f"\n  Overall Score: [{bar}] "
        f"{click.style(f'{score}/100', fg=color, bold=True)}"
    )

    # Strengths
    if review.strengths:
        click.echo(click.style("\n  Strengths:", fg="green", bold=True))
        for item in review.strengths:
            click.echo(f"    + {item}")

    # Weaknesses
    if review.weaknesses:
        click.echo(click.style("\n  Areas for Improvement:", fg="yellow", bold=True))
        for w in review.weaknesses:
            click.echo(f"    [{w.section}]")
            click.echo(f"      Issue: {w.issue}")
            click.echo(f"      Fix:   {w.suggestion}")

    # Missing keywords
    if review.missing_keywords:
        click.echo(click.style("\n  Missing Keywords:", fg="red", bold=True))
        click.echo(f"    {', '.join(review.missing_keywords)}")

    # Improved bullets
    if review.improved_bullets:
        click.echo(
            click.style("\n  Suggested Bullet Improvements:", fg="cyan", bold=True)
        )
        for b in review.improved_bullets:
            click.echo(f"    Before: {b.original}")
            improved = b.improved
            if b.has_placeholders:
                improved = click.style(improved, fg="yellow")
            click.echo(f"    After:  {improved}")
            if b.has_placeholders:
                click.echo(
                    click.style("    ^ Contains placeholder metrics", fg="yellow")
                )
            click.echo("")

    click.echo("")
