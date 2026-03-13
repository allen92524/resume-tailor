"""User profile management for resume-tailor.

Profile lives at ~/.resume-tailor/{profile_name}/profile.json and stores:
- identity: contact info extracted from base resume
- base_resume: the full resume text
- experience_bank: saved answers from gap analysis Q&A
- history: log of each resume generation
- preferences: saved defaults for format and output path
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone

import click

from .api import parse_json_response
from .config import (
    DEFAULT_MODEL,
    MAX_TOKENS_CONTACT_EXTRACTION,
    DEFAULT_PROFILE,
    get_profile_dir,
    get_profile_path,
)
from .llm_client import call_llm
from .models import Profile, Identity, ResumeReview, EnrichmentAnalysis
from .prompts import CONTACT_EXTRACTION_SYSTEM, CONTACT_EXTRACTION_USER

logger = logging.getLogger(__name__)


def _ensure_profile_dir(profile_name: str = DEFAULT_PROFILE) -> None:
    """Create the profile directory if it doesn't exist."""
    os.makedirs(get_profile_dir(profile_name), exist_ok=True)


def _migrate_legacy_profile() -> None:
    """Migrate legacy ~/.resume-tailor/profile.json to ~/.resume-tailor/default/profile.json.

    Uses hardcoded paths (not get_profile_path) so this is safe when functions
    are mocked in tests.
    """
    base_dir = os.path.expanduser("~/.resume-tailor")
    legacy_path = os.path.join(base_dir, "profile.json")
    new_dir = os.path.join(base_dir, DEFAULT_PROFILE)
    new_path = os.path.join(new_dir, "profile.json")

    if os.path.isfile(legacy_path) and not os.path.isfile(new_path):
        os.makedirs(new_dir, exist_ok=True)
        os.rename(legacy_path, new_path)
        logger.info("Migrated legacy profile from %s to %s", legacy_path, new_path)


def _migrate_profile_fields(
    profile: Profile, profile_name: str = DEFAULT_PROFILE
) -> None:
    """Migrate profile to include new fields introduced in later versions.

    - Copies base_resume to original_resume if original_resume is empty.
    """
    changed = False
    if profile.base_resume and not profile.original_resume:
        profile.original_resume = profile.base_resume
        logger.info("Migrated profile: copied base_resume to original_resume")
        changed = True
    if changed:
        save_profile(profile, profile_name)


def load_profile(profile_name: str = DEFAULT_PROFILE) -> Profile | None:
    """Load the profile from disk. Returns None if no profile exists."""
    # Auto-migrate legacy profile location for the default profile
    if profile_name == DEFAULT_PROFILE:
        _migrate_legacy_profile()

    path = get_profile_path(profile_name)
    if not os.path.isfile(path):
        logger.debug("No profile file at %s", path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Profile loaded from %s", path)
    profile = Profile.from_dict(data)
    _migrate_profile_fields(profile, profile_name)
    return profile


def list_profiles() -> list[str]:
    """Return names of all profiles that have a profile.json file."""
    base_dir = os.path.expanduser("~/.resume-tailor")
    if not os.path.isdir(base_dir):
        return []
    profiles = []
    for name in sorted(os.listdir(base_dir)):
        candidate = os.path.join(base_dir, name, "profile.json")
        if os.path.isfile(candidate):
            profiles.append(name)
    return profiles


def select_profile_interactive(requested: str) -> tuple[str, Profile | None]:
    """If the requested profile doesn't exist, offer to pick an existing one.

    Returns (profile_name, profile_or_none).
    If the user picks an existing profile, returns (name, loaded_profile).
    If the user wants to create a new one, returns (requested, None).
    """
    prof = load_profile(requested)
    if prof:
        return requested, prof

    existing = list_profiles()
    if not existing:
        return requested, None

    # Show existing profiles and let user pick
    click.echo()
    click.echo(f'No profile found for "{requested}".')
    click.echo()
    click.echo("Existing profiles:")
    for i, name in enumerate(existing, 1):
        p = load_profile(name)
        label = name
        if p and p.identity and p.identity.name:
            label = f"{name} ({p.identity.name})"
        click.echo(f"  {i}. {label}")
    click.echo(f"  {len(existing) + 1}. Create a new profile")
    click.echo()

    choice = click.prompt(
        "Choose a profile",
        type=click.IntRange(1, len(existing) + 1),
        default=1,
    )

    if choice <= len(existing):
        picked = existing[choice - 1]
        click.echo(f'Using profile "{picked}".')
        return picked, load_profile(picked)
    else:
        click.echo(f'Creating new profile "{requested}".')
        return requested, None


def save_profile(profile: Profile, profile_name: str = DEFAULT_PROFILE) -> None:
    """Save the profile to disk."""
    _ensure_profile_dir(profile_name)
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    path = get_profile_path(profile_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, indent=2)
    logger.info("Profile saved to %s", path)


def extract_identity(resume_text: str, model: str = DEFAULT_MODEL) -> Identity:
    """Send resume text to the LLM to extract contact/identity fields."""
    logger.info("Extracting identity from resume")

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_CONTACT_EXTRACTION,
        system=CONTACT_EXTRACTION_SYSTEM,
        user_content=CONTACT_EXTRACTION_USER.format(resume_text=resume_text),
        purpose="contact extraction",
    )

    try:
        data = parse_json_response(response_text)
    except Exception:
        logger.warning(
            "Failed to parse contact extraction response. Raw LLM output:\n%s",
            response_text,
        )
        raise
    return Identity.from_dict(data)


