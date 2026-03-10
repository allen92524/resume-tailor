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

from .api import call_api, parse_json_response
from .config import (
    MODEL,
    MAX_TOKENS_CONTACT_EXTRACTION,
    DEFAULT_PROFILE,
    get_profile_dir,
    get_profile_path,
)
from .models import Profile, Identity
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
    return Profile.from_dict(data)


def save_profile(profile: Profile, profile_name: str = DEFAULT_PROFILE) -> None:
    """Save the profile to disk."""
    _ensure_profile_dir(profile_name)
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    path = get_profile_path(profile_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, indent=2)
    logger.info("Profile saved to %s", path)


def extract_identity(resume_text: str) -> Identity:
    """Send resume text to Claude to extract contact/identity fields."""
    logger.info("Extracting identity from resume")

    response_text = call_api(
        model=MODEL,
        max_tokens=MAX_TOKENS_CONTACT_EXTRACTION,
        system=CONTACT_EXTRACTION_SYSTEM,
        user_content=CONTACT_EXTRACTION_USER.format(resume_text=resume_text),
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


def create_profile(resume_text: str, profile_name: str = DEFAULT_PROFILE) -> Profile:
    """Create a new profile from a base resume.

    Extracts identity fields via Claude and initializes all sections.
    """
    click.echo("Extracting contact information from your resume...")
    identity = extract_identity(resume_text)

    # Show what was extracted
    click.echo("\nExtracted profile:")
    for key in Identity.__dataclass_fields__:
        value = getattr(identity, key)
        if value:
            click.echo(f"  {key}: {value}")

    profile = Profile(
        identity=identity,
        base_resume=resume_text,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    save_profile(profile, profile_name)
    profile_dir = get_profile_dir(profile_name)
    click.echo(f"\nProfile saved to {profile_dir}/profile.json")
    return profile


def first_run_setup(profile_name: str = DEFAULT_PROFILE) -> Profile:
    """First-run experience: collect base resume, review it, and create profile."""
    from .resume_parser import collect_resume_text
    from .resume_reviewer import (
        review_resume,
        improve_resume,
        display_review,
        resolve_resume_placeholders,
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

    # Review the resume before saving
    click.echo("\nReviewing your resume...")
    try:
        review = review_resume(resume_text)
        display_review(review)

        # Let user fill in placeholder metrics in suggested bullets
        # Lazy import to avoid circular dependency (main imports profile)
        from src.main import _fill_review_placeholders  # noqa: E402

        review = _fill_review_placeholders(review)

        if click.confirm(
            "Would you like to incorporate these suggestions into your base resume?",
            default=False,
        ):
            # Collect skipped placeholder descriptions to avoid re-suggesting
            all_skipped: list[str] = []
            for b in review.improved_bullets:
                all_skipped.extend(b.skipped_placeholders)

            click.echo("Improving your resume...")
            resume_text = improve_resume(
                resume_text,
                review,
                skipped_placeholders=all_skipped or None,
            )
            resume_text = resolve_resume_placeholders(resume_text)
            click.echo("Resume improved.")
    except Exception as e:
        logger.warning("Resume review failed: %s", e)
        click.echo(f"Warning: Resume review failed ({e}). Continuing with original.")

    return create_profile(resume_text, profile_name)



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
