"""CLI entry point for resume-tailor."""

import json
import logging
import os
import re
import sys

import anthropic
import click

# Allow running as `python src/main.py` from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import (
    MODEL,
    DEFAULT_MODEL,
    MAX_TOKENS_VALIDATE,
    MAX_GAP_QUESTIONS,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_PROFILE,
    get_profile_path,
)
from src.llm_client import (
    is_ollama_model,
    get_ollama_model_name,
    prepare_ollama,
    list_ollama_models,
)
from src.models import (
    ResumeContent,
    JDAnalysis,
    GapAnalysis,
    CompatibilityAssessment,
    ResumeReview,
    ReviewWeakness,
)
from src.resume_parser import collect_resume_text, validate_resume_content
from src.jd_analyzer import analyze_jd, collect_jd_text
from src.gap_analyzer import analyze_gaps
from src.compatibility_assessor import assess_compatibility, display_assessment
from src.resume_generator import generate_tailored_resume
from src.docx_builder import build_resume, open_file
from src.session import save_session, load_session
from src.resume_reviewer import (
    review_resume,
    improve_resume,
    display_review,
    resolve_resume_placeholders,
)
from src.profile import (
    load_profile,
    save_profile,
    first_run_setup,
    lookup_experience,
    save_experience,
    append_history,
    save_preferences,
    get_preferences,
    delete_profile,
    open_in_editor,
    export_as_markdown,
    backup_profile,
    list_backups,
    restore_profile,
)

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_mock_fixture(name: str) -> dict:
    """Load a mock JSON fixture from tests/fixtures/ for --dry-run mode."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
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


def _summarize_resume(text: str) -> dict:
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


def _summarize_jd(text: str) -> dict:
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


def _fill_placeholders_in_text(
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


def _fill_review_placeholders(review: ResumeReview) -> ResumeReview:
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
        b.improved = _fill_placeholders_in_text(
            b.improved,
            placeholder_descriptions=b.placeholder_descriptions,
            skipped_out=skipped,
        )
        b.has_placeholders = False
        b.skipped_placeholders = skipped

    return review


def _fill_generation_placeholders(resume_data: ResumeContent) -> ResumeContent:
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
                exp.bullets[idx] = _fill_placeholders_in_text(
                    bullet,
                    placeholder_descriptions=exp.placeholder_descriptions,
                )
        exp.placeholder_bullets = []

    return resume_data


@click.group()
@click.option("--verbose", is_flag=True, default=False, help="Enable debug logging.")
@click.option(
    "--profile",
    "profile_name",
    default=DEFAULT_PROFILE,
    show_default=True,
    help="Profile name. Each profile stores its own resume, history, and preferences.",
)
@click.pass_context
def cli(ctx, verbose, profile_name):
    """Resume Tailor - AI-powered resume generator."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["profile_name"] = profile_name
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# Profile commands
# ---------------------------------------------------------------------------


@cli.group()
def profile():
    """Manage your resume-tailor profile."""
    pass


@profile.command("view")
@click.pass_context
def profile_view(ctx):
    """Show full profile summary."""
    pname = ctx.obj["profile_name"]
    prof = load_profile(pname)
    if not prof:
        click.echo("No profile found. Run `python src/main.py generate` to create one.")
        return

    identity = prof.identity
    click.echo("\n" + "=" * 50)
    click.echo(f"  Profile: {identity.name or 'Unknown'}")
    if pname != DEFAULT_PROFILE:
        click.echo(f"  (profile: {pname})")
    click.echo("=" * 50)

    # Contact info
    for field in ("email", "phone", "location", "linkedin", "github"):
        value = getattr(identity, field)
        if value:
            click.echo(f"  {field.capitalize():10s} {value}")

    # Resume stats
    if prof.base_resume:
        word_count = len(prof.base_resume.split())
        click.echo(f"\n  Base resume: {word_count} words")
    if prof.original_resume:
        orig_words = len(prof.original_resume.split())
        click.echo(f"  Original resume: {orig_words} words (never modified)")
    if prof.applications_since_review:
        click.echo(f"  Applications since last review: {prof.applications_since_review}")

    # Writing preferences
    if prof.writing_preferences:
        click.echo("\n  Writing preferences:")
        for key, value in prof.writing_preferences.items():
            click.echo(f"    - {key}: {value}")

    # Experience bank
    if prof.experience_bank:
        click.echo(f"\n  Experience bank: {len(prof.experience_bank)} saved answers")
        for skill, answer in prof.experience_bank.items():
            preview = answer[:60] + "..." if len(answer) > 60 else answer
            click.echo(f"    - {skill}: {preview}")

    # History
    if prof.history:
        click.echo(f"\n  Application history: {len(prof.history)} entries")
        for entry in prof.history[-5:]:  # show last 5
            date = entry.get("date", "")[:10]
            company = entry.get("company") or "N/A"
            role = entry.get("role") or "N/A"
            score = entry.get("match_score")
            score_str = f"{score}%" if score is not None else "N/A"
            click.echo(f"    {date}  {company} - {role} ({score_str})")
        if len(prof.history) > 5:
            click.echo(f"    ... and {len(prof.history) - 5} more")

    # Preferences
    if prof.preferences:
        click.echo("\n  Preferences:")
        if prof.preferences.get("format"):
            click.echo(f"    Default format: {prof.preferences['format']}")
        if prof.preferences.get("output_path"):
            click.echo(f"    Default output: {prof.preferences['output_path']}")

    click.echo("")