def create_profile(
    resume_text: str,
    profile_name: str = DEFAULT_PROFILE,
    model: str = DEFAULT_MODEL,
    original_resume_text: str | None = None,
) -> Profile:
    """Create a new profile from a base resume.

    Extracts identity fields via the selected LLM and initializes all sections.
    *original_resume_text* is the unmodified first upload; defaults to resume_text.
    """
    click.echo("Extracting contact information from your resume...")
    identity = extract_identity(resume_text, model=model)

    # Show what was extracted
    click.echo("\nExtracted profile:")
    for key in Identity.__dataclass_fields__:
        value = getattr(identity, key)
        if value:
            click.echo(f"  {key}: {value}")

    profile = Profile(
        identity=identity,
        base_resume=resume_text,
        original_resume=original_resume_text or resume_text,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    save_profile(profile, profile_name)
    profile_dir = get_profile_dir(profile_name)
    click.echo(f"\nProfile saved to {profile_dir}/profile.json")
    return profile


def _ask_weakness_questions(
    review: "ResumeReview",
    model: str = DEFAULT_MODEL,
) -> tuple[dict[str, str], list[str]]:
    """Walk through each weakness with conversational Q&A.

    Uses the LLM-driven conversational engine to ask follow-ups for vague
    answers and generate per-weakness bullet previews for confirmation.

    Returns (answers_dict, skipped_placeholder_descriptions).
    answers_dict maps weakness descriptions to user answers (or confirmed
    improved bullets) for use in improvement.
    """
    from .conversation import (
        conversational_qa,
        generate_improved_bullet,
        confirm_bullet,
    )

    answers: dict[str, str] = {}
    all_skipped: list[str] = []

    if not review.weaknesses:
        return answers, all_skipped

    click.echo(
        click.style(
            "\nLet's improve your resume. I'll ask about each area that could be stronger.",
            fg="cyan",
            bold=True,
        )
    )
    click.echo("Answer each question or press Enter to skip.\n")

    # Build a map from weakness issue to matching improved bullet text
    bullet_map: dict[str, str] = {}
    for b in review.improved_bullets:
        # Try to match bullets to weaknesses by checking if the original
        # bullet text appears in any weakness suggestion
        for w in review.weaknesses:
            if b.original and b.original.lower() in w.suggestion.lower():
                bullet_map[w.issue] = b.original
                break

    for w in review.weaknesses:
        section_label = f"[{w.section}]" if w.section != "General" else ""
        click.echo(click.style(f"  {section_label} {w.issue}", bold=True))

        bullet_text = bullet_map.get(w.issue, "")

        answer = conversational_qa(
            context_type="resume weakness",
            context_description=w.issue,
            initial_question=f"{w.suggestion}\n    (e.g. specific numbers, tools, or details)",
            bullet_text=bullet_text,
            model=model,
        )

        if answer:
            # Generate an improved bullet preview if we have a matching bullet
            if bullet_text:
                try:
                    improved = generate_improved_bullet(
                        original_bullet=bullet_text,
                        weakness_context=w.issue,
                        user_answers=answer,
                        model=model,
                    )
                    confirmed = confirm_bullet(improved)
                    if confirmed:
                        answers[w.issue] = confirmed
                        click.echo(click.style("    Saved.", fg="green"))
                    else:
                        # User rejected — still save raw answer
                        answers[w.issue] = answer
                        click.echo(
                            click.style("    Using your raw answer.", fg="yellow")
                        )
                except Exception:
                    logger.debug("Bullet improvement failed, using raw answer")
                    answers[w.issue] = answer
                    click.echo(click.style("    Saved.", fg="green"))
            else:
                answers[w.issue] = answer
                click.echo(click.style("    Saved.", fg="green"))
        else:
            click.echo("    Skipped.")
        click.echo("")

    # Also handle improved bullet placeholders
    from src.commands.common import (
        fill_review_placeholders as _fill_review_placeholders,
    )  # noqa: E402

    review = _fill_review_placeholders(review)
    for b in review.improved_bullets:
        all_skipped.extend(b.skipped_placeholders)

    return answers, all_skipped


def _ask_enrichment_questions(
    enrichment: EnrichmentAnalysis,
    model: str = DEFAULT_MODEL,
) -> dict[str, str]:
    """Walk through enrichment questions with conversational Q&A.

    Uses the LLM-driven conversational engine to ask follow-ups for vague
    answers and generate per-bullet previews for confirmation.

    Returns dict mapping question text to user answers (or confirmed
    improved bullets).
    """
    from .conversation import (
        conversational_qa,
        generate_improved_bullet,
        confirm_bullet,
    )

    answers: dict[str, str] = {}

    if not enrichment.questions:
        return answers

    click.echo(
        click.style(
            "\nLet's gather some details to strengthen your resume.",
            fg="cyan",
            bold=True,
        )
    )
    click.echo("Answer each question or press Enter to skip.\n")

    for q in enrichment.questions:
        click.echo(click.style(f"  [{q.role}]", bold=True))

        initial_question = q.question
        if q.example_answers:
            initial_question += f"\n    ({q.example_answers})"

        answer = conversational_qa(
            context_type="resume enrichment",
            context_description=q.question,
            initial_question=initial_question,
            bullet_text=q.bullet_text,
            model=model,
        )

        if answer:
            # Generate an improved bullet preview if we have a matching bullet
            if q.bullet_text:
                try:
                    improved = generate_improved_bullet(
                        original_bullet=q.bullet_text,
                        weakness_context=q.question,
                        user_answers=answer,
                        model=model,
                    )
                    confirmed = confirm_bullet(improved)
                    if confirmed:
                        answers[q.question] = confirmed
                        click.echo(click.style("    Saved.", fg="green"))
                    else:
                        # User rejected — still save raw answer
                        answers[q.question] = answer
                        click.echo(
                            click.style("    Using your raw answer.", fg="yellow")
                        )
                except Exception:
                    logger.debug("Bullet improvement failed, using raw answer")
                    answers[q.question] = answer
                    click.echo(click.style("    Saved.", fg="green"))
            else:
                answers[q.question] = answer
                click.echo(click.style("    Saved.", fg="green"))
        else:
            click.echo("    Skipped.")
        click.echo("")

    return answers


def first_run_setup(
    profile_name: str = DEFAULT_PROFILE, model: str = DEFAULT_MODEL
) -> Profile:
    """First-run experience: collect base resume, enrich it, and create profile."""
    from .resume_parser import collect_resume_text
    from .resume_enricher import (
        enrich_resume,
        display_enrichment,
        improve_resume_with_enrichment,
    )

    click.echo("\n" + "=" * 50)
    click.echo("  Welcome! Let's set up your profile.")
    if profile_name != DEFAULT_PROFILE:
        click.echo(f"  (Profile: {profile_name})")
    click.echo("=" * 50)
    click.echo(
        "\nProvide your base resume once, and it will be used for all future runs."
    )

    click.echo("\n--- Base Resume ---")
    resume_text = collect_resume_text()
    if not resume_text:
        click.echo("Error: No resume text provided.")
        sys.exit(1)

    # Preserve the original upload before any modifications
    original_resume_text = resume_text

    # Enrich the resume before saving
    click.echo("\nAnalyzing your resume...")
    try:
        enrichment = enrich_resume(resume_text, model=model)
        display_enrichment(enrichment)

        # Walk through enrichment questions to gather real data
        answers = _ask_enrichment_questions(enrichment, model=model)

        if answers:
            click.echo("Improving your resume with your answers...")
            resume_text = improve_resume_with_enrichment(
                resume_text,
                enrichment,
                answers,
                model=model,
            )

            # Show the improved version and get confirmation
            click.echo("\n" + "=" * 50)
            click.echo("  Improved Resume Preview")
            click.echo("=" * 50)
            click.echo(resume_text)
            click.echo("=" * 50)

            if not click.confirm(
                "Save this improved version as your base resume?", default=True
            ):
                click.echo("Keeping your original resume.")
                resume_text = original_resume_text
            else:
                click.echo("Resume improved and saved.")
        else:
            click.echo("No changes requested. Keeping your original resume.")

        # Save raw answers to experience bank for future reuse
        experience_bank_entries: dict[str, str] = {}
        for question, answer in answers.items():
            experience_bank_entries[question] = answer

    except Exception as e:
        logger.warning("Resume enrichment failed: %s", e)
        click.echo(
            f"Warning: Resume enrichment failed ({e}). Continuing with original."
        )
        experience_bank_entries = {}

    profile = create_profile(
        resume_text,
        profile_name,
        model=model,
        original_resume_text=original_resume_text,
    )

    # Save answers to experience bank
    for skill, answer in experience_bank_entries.items():
        save_experience(profile, skill, answer, profile_name)

    return profile


def save_experience(
    profile: Profile, skill: str, answer: str, profile_name: str = DEFAULT_PROFILE
) -> None:
    """Save a gap answer to the experience bank."""
    profile.experience_bank[skill] = answer
    save_profile(profile, profile_name)


def lookup_experience(profile: Profile, skill: str) -> str | None:
    """Look up a saved answer in the experience bank.

    Uses case-insensitive matching on the skill key.
    """
    skill_lower = skill.lower()
    for key, value in profile.experience_bank.items():
        if key.lower() == skill_lower:
            return value
    return None


def append_history(
    profile: Profile,
    company: str | None,
    role: str | None,
    match_score: int | None,
    output_file: str,
    profile_name: str = DEFAULT_PROFILE,
) -> None:
    """Append a generation entry to the application history."""
    profile.history.append(
        {
            "date": datetime.now(timezone.utc).isoformat(),
            "company": company,
            "role": role,
            "match_score": match_score,
            "output_file": output_file,
        }
    )
    save_profile(profile, profile_name)


def save_preferences(
    profile: Profile,
    output_format: str,
    output_path: str | None,
    profile_name: str = DEFAULT_PROFILE,
) -> None:
    """Save user preferences for future runs."""
    profile.preferences = {
        "format": output_format,
        "output_path": output_path,
    }
    save_profile(profile, profile_name)


def get_preferences(profile: Profile) -> dict:
    """Get saved preferences, or empty dict."""
    return profile.preferences


def delete_profile(profile_name: str = DEFAULT_PROFILE) -> bool:
    """Delete the profile file. Returns True if deleted."""
    path = get_profile_path(profile_name)
    if os.path.isfile(path):
        os.remove(path)
        logger.info("Profile deleted: %s", path)
        return True
    return False


def open_in_editor(filepath: str) -> None:
    """Open a file in the user's default editor."""
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
    try:
        subprocess.run([editor, filepath], check=True)
    except FileNotFoundError:
        click.echo(
            f"Editor '{editor}' not found. Set $EDITOR to your preferred editor."
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"Editor exited with error: {e}")


def backup_profile(profile_name: str = DEFAULT_PROFILE) -> str | None:
    """Copy the current profile to a timestamped backup file.

    Returns the backup file path, or None if no profile exists.
    """
    path = get_profile_path(profile_name)
    if not os.path.isfile(path):
        return None

    timestamp = datetime.now().strftime("%Y-%m-%d")
    backup_name = f"profile_backup_{timestamp}.json"
    backup_path = os.path.join(get_profile_dir(profile_name), backup_name)

    import shutil

    shutil.copy2(path, backup_path)
    logger.info("Profile backed up to %s", backup_path)
    return backup_path


def list_backups(profile_name: str = DEFAULT_PROFILE) -> list[str]:
    """Return a sorted list of backup file paths for the given profile."""
    profile_dir = get_profile_dir(profile_name)
    if not os.path.isdir(profile_dir):
        return []

    backups = [
        os.path.join(profile_dir, f)
        for f in os.listdir(profile_dir)
        if f.startswith("profile_backup_") and f.endswith(".json")
    ]
    backups.sort()
    return backups


def restore_profile(backup_path: str, profile_name: str = DEFAULT_PROFILE) -> None:
    """Restore a profile from a backup file."""
    import shutil

    dest = get_profile_path(profile_name)
    _ensure_profile_dir(profile_name)
    shutil.copy2(backup_path, dest)
    logger.info("Profile restored from %s", backup_path)


def export_as_markdown(profile: Profile) -> str:
    """Export profile as formatted markdown string."""
    lines: list[str] = []
    identity = profile.identity

    lines.append(f"# {identity.name or 'Resume Tailor Profile'}")
    lines.append("")

    # Contact info
    contact_fields = [
        ("Email", identity.email),
        ("Phone", identity.phone),
        ("Location", identity.location),
        ("LinkedIn", identity.linkedin),
        ("GitHub", identity.github),
    ]
    contact_items = [f"**{k}:** {v}" for k, v in contact_fields if v]
    if contact_items:
        lines.append("## Contact")
        for item in contact_items:
            lines.append(f"- {item}")
        lines.append("")

    # Writing preferences
    if profile.writing_preferences:
        lines.append("## Writing Preferences")
        for key, value in profile.writing_preferences.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    # Experience bank
    if profile.experience_bank:
        lines.append("## Experience Bank")
        for skill, answer in profile.experience_bank.items():
            lines.append(f"- **{skill}:** {answer}")
        lines.append("")

    # Application history
    if profile.history:
        lines.append("## Application History")
        lines.append("")
        lines.append("| Date | Company | Role | Match Score |")
        lines.append("|------|---------|------|-------------|")
        for entry in profile.history:
            date = entry.get("date", "")[:10]
            company = entry.get("company") or "N/A"
            role = entry.get("role") or "N/A"
            score = entry.get("match_score")
            score_str = f"{score}%" if score is not None else "N/A"
            lines.append(f"| {date} | {company} | {role} | {score_str} |")
        lines.append("")

    # Preferences
    if profile.preferences:
        lines.append("## Preferences")
        if profile.preferences.get("format"):
            lines.append(f"- **Default format:** {profile.preferences['format']}")
        if profile.preferences.get("output_path"):
            lines.append(
                f"- **Default output path:** {profile.preferences['output_path']}"
            )
        lines.append("")

    return "\n".join(lines)
