"""Shared utilities for CLI commands."""

import json
import logging
import os
import re
import sys

import anthropic
import click

from src.config import MODEL, MAX_TOKENS_VALIDATE, OLLAMA_BASE_URL
from src.llm_client import list_ollama_models
from src.models import ResumeContent, ResumeReview


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_mock_fixture(name: str) -> dict:
    """Load a mock JSON fixture from tests/fixtures/ for --dry-run mode."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures")
    path = os.path.join(fixtures_dir, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_api_key() -> None:
    """Make a minimal API call to verify the key works. Exits on failure."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        click.echo(
            "Error: ANTHROPIC_API_KEY environment variable is not set.\n"
            "Set it with: export ANTHROPIC_API_KEY='your-key-here'"
        )
        sys.exit(1)

    click.echo("Validating API key...", nl=False)
    try:
        client = anthropic.Anthropic()
        client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_VALIDATE,
            messages=[{"role": "user", "content": "hi"}],
        )
        click.echo(" OK")
    except anthropic.AuthenticationError:
        click.echo(" FAILED")
        click.echo(
            "\nError: Invalid API key. Check your ANTHROPIC_API_KEY.\n"
            "Get a valid key at: https://console.anthropic.com/settings/keys"
        )
        sys.exit(1)
    except anthropic.APIConnectionError as e:
        click.echo(" FAILED")
        click.echo(f"\nError: Could not connect to the Anthropic API.\n{e}")
        sys.exit(1)
    except Exception as e:
        click.echo(" FAILED")
        click.echo(f"\nError validating API key: {e}")
        sys.exit(1)


def summarize_resume(text: str) -> dict:
    """Extract a quick summary from resume text for confirmation."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    word_count = len(text.split())

    # Guess name from first non-empty line
    detected_name = lines[0] if lines else None

    # Count roles: look for lines with date-like patterns (2019, 2020-2023, etc.)
    date_pattern = re.compile(r"\b(19|20)\d{2}\b")
    role_lines = [line for line in lines if date_pattern.search(line)]
    role_count = len(role_lines)

    return {
        "word_count": word_count,
        "detected_name": detected_name,
        "role_count": role_count,
    }


def summarize_jd(text: str) -> dict:
    """Extract a quick summary from JD text for confirmation."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    word_count = len(text.split())

    # Try to detect role title from early lines
    detected_title = None
    for line in lines[:5]:
        # Skip very short or very long lines, look for title-like ones
        if 3 <= len(line.split()) <= 12:
            detected_title = line
            break

    # Try to detect company name — look for "at <Company>" or "<Company> is"
    detected_company = None
    full = " ".join(lines[:10])
    at_match = re.search(r"\bat\s+([A-Z][A-Za-z0-9 &.,]+)", full)
    if at_match:
        detected_company = at_match.group(1).strip().rstrip(".,")

    return {
        "word_count": word_count,
        "detected_title": detected_title,
        "detected_company": detected_company,
    }


def capture_writing_preference(
    prof, feedback: str, pname: str
) -> None:
    """Extract and save writing preferences from user feedback."""
    from src.profile import save_profile

    # Common patterns to detect
    pref_patterns = {
        "bullet_length": ["shorter", "longer", "concise", "brief", "detailed"],
        "tone": ["formal", "casual", "conversational", "professional", "technical"],
        "verb_avoidance": ["spearheaded", "leveraged", "synergized", "utilized"],
    }
    feedback_lower = feedback.lower()

    for category, keywords in pref_patterns.items():
        for kw in keywords:
            if kw in feedback_lower:
                prof.writing_preferences[category] = feedback
                save_profile(prof, pname)
                click.echo(
                    click.style("    Noted: saved as writing preference.", fg="green")
                )
                return

    # If no pattern matched, save as general preference
    prof.writing_preferences["general"] = feedback
    save_profile(prof, pname)
    click.echo(click.style("    Noted: saved as writing preference.", fg="green"))


def fill_placeholders_in_text(
    text: str,
    show_context: bool = True,
    placeholder_descriptions: dict[str, str] | None = None,
    skipped_out: list[str] | None = None,
) -> str:
    """Find [X%], [number], etc. placeholders in text and prompt user to fill them.

    Returns the text with placeholders replaced by user-provided values.
    When the user types 'skip', the entire metric clause is removed rather
    than inserting a vague word.  If *skipped_out* is provided, appended with
    the description (or placeholder token) of every skipped placeholder so
    callers can track what the user declined.
    """
    import re as _re
    from src.resume_reviewer import _remove_placeholder_clause

    placeholder_re = _re.compile(r"\[([^\]]*(?:X|Y|number|N)[^\]]*)\]", _re.IGNORECASE)
    if not placeholder_re.search(text):
        return text

    descriptions = placeholder_descriptions or {}

    # Re-search for each placeholder fresh to avoid stale indices after text modifications
    while True:
        match = placeholder_re.search(text)
        if not match:
            break

        placeholder = match.group(0)  # e.g. "[X%]"
        inner = match.group(1)  # e.g. "X%"

        # Look up the description for this placeholder
        description = descriptions.get(placeholder, "")

        if description:
            prompt_msg = f"  → {description} (enter a number, or 'skip')"
        else:
            # Fallback: derive context from the full line containing the placeholder
            if show_context:
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                if line_end == -1:
                    line_end = len(text)
                line_context = text[line_start:line_end].strip()
                # Truncate if very long
                if len(line_context) > 100:
                    # Show portion around the placeholder
                    rel_start = match.start() - line_start
                    ctx_start = max(0, rel_start - 40)
                    ctx_end = min(len(line_context), rel_start + len(placeholder) + 40)
                    line_context = line_context[ctx_start:ctx_end].strip()
                context_label = line_context if line_context else placeholder
            else:
                context_label = placeholder
            prompt_msg = f"  {context_label}\n    → (enter a number, or 'skip')"

        value = click.prompt(
            prompt_msg,
            default="skip",
            show_default=False,
        ).strip()
        if value.lower() == "skip":
            text = _remove_placeholder_clause(text, match.start(), match.end())
            if skipped_out is not None:
                skipped_out.append(description or placeholder)
        else:
            # Strip trailing % to avoid double "%%"
            value = value.rstrip("%")
            # Replace placeholder with the user's value, keeping any suffix
            # e.g. [X%] -> 99% if user types "99"
            suffix = ""
            if "%" in inner:
                suffix = "%"
            text = text[: match.start()] + value + suffix + text[match.end() :]

    return text