@profile.command("update")
@click.pass_context
def profile_update(ctx):
    """Interactively update identity fields (name, email, phone, etc.)."""
    pname = ctx.obj["profile_name"]
    prof = load_profile(pname)
    if not prof:
        click.echo("No profile found. Run `python src/main.py generate` to create one.")
        return

    identity = prof.identity
    fields = ["name", "email", "phone", "location", "linkedin", "github"]
    changed = False

    click.echo("\nUpdate your profile. Press Enter to keep the current value.\n")
    for field in fields:
        current = getattr(identity, field) or ""
        display = current if current else "(not set)"
        new_value = click.prompt(
            f"  {field.capitalize()} [{display}]",
            default="",
            show_default=False,
        )
        if new_value.strip():
            setattr(identity, field, new_value.strip())
            changed = True

    if changed:
        save_profile(prof, pname)
        click.echo("\nProfile updated.")
    else:
        click.echo("\nNo changes made.")


@profile.command("reset")
@click.pass_context
def profile_reset(ctx):
    """Delete profile and start over."""
    pname = ctx.obj["profile_name"]
    prof = load_profile(pname)
    if not prof:
        click.echo("No profile found. Nothing to reset.")
        return

    name = prof.identity.name or "Unknown"
    history_count = len(prof.history)
    bank_count = len(prof.experience_bank)

    click.echo(f"\nThis will delete your profile for {name}.")
    click.echo(f"  {bank_count} saved experience answers will be lost.")
    click.echo(f"  {history_count} application history entries will be lost.")

    if click.confirm("\nAre you sure?", default=False):
        delete_profile(pname)
        click.echo("Profile deleted.")
    else:
        click.echo("Cancelled.")


@profile.command("reset-baseline")
@click.pass_context
def profile_reset_baseline(ctx):
    """Revert base_resume back to the original unmodified resume."""
    pname = ctx.obj["profile_name"]
    prof = load_profile(pname)
    if not prof:
        click.echo("No profile found. Run `python src/main.py generate` to create one.")
        return

    if not prof.original_resume:
        click.echo("No original resume stored. Cannot reset baseline.")
        return

    if prof.base_resume == prof.original_resume:
        click.echo("Base resume is already the same as the original. Nothing to reset.")
        return

    base_words = len(prof.base_resume.split())
    orig_words = len(prof.original_resume.split())
    click.echo(f"\nCurrent base resume: {base_words} words (improved)")
    click.echo(f"Original resume:     {orig_words} words (unmodified)")

    if click.confirm(
        "Revert base resume to the original? All improvements will be lost", default=False
    ):
        prof.base_resume = prof.original_resume
        prof.applications_since_review = 0
        save_profile(prof, pname)
        click.echo("Base resume reset to original.")
    else:
        click.echo("Cancelled.")


@profile.command("edit")
@click.pass_context
def profile_edit(ctx):
    """Open profile.json in the default editor."""
    pname = ctx.obj["profile_name"]
    path = get_profile_path(pname)
    if not os.path.isfile(path):
        click.echo("No profile found. Run `python src/main.py generate` to create one.")
        return

    click.echo(f"Opening {path}...")
    open_in_editor(path)


@profile.command("export")
@click.pass_context
def profile_export(ctx):
    """Export profile as formatted markdown."""
    pname = ctx.obj["profile_name"]
    prof = load_profile(pname)
    if not prof:
        click.echo("No profile found. Run `python src/main.py generate` to create one.")
        return

    md = export_as_markdown(prof)
    click.echo(md)


@profile.command("backup")
@click.pass_context
def profile_backup(ctx):
    """Create a timestamped backup of your profile."""
    pname = ctx.obj["profile_name"]
    backup_path = backup_profile(pname)
    if not backup_path:
        click.echo("No profile found. Nothing to back up.")
        return
    click.echo(f"Profile backed up to {backup_path}")


