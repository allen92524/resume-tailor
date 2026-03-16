"""Analyze job descriptions using the Claude API."""

import logging

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_JD_ANALYSIS
from .llm_client import call_llm, normalize_response
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
        purpose="JD analysis",
    )

    try:
        data = parse_json_response(response_text)
    except Exception:
        logger.warning("Failed to parse JD analysis response. Raw LLM output:\n%s", response_text)
        raise
    data = normalize_response(data, schema="jd_analysis")
    result = JDAnalysis.from_dict(data)
    logger.info(
        "JD analysis complete: role=%s, company=%s", result.job_title, result.company
    )
    return result


def collect_jd_text(model: str = DEFAULT_MODEL) -> str:
    """Interactively collect job description text from the user.

    Accepts a URL, file path, or pasted text (end with END on its own line).
    If a URL is provided, fetches the page via MCP and extracts the JD using LLM.
    """
    from .resume_parser import _looks_like_file_path, read_resume_from_file

    logger.info("Collecting job description text from user")
    print("\nProvide the job description: paste a URL, file path, or content below.")
    print("Supported: URLs (https://...), file formats (.txt, .md, .docx, .pdf)")
    print("When pasting text, type END on its own line to finish.\n")

    while True:
        lines: list[str] = []
        try:
            first_line = input()
        except EOFError:
            return ""

        # Check if input is a URL
        first_stripped = first_line.strip()
        if _is_url(first_stripped):
            result = _fetch_jd_from_url(first_stripped, model)
            if result:
                return result
            print("Please try again with a different URL, file path, or paste the text.\n")
            continue

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


def _is_url(text: str) -> bool:
    """Check if text looks like a URL."""
    return text.startswith(("http://", "https://", "www."))


def _fetch_jd_from_url(url: str, model: str = DEFAULT_MODEL) -> str | None:
    """Fetch a job posting URL and extract the job description.

    Uses MCP fetch server to get the page, then LLM to extract the JD.
    Returns the extracted JD text, or None if it fails.
    """
    import click

    from .llm_client import call_llm
    from .prompts import EXTRACT_JD_SYSTEM, EXTRACT_JD_USER

    click.echo("Fetching job posting from URL...")
    try:
        from .mcp_client import fetch_url

        page_content = fetch_url(url)
    except Exception as e:
        logger.warning("Failed to fetch URL %s: %s", url, e)
        click.echo(f"Could not fetch URL: {e}")
        click.echo("Please paste the job description manually instead.")
        return None

    if not page_content or len(page_content.strip()) < 100:
        click.echo(
            "The page returned very little content (may require JavaScript). "
            "Please paste the job description manually instead."
        )
        return None

    click.echo(f"Page fetched ({len(page_content)} chars). Extracting job description...")
    try:
        jd_text = call_llm(
            model=model,
            max_tokens=4096,
            system=EXTRACT_JD_SYSTEM,
            user_content=EXTRACT_JD_USER.format(page_content=page_content),
            purpose="JD extraction from URL",
        )
    except Exception as e:
        logger.warning("Failed to extract JD from page content: %s", e)
        click.echo(f"Could not extract JD from page: {e}")
        return None

    if not jd_text or len(jd_text.strip()) < 50:
        click.echo("Could not find a job description on this page.")
        return None

    jd_text = jd_text.strip()
    click.echo(f"\nExtracted job description ({len(jd_text.split())} words):")
    # Show preview
    preview = jd_text[:500] + ("..." if len(jd_text) > 500 else "")
    click.echo(preview)

    if click.confirm("\nUse this job description?", default=True):
        return jd_text

    click.echo("Discarded. Please paste the job description manually.")
    return None