def fill_review_placeholders(review: ResumeReview) -> ResumeReview:
    """Prompt user to fill placeholder metrics in review improved_bullets.

    Tracks which placeholders the user skipped so the improve prompt can
    instruct Claude not to re-add them.
    """
    has_any = any(b.has_placeholders for b in review.improved_bullets)
    if not has_any:
        return review

    click.echo(
        click.style(
            "\nSome improved bullets have placeholder metrics. "
            "Please fill in real numbers or type 'skip' to drop the metric.",
            fg="yellow",
            bold=True,
        )
    )
    for b in review.improved_bullets:
        if not b.has_placeholders:
            continue
        click.echo(f'\n  Bullet: "{b.improved}"')
        skipped: list[str] = []
        b.improved = fill_placeholders_in_text(
            b.improved,
            placeholder_descriptions=b.placeholder_descriptions,
            skipped_out=skipped,
        )
        b.has_placeholders = False
        b.skipped_placeholders = skipped

    return review


def fill_generation_placeholders(resume_data: ResumeContent) -> ResumeContent:
    """Prompt user to fill placeholder metrics in generated resume bullets."""
    has_any = any(exp.placeholder_bullets for exp in resume_data.experience)
    if not has_any:
        return resume_data

    click.echo(
        click.style(
            "\nSome resume bullets have placeholder metrics. "
            "Please fill in real numbers or type 'skip' to drop the metric.",
            fg="yellow",
            bold=True,
        )
    )
    for exp in resume_data.experience:
        if not exp.placeholder_bullets:
            continue
        click.echo(
            click.style(
                f"\n  [{exp.company} — {exp.title}]",
                bold=True,
            )
        )
        for idx in exp.placeholder_bullets:
            if idx < len(exp.bullets):
                bullet = exp.bullets[idx]
                click.echo(f'\n  Bullet: "{bullet}"')
                exp.bullets[idx] = fill_placeholders_in_text(
                    bullet,
                    placeholder_descriptions=exp.placeholder_descriptions,
                )
        exp.placeholder_bullets = []

    return resume_data


def select_model_interactive(profile_prefs: dict) -> str:
    """Show an interactive menu for model selection.

    Auto-detects available backends (Claude API key, Ollama) and presents
    numbered options. Returns the model string (e.g. 'claude', 'ollama:qwen3.5').
    """
    options: list[dict] = []

    # Check for saved preference
    saved_model = profile_prefs.get("model")

    # Check Claude availability
    has_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if has_claude:
        options.append({
            "value": "claude",
            "label": "Claude (Anthropic API)",
            "detail": "Best quality, paid API, fastest",
        })

    # Check Ollama availability
    ollama_models = list_ollama_models(OLLAMA_BASE_URL)
    for m in ollama_models:
        name = m["name"]
        size = m["size_gb"]
        size_str = f"{size}GB" if size else "unknown size"
        options.append({
            "value": f"ollama:{name}",
            "label": f"Ollama: {name}",
            "detail": f"Local, free, {size_str}",
        })

    if not options:
        click.echo(
            "Error: No AI models available.\n"
            "  - Set ANTHROPIC_API_KEY for Claude API, or\n"
            "  - Start Ollama with: ollama serve"
        )
        sys.exit(1)

    # If only one option, use it automatically
    if len(options) == 1:
        choice = options[0]["value"]
        click.echo(f"Using {options[0]['label']} (only available backend)")
        return choice

    # Show menu
    click.echo("\n--- Select AI Model ---\n")

    # Mark the saved default
    default_idx = 1
    for i, opt in enumerate(options, 1):
        marker = ""
        if opt["value"] == saved_model:
            marker = " (saved default)"
            default_idx = i
        click.echo(f"  {i}. {opt['label']}{marker}")
        click.echo(f"     {opt['detail']}")

    click.echo("")
    choice_str = click.prompt(
        "Choose a model",
        default=str(default_idx),
        show_default=True,
    ).strip()

    try:
        idx = int(choice_str) - 1
        if idx < 0 or idx >= len(options):
            raise ValueError()
    except ValueError:
        click.echo("Invalid selection. Using default.")
        idx = default_idx - 1

    selected = options[idx]["value"]
    click.echo(f"Selected: {options[idx]['label']}\n")
    return selected


# ---------------------------------------------------------------------------
# Backward-compatible aliases (underscore-prefixed names used by other modules)
# ---------------------------------------------------------------------------
_setup_logging = setup_logging
_load_mock_fixture = load_mock_fixture
_summarize_resume = summarize_resume
_summarize_jd = summarize_jd
_capture_writing_preference = capture_writing_preference
_fill_placeholders_in_text = fill_placeholders_in_text
_fill_review_placeholders = fill_review_placeholders
_fill_generation_placeholders = fill_generation_placeholders