@profile.command("restore")
@click.pass_context
def profile_restore(ctx):
    """Restore profile from a backup."""
    pname = ctx.obj["profile_name"]
    backups = list_backups(pname)
    if not backups:
        click.echo("No backups found.")
        return

    click.echo("\nAvailable backups:\n")
    for i, path in enumerate(backups, 1):
        filename = os.path.basename(path)
        size = os.path.getsize(path)
        click.echo(f"  {i}. {filename} ({size:,} bytes)")

    choice = click.prompt(
        "\nEnter backup number to restore (or 'q' to cancel)",
        default="q",
        show_default=False,
    ).strip()

    if choice.lower() == "q":
        click.echo("Cancelled.")
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(backups):
            raise ValueError()
    except ValueError:
        click.echo("Invalid selection.")
        return

    selected = backups[idx]
    filename = os.path.basename(selected)

    if not click.confirm(
        f"Restore from {filename}? This will overwrite your current profile"
    ):
        click.echo("Cancelled.")
        return

    restore_profile(selected, pname)
    click.echo(f"Profile restored from {filename}.")


# ---------------------------------------------------------------------------
# Review command
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--model",
    default=None,
    help="LLM model to use. 'claude' for Anthropic API, or 'ollama:<name>' for local Ollama.",
)
@click.pass_context
def review(ctx, model):
    """Review your base resume for quality and get improvement suggestions."""
    pname = ctx.obj["profile_name"]

    prof = load_profile(pname)
    if not prof:
        click.echo("No profile found. Run `python src/main.py generate` to create one.")
        sys.exit(1)

    # Model selection: interactive menu if --model not provided
    if model is None:
        prefs = get_preferences(prof)
        model = select_model_interactive(prefs)

        if prefs.get("model") != model:
            prof.preferences["model"] = model
            save_profile(prof, pname)

    if is_ollama_model(model):
        click.echo(f"Using local Ollama model: {get_ollama_model_name(model)}")
        try:
            prepare_ollama(model)
        except (ConnectionError, RuntimeError) as e:
            click.echo(f"Error: {e}")
            sys.exit(1)
    else:
        validate_api_key()

    if not prof.base_resume:
        click.echo("Error: No base resume in your profile.")
        sys.exit(1)

    click.echo("Reviewing your resume...")
    try:
        review_result = review_resume(prof.base_resume, model=model)
    except Exception as e:
        logger.error("Resume review failed: %s", e)
        click.echo(f"Error reviewing resume: {e}")
        sys.exit(1)

    display_review(review_result)

    # Walk through each weakness with targeted questions
    from src.profile import _ask_weakness_questions

    answers, all_skipped = _ask_weakness_questions(review_result)

    if answers:
        answer_context = "\n".join(
            f"- {issue}: {answer}" for issue, answer in answers.items()
        )
        review_result.weaknesses.append(
            ReviewWeakness(
                section="User Provided",
                issue="Additional context from user",
                suggestion=f"Incorporate these details:\n{answer_context}",
            )
        )

        click.echo("Improving your resume with your answers...")
        try:
            improved = improve_resume(
                prof.base_resume,
                review_result,
                skipped_placeholders=all_skipped or None,
                model=model,
            )
        except Exception as e:
            logger.error("Resume improvement failed: %s", e)
            click.echo(f"Error improving resume: {e}")
            sys.exit(1)

        improved = resolve_resume_placeholders(improved)

        click.echo("\nImproved resume preview:")
        click.echo(improved[:500] + ("..." if len(improved) > 500 else ""))
        if click.confirm("Save this improved version?", default=True):
            prof.base_resume = improved
            prof.applications_since_review = 0
            save_profile(prof, pname)
            click.echo("Base resume updated and saved.")

            # Save answers to experience bank
            for issue, answer in answers.items():
                save_experience(prof, issue, answer, pname)
        else:
            click.echo("Keeping existing resume.")


# ---------------------------------------------------------------------------
# Interactive model selection
# ---------------------------------------------------------------------------


def select_model_interactive(profile_prefs: dict) -> str:
    """Show an interactive menu for model selection.

    Auto-detects available backends (Claude API key, Ollama) and presents
    numbered options. Returns the model string (e.g. 'claude', 'ollama:qwen3.5').
    """
    from src.config import OLLAMA_BASE_URL

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
# Generate command
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["docx", "pdf", "md", "all"], case_sensitive=False),
    default=None,
    help="Output format (default: docx, or saved preference).",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    default=None,
    help="Output file or directory path (default: output/ folder, or saved preference).",
)
@click.option(
    "--skip-questions",
    is_flag=True,
    default=False,
    help="Skip follow-up questions for a quick run.",
)
@click.option(
    "--skip-assessment",
    is_flag=True,
    default=False,
    help="Skip the compatibility assessment step.",
)
@click.option(
    "--reference",
    "reference_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to a reference resume from someone in a similar role.",
)
@click.option(
    "--resume-session",
    is_flag=True,
    default=False,
    help="Reload resume and JD from the last saved session.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Use mock API responses instead of calling Claude. For testing without spending credits.",
)
@click.option(
    "--model",
    default=None,
    help="LLM model to use. 'claude' for Anthropic API, or 'ollama:<name>' for local Ollama.",
)
@click.pass_context
def generate(
    ctx,
    output_format: str | None,
    output_path: str | None,
    skip_questions: bool,
    skip_assessment: bool,
    reference_path: str | None,
    resume_session: bool,
    dry_run: bool,
    model: str | None,
):
    """Generate a tailored resume from your resume and a job description."""
    pname = ctx.obj["profile_name"]

    # Step 1: Model selection — first thing, before any LLM calls
    if dry_run:
        model = model or DEFAULT_MODEL
        click.echo(
            click.style("[DRY RUN] Using mock API responses.", fg="yellow", bold=True)
        )
    elif model is None:
        # Load profile only to check saved model preference (no LLM calls)
        existing_prof = load_profile(pname)
        prefs = get_preferences(existing_prof) if existing_prof else {}
        model = select_model_interactive(prefs)

    # Validate/prepare the chosen backend before any LLM calls
    if not dry_run:
        if is_ollama_model(model):
            click.echo(f"Using local Ollama model: {get_ollama_model_name(model)}")
            try:
                prepare_ollama(model)
            except (ConnectionError, RuntimeError) as e:
                click.echo(f"Error: {e}")
                sys.exit(1)
        else:
            validate_api_key()

    # Load or create profile (now uses the selected model for any LLM calls)
    prof = load_profile(pname)
    if not prof:
        prof = first_run_setup(pname, model=model)

    # Save model preference if different from what's stored
    if not dry_run:
        prefs = get_preferences(prof)
        if prefs.get("model") != model:
            prof.preferences["model"] = model
            save_profile(prof, pname)

    # Apply saved preferences as defaults (flags override)
    prefs = get_preferences(prof)
    if output_format is None:
        output_format = prefs.get("format", DEFAULT_OUTPUT_FORMAT)
    if output_path is None:
        output_path = prefs.get("output_path")

    # Periodic baseline review prompt for returning users
    if (
        not dry_run
        and prof.base_resume
        and prof.applications_since_review >= 10
    ):
        click.echo(
            click.style(
                f"\nYou've generated {prof.applications_since_review} resumes since "
                "your last baseline review.",
                fg="yellow",
                bold=True,
            )
        )
        if click.confirm("Want to review your baseline resume?", default=False):
            click.echo("Reviewing your baseline resume...")
            try:
                review_result = review_resume(prof.base_resume, model=model)
                display_review(review_result)
                review_result = _fill_review_placeholders(review_result)

                if click.confirm(
                    "Incorporate these suggestions?", default=False
                ):
                    all_skipped: list[str] = []
                    for b in review_result.improved_bullets:
                        all_skipped.extend(b.skipped_placeholders)

                    click.echo("Improving your resume...")
                    improved = improve_resume(
                        prof.base_resume,
                        review_result,
                        skipped_placeholders=all_skipped or None,
                        model=model,
                    )
                    improved = resolve_resume_placeholders(improved)
                    prof.base_resume = improved
                    prof.applications_since_review = 0
                    save_profile(prof, pname)
                    click.echo("Base resume updated.")
                else:
                    # Reset counter even if they decline
                    prof.applications_since_review = 0
                    save_profile(prof, pname)
            except Exception as e:
                logger.warning("Baseline review failed: %s", e)
                click.echo(f"Warning: Review failed ({e}). Continuing.")

    click.echo("\n" + "=" * 50)
    click.echo("  Resume Tailor - AI-Powered Resume Generator")
    click.echo("=" * 50)

    # Use profile resume if available
    identity = prof.identity
    profile_name = identity.name
    has_profile_resume = bool(prof.base_resume)

    # Track optional reference resume
    reference_text = None

    # Try to restore from session
    session = None
    if resume_session:
        session = load_session(pname)
        if session:
            resume_text = session["resume_text"]
            jd_text = session["jd_text"]
            saved_at = session.get("saved_at", "unknown time")
            click.echo(f"\nRestored session from {saved_at}")

            r_summary = _summarize_resume(resume_text)
            name_part = (
                f", name: {r_summary['detected_name']}"
                if r_summary["detected_name"]
                else ""
            )
            click.echo(f"  Resume: {r_summary['word_count']} words{name_part}")
            j_summary = _summarize_jd(jd_text)
            role_part = (
                f", role: {j_summary['detected_title']}"
                if j_summary["detected_title"]
                else ""
            )
            click.echo(f"  JD: {j_summary['word_count']} words{role_part}")

            if not click.confirm("Use this session?", default=True):
                click.echo("Session discarded. Collecting fresh input.\n")
                resume_session = False  # fall through to manual collection
            else:
                click.echo("")
        else:
            click.echo("\nNo saved session found. Collecting fresh input.\n")
            resume_session = False

    if not resume_session:
        # Step 1: Resume Input
        if has_profile_resume:
            resume_text = prof.base_resume
            click.echo(f"\nUsing profile resume for {profile_name}")
        else:
            click.echo("\n--- Step 1: Your Resume ---")
            try:
                resume_text = collect_resume_text()
            except (FileNotFoundError, ValueError) as e:
                click.echo(f"Error: {e}")
                sys.exit(1)

            if not resume_text:
                click.echo("Error: No resume text provided.")
                sys.exit(1)

            # Validate that it looks like an actual resume
            while not validate_resume_content(resume_text):
                click.echo(
                    click.style(
                        "\nThis doesn't look like a resume. "
                        "Did you paste the right content?",
                        fg="yellow",
                        bold=True,
                    )
                )
                if not click.confirm("Try again?", default=True):
                    click.echo("Exiting.")
                    sys.exit(0)
                try:
                    resume_text = collect_resume_text()
                except (FileNotFoundError, ValueError) as e:
                    click.echo(f"Error: {e}")
                    sys.exit(1)
                if not resume_text:
                    click.echo("Error: No resume text provided.")
                    sys.exit(1)

            # Show resume summary and confirm
            r_summary = _summarize_resume(resume_text)
            click.echo(f"\n  Words:  {r_summary['word_count']}")
            if r_summary["detected_name"]:
                click.echo(f"  Name:   {r_summary['detected_name']}")
            if r_summary["role_count"]:
                click.echo(f"  Roles:  {r_summary['role_count']} detected")
            if not click.confirm("Is this correct?", default=True):
                click.echo("Please re-run and provide the correct resume.")
                sys.exit(0)

        # Returning user check: anything new since last application?
        if has_profile_resume and not dry_run:
            click.echo("\n--- Returning User Check ---")
            new_input = click.prompt(
                "Anything new since your last application? "
                "New skills, projects, certifications? (Enter to skip)",
                default="",
                show_default=False,
            ).strip()
            if new_input:
                # Update base_resume with new info via LLM
                click.echo("Updating your baseline resume with new information...")
                try:
                    # Build a minimal review that tells the LLM to incorporate new info
                    update_review = ResumeReview(
                        overall_score=80,
                        strengths=["Existing resume is solid"],
                        weaknesses=[
                            ReviewWeakness(
                                section="General",
                                issue="Missing recent experience",
                                suggestion=f"Incorporate the following new information: {new_input}",
                            )
                        ],
                    )
                    updated = improve_resume(
                        prof.base_resume, update_review, model=model
                    )
                    updated = resolve_resume_placeholders(updated)

                    click.echo("\nUpdated resume preview (first 500 chars):")
                    click.echo(updated[:500] + ("..." if len(updated) > 500 else ""))
                    if click.confirm("Save this update to your profile?", default=True):
                        resume_text = updated
                        prof.base_resume = updated
                        save_profile(prof, pname)
                        click.echo("Profile updated.")
                    else:
                        click.echo("Keeping existing resume.")
                except Exception as e:
                    logger.warning("Failed to update resume: %s", e)
                    click.echo(f"Warning: Could not update resume ({e}). Continuing with existing.")

                # Save new info to experience bank
                save_experience(prof, "recent_updates", new_input, pname)

        # Step 2: Reference Resume (Optional)
        click.echo("\n--- Step 2: Reference Resume (Optional) ---")
        if reference_path:
            from src.resume_parser import read_resume_from_file

            try:
                reference_text = read_resume_from_file(reference_path)
                click.echo(f"Reference resume loaded from {reference_path}")
            except (FileNotFoundError, ValueError) as e:
                logger.warning("Could not load reference resume: %s", e)
                click.echo(f"Warning: Could not load reference resume ({e}). Skipping.")
        else:
            ref_input = click.prompt(
                "Do you have a reference resume from someone in a similar role? "
                "(file path or Enter to skip)",
                default="",
                show_default=False,
            ).strip()
            if ref_input:
                from src.resume_parser import read_resume_from_file

                try:
                    reference_text = read_resume_from_file(ref_input)
                    r_ref = _summarize_resume(reference_text)
                    click.echo(
                        f"  Reference resume loaded: {r_ref['word_count']} words"
                    )
                except (FileNotFoundError, ValueError) as e:
                    logger.warning("Could not load reference resume: %s", e)
                    click.echo(
                        f"  Warning: Could not load reference resume ({e}). Skipping."
                    )

        # Step 3: Resume Review with Q&A (skip if profile already has a reviewed resume)
        if not dry_run and not has_profile_resume:
            click.echo("\n--- Step 3: Resume Review ---")
            click.echo("Reviewing your resume...")
            try:
                from src.profile import _ask_weakness_questions

                review_result = review_resume(resume_text, model=model)
                display_review(review_result)

                # Walk through each weakness with targeted questions
                answers, all_skipped = _ask_weakness_questions(review_result)

                if answers:
                    answer_context = "\n".join(
                        f"- {issue}: {answer}" for issue, answer in answers.items()
                    )
                    review_result.weaknesses.append(
                        ReviewWeakness(
                            section="User Provided",
                            issue="Additional context from user",
                            suggestion=f"Incorporate these details:\n{answer_context}",
                        )
                    )

                    click.echo("Improving your resume with your answers...")
                    try:
                        improved = improve_resume(
                            resume_text,
                            review_result,
                            skipped_placeholders=all_skipped or None,
                            model=model,
                        )
                    except Exception as e:
                        logger.error("Resume improvement failed: %s", e)
                        click.echo(f"Error improving resume: {e}")
                        improved = None

                    if improved:
                        improved = resolve_resume_placeholders(improved)
                        click.echo("\nImproved resume preview:")
                        click.echo(improved[:500] + ("..." if len(improved) > 500 else ""))
                        if click.confirm("Save this improved version?", default=True):
                            resume_text = improved
                            prof.base_resume = improved
                            save_profile(prof, pname)
                            click.echo("Base resume updated and saved.")
                        else:
                            click.echo("Keeping original resume.")

                    # Save answers to experience bank
                    for issue, answer in answers.items():
                        save_experience(prof, issue, answer, pname)
            except Exception as e:
                logger.warning("Resume review failed: %s", e)
                click.echo(f"Warning: Resume review failed ({e}). Continuing.")

        # Step 4: JD Input
        click.echo("\n--- Step 4: Target Job Description ---")
        jd_text = collect_jd_text()

        if not jd_text:
            click.echo("Error: No job description provided.")
            sys.exit(1)

        # Show JD summary and confirm
        j_summary = _summarize_jd(jd_text)
        click.echo(f"\n  Words:    {j_summary['word_count']}")
        if j_summary["detected_title"]:
            click.echo(f"  Role:     {j_summary['detected_title']}")
        if j_summary["detected_company"]:
            click.echo(f"  Company:  {j_summary['detected_company']}")
        if not click.confirm("Is this correct?", default=True):
            click.echo("Please re-run and provide the correct job description.")
            sys.exit(0)

        # Auto-save session
        save_session(resume_text, jd_text, profile_name=pname)
        click.echo("\nSession saved. Re-run with --resume-session to skip input.")

    # Step 5: JD Analysis
    click.echo("\n--- Step 5: JD Analysis ---")
    if dry_run:
        click.echo("[DRY RUN] Loading mock JD analysis...")
        jd_analysis = JDAnalysis.from_dict(_load_mock_fixture("mock_jd_analysis.json"))
    else:
        _model_label = get_ollama_model_name(model) if is_ollama_model(model) else "Claude"
        click.echo(f"Analyzing job description using {_model_label}...")
        try:
            jd_analysis = analyze_jd(jd_text, reference_text=reference_text, model=model)
        except Exception as e:
            logger.error("JD analysis failed: %s", e)
            click.echo(f"Error analyzing job description: {e}")
            sys.exit(1)

    click.echo(f"Analysis complete. Role: {jd_analysis.job_title or 'N/A'}")
    click.echo(f"Key skills identified: {', '.join(jd_analysis.required_skills[:5])}")
    if jd_analysis.style_insights:
        click.echo(
            f"Reference resume style: {jd_analysis.style_insights.tone or 'analyzed'}"
        )

    # Gap analysis & follow-up questions
    user_additions = ""
    saved_answers: dict | None = None
    if resume_session and session:
        saved_answers = session.get("answers")

    if not skip_questions:
        reuse_answers = False

        # If session has saved answers, offer to reuse them
        if saved_answers:
            click.echo("\n--- Previous Answers Found ---")
            gap_answers_saved = saved_answers.get("gap_answers", [])
            if gap_answers_saved:
                click.echo("\n  Gap question answers:")
                for a in gap_answers_saved:
                    click.echo(f"    - {a}")
            if saved_answers.get("extra_skills"):
                click.echo(f"  Extra skills: {saved_answers['extra_skills']}")
            if saved_answers.get("emphasis"):
                click.echo(f"  Emphasis: {saved_answers['emphasis']}")
            if saved_answers.get("job_title"):
                click.echo(f"  Job title: {saved_answers['job_title']}")

            reuse_answers = click.confirm("Use these answers again?", default=True)

        if reuse_answers and saved_answers:
            # Rebuild user_additions from saved answers
            gap_answers = saved_answers.get("gap_answers", [])
            extra_skills = saved_answers.get("extra_skills", "")
            emphasis = saved_answers.get("emphasis", "")
            job_title = saved_answers.get("job_title", "")
        else:
            # Run gap analysis and ask questions fresh
            click.echo("\n--- Step 6: Gap Analysis & Follow-Up Questions ---")
            if dry_run:
                click.echo("[DRY RUN] Loading mock gap analysis...")
                gap_result = GapAnalysis.from_dict(
                    _load_mock_fixture("mock_gap_analysis.json")
                )
            else:
                click.echo("Comparing your resume against the job requirements...")
                try:
                    gap_result = analyze_gaps(resume_text, jd_analysis, model=model)
                except Exception as e:
                    logger.warning("Gap analysis failed: %s", e)
                    click.echo(
                        f"Warning: Gap analysis failed ({e}). Continuing without it."
                    )
                    gap_result = GapAnalysis()

            # Show strengths
            if gap_result.strengths:
                click.echo("\nYour resume already matches well on:")
                for s in gap_result.strengths:
                    click.echo(f"  - {s}")

            # Ask gap questions (with experience bank lookup + smart follow-up)
            gap_answers: list[str] = []
            if gap_result.gaps:
                click.echo(
                    "\nI have a few questions based on gaps between your resume and the JD."
                    "\nAnswer each one, or press Enter to skip.\n"
                )
                seen_questions: set[str] = set()
                question_count = 0
                for gap in gap_result.gaps:
                    # Safety: never ask more than MAX_GAP_QUESTIONS
                    if question_count >= MAX_GAP_QUESTIONS:
                        logger.debug(
                            "Reached max gap questions limit (%d), stopping",
                            MAX_GAP_QUESTIONS,
                        )
                        break
                    # Skip gaps with empty questions
                    if not gap.question.strip():
                        continue
                    # Deduplicate: skip if we already asked this question
                    q_key = gap.question.strip().lower()
                    if q_key in seen_questions:
                        logger.debug("Skipping duplicate question: %s", gap.question)
                        continue
                    seen_questions.add(q_key)
                    question_count += 1
                    skill = gap.skill
                    saved = lookup_experience(prof, skill)
                    if saved:
                        preview = saved[:70] + "..." if len(saved) > 70 else saved
                        click.echo(f"\n  {skill}:")
                        click.echo(f'    Saved answer: "{preview}"')
                        click.echo(
                            "    [Enter] Use this answer  |  [u] Update  |  [s] Skip this skill"
                        )
                        choice = (
                            click.prompt(
                                "   ",
                                default="",
                                show_default=False,
                            )
                            .strip()
                            .lower()
                        )
                        if choice == "s":
                            pass  # skip — don't include this skill
                        elif choice == "u":
                            answer = click.prompt(
                                f"    {gap.question}",
                                default="",
                                show_default=False,
                            )
                            if answer.strip():
                                gap_answers.append(f"{skill}: {answer.strip()}")
                                save_experience(prof, skill, answer.strip(), pname)
                        else:
                            gap_answers.append(f"{skill}: {saved}")
                    else:
                        answer = click.prompt(
                            f"  {gap.question}",
                            default="",
                            show_default=False,
                        )
                        if answer.strip():
                            gap_answers.append(f"{skill}: {answer.strip()}")
                            save_experience(prof, skill, answer.strip(), pname)
                        elif hasattr(gap, "adjacent_skills") and gap.adjacent_skills:
                            # Smart follow-up: suggest adjacent skills
                            adjacent = ", ".join(gap.adjacent_skills)
                            click.echo(
                                f"    Even related experience counts. "
                                f"For example: {adjacent}."
                            )
                            followup = click.prompt(
                                "    Have you done anything like that?",
                                default="",
                                show_default=False,
                            )
                            if followup.strip():
                                gap_answers.append(f"{skill}: {followup.strip()}")
                                save_experience(
                                    prof, skill, followup.strip(), pname
                                )

            # Generic follow-up questions
            click.echo("\n--- Additional Questions ---")
            extra_skills = click.prompt(
                "Any other skills or certifications to add?",
                default="",
                show_default=False,
            )
            emphasis = click.prompt(
                "What aspects of your experience do you want to emphasize?",
                default="",
                show_default=False,
            )
            job_title = click.prompt(
                "Preferred job title for the resume header? (Enter to use JD title)",
                default="",
                show_default=False,
            )

        # Save answers to session
        answers_data = {
            "gap_answers": gap_answers,
            "extra_skills": extra_skills.strip(),
            "emphasis": emphasis.strip(),
            "job_title": job_title.strip(),
        }
        save_session(resume_text, jd_text, answers=answers_data, profile_name=pname)

        # Build user_additions string
        additions: list[str] = []
        if gap_answers:
            additions.append(
                "Additional experience from candidate:\n"
                + "\n".join(f"- {a}" for a in gap_answers)
            )
        if extra_skills.strip():
            additions.append(
                f"Additional skills/certifications: {extra_skills.strip()}"
            )
        if emphasis.strip():
            additions.append(f"Candidate wants to emphasize: {emphasis.strip()}")
        if job_title.strip():
            additions.append(f"Preferred job title for header: {job_title.strip()}")

        if additions:
            user_additions = "Additional Context from Candidate:\n" + "\n".join(
                additions
            )

    # Compatibility assessment step
    match_score: int | None = None
    if not skip_assessment:
        click.echo("\n--- Step 7: Compatibility Assessment ---")
        if dry_run:
            click.echo("[DRY RUN] Loading mock compatibility assessment...")
            assessment = CompatibilityAssessment.from_dict(
                _load_mock_fixture("mock_compatibility.json")
            )
        else:
            click.echo("Evaluating match between your resume and the job...")
            try:
                assessment = assess_compatibility(resume_text, jd_analysis, model=model)
            except Exception as e:
                logger.warning("Compatibility assessment failed: %s", e)
                click.echo(
                    f"Warning: Compatibility assessment failed ({e}). Continuing."
                )
                assessment = None

        if assessment:
            match_score = assessment.match_score
            display_assessment(assessment)

            if not assessment.proceed:
                click.echo(
                    click.style(
                        "  Warning: Your match score is below 30%. "
                        "This may be a poor fit.",
                        fg="bright_red",
                        bold=True,
                    )
                )
                if not click.confirm("Do you still want to proceed?", default=False):
                    click.echo("Exiting. Try a different job description.")
                    sys.exit(0)
            else:
                if not click.confirm(
                    f"Match score: {assessment.match_score}%. "
                    "Proceed with generation?",
                    default=True,
                ):
                    click.echo("Exiting.")
                    sys.exit(0)

    # Step 8: Generate Tailored Resume
    click.echo("\n--- Step 8: Generating Tailored Resume ---")
    if dry_run:
        click.echo("[DRY RUN] Loading mock resume generation...")
        resume_data = ResumeContent.from_dict(
            _load_mock_fixture("mock_resume_generation.json")
        )
    else:
        click.echo("Generating tailored resume content...")
        try:
            resume_data = generate_tailored_resume(
                resume_text, jd_analysis, user_additions, model=model
            )
        except Exception as e:
            logger.error("Resume generation failed: %s", e)
            click.echo(f"Error generating resume: {e}")

            # Fallback: if using Ollama, offer to switch to Claude
            if is_ollama_model(model):
                if click.confirm(
                    "Local model is having issues. "
                    "Would you like to switch to Claude API?",
                    default=True,
                ):
                    validate_api_key()
                    model = "claude"
                    click.echo("Retrying with Claude API...")
                    try:
                        resume_data = generate_tailored_resume(
                            resume_text, jd_analysis, user_additions, model=model
                        )
                    except Exception as e2:
                        logger.error("Claude fallback also failed: %s", e2)
                        click.echo(f"Error generating resume with Claude: {e2}")
                        sys.exit(1)
                else:
                    sys.exit(1)
            else:
                sys.exit(1)

    click.echo("Resume content generated.")

    # Step 9: Output
    formats = [output_format.lower()]
    format_label = "all formats" if output_format == "all" else output_format.upper()
    click.echo(f"\n--- Step 9: Building {format_label} ---")

    default_output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    try:
        filepaths = build_resume(
            resume_data,
            output_dir=default_output_dir,
            output_path=output_path,
            formats=formats,
            identity=identity,
            jd_analysis=jd_analysis,
        )
    except RuntimeError as e:
        click.echo(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("Output build failed: %s", e)
        click.echo(f"Error building output: {e}")
        sys.exit(1)

    click.echo("\nDone! Your tailored resume has been saved to:")
    for fp in filepaths:
        click.echo(f"  {fp}")

    # Offer PDF conversion if not already generated
    if "pdf" not in formats and any(fp.endswith(".docx") for fp in filepaths):
        if click.confirm("Also save as PDF?", default=False):
            from src.docx_builder import _convert_docx_to_pdf

            for fp in filepaths:
                if fp.endswith(".docx"):
                    pdf_path = fp.rsplit(".", 1)[0] + ".pdf"
                    try:
                        _convert_docx_to_pdf(fp, pdf_path)
                        click.echo(f"  {pdf_path}")
                        filepaths.append(pdf_path)
                    except RuntimeError as e:
                        click.echo(f"PDF conversion failed: {e}")
                    break

    # Save to application history and increment review counter
    company = jd_analysis.company
    role = jd_analysis.job_title
    for fp in filepaths:
        append_history(prof, company, role, match_score, fp, pname)
    prof.applications_since_review += 1
    save_profile(prof, pname)

    # Save preferences on first successful run (or update if flags were explicit)
    if not prefs.get("format"):
        save_preferences(prof, output_format, output_path, pname)

    # Offer to open the file(s)
    if click.confirm("\nOpen file?", default=False):
        for fp in filepaths:
            open_file(fp)


if __name__ == "__main__":
    cli()
