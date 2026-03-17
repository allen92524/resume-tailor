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
    MAX_TOKENS_CONFLICT_CHECK,
    MAX_TOKENS_EXPERIENCE_MATCH,
    MAX_TOKENS_MIGRATION,
    PROFILE_SCHEMA_VERSION,
    DEFAULT_PROFILE,
    get_profile_dir,
    get_profile_path,
)
from .llm_client import call_llm
from .models import Profile, Identity, ResumeReview, EnrichmentAnalysis
from .prompts import (
    CONTACT_EXTRACTION_SYSTEM,
    CONTACT_EXTRACTION_USER,
    CONFLICT_CHECK_SYSTEM,
    CONFLICT_CHECK_USER,
    EXPERIENCE_BANK_MATCH_SYSTEM,
    EXPERIENCE_BANK_MATCH_USER,
    MIGRATE_EXTRACT_FACTS_SYSTEM,
    MIGRATE_EXTRACT_FACTS_USER,
    MIGRATE_GROUP_EXPERIENCE_SYSTEM,
    MIGRATE_GROUP_EXPERIENCE_USER,
)

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
        save_experience(profile, skill, answer, profile_name, model=model)

    return profile


def _find_duplicate_key(
    profile: Profile, skill: str, role_key: str
) -> tuple[str, str, str] | None:
    """Find an existing work_history key that is a duplicate of *skill*.

    Returns (existing_role, existing_key, match_type) where match_type
    is ``"exact"`` or ``"fuzzy"``.  Returns ``None`` if no match.

    Match strategy (in order):
    1. Exact case-insensitive match → ``"exact"``
    2. Fuzzy match: after stripping common prefixes like "clarification:",
       check if one normalized key is a substring of the other → ``"fuzzy"``
    """
    skill_lower = skill.lower().strip()
    norm_skill = _normalize_key(skill_lower)

    for role, entries in profile.work_history.items():
        for key in entries:
            key_lower = key.lower().strip()
            # Exact match
            if key_lower == skill_lower:
                return (role, key, "exact")
            # Fuzzy: normalized substring match
            norm_key = _normalize_key(key_lower)
            if norm_key and norm_skill and (
                norm_key in norm_skill or norm_skill in norm_key
            ):
                return (role, key, "fuzzy")
    return None


def _normalize_key(key: str) -> str:
    """Strip common prefixes and noise from a work_history key for comparison."""
    import re

    # Strip "clarification:" prefix
    key = re.sub(r"^clarification:\s*", "", key)
    # Strip leading articles and filler
    key = re.sub(r"^(the|a|an)\s+", "", key)
    # Collapse whitespace
    key = re.sub(r"\s+", " ", key).strip()
    return key


def _merge_answers(
    skill: str, old_answer: str, new_answer: str, model: str = DEFAULT_MODEL
) -> tuple[str, str | None]:
    """Use LLM to combine two answers about the same topic.

    Returns (merged_answer, None) on success, or
    (new_answer, conflict_description) when the answers contradict.
    Falls back to keeping the new answer if the LLM call fails.
    """
    from .config import MAX_TOKENS_MERGE_ANSWERS
    from .prompts import MERGE_ANSWERS_SYSTEM, MERGE_ANSWERS_USER

    try:
        raw = call_llm(
            model=model,
            max_tokens=MAX_TOKENS_MERGE_ANSWERS,
            system=MERGE_ANSWERS_SYSTEM,
            user_content=MERGE_ANSWERS_USER.format(
                skill=skill,
                old_answer=old_answer,
                new_answer=new_answer,
            ),
            purpose="merge answers",
        )
        data = parse_json_response(raw)
        action = data.get("action", "merge")
        if action == "conflict":
            return new_answer, data.get("conflict_description", "Conflicting answers")
        merged = data.get("merged_answer", "")
        return (merged if merged else new_answer), None
    except Exception:
        logger.warning("Answer merge LLM call failed, keeping new answer")
        return new_answer, None


def save_experience(
    profile: Profile,
    skill: str,
    answer: str,
    profile_name: str = DEFAULT_PROFILE,
    role_key: str = "General",
    model: str = DEFAULT_MODEL,
) -> None:
    """Save a gap answer to the structured work history.

    Stores under work_history[role_key][skill] = answer.
    Also writes to legacy experience_bank for backward compatibility
    until migration is complete.

    Deduplication:
    - Exact match (case-insensitive) in same role → silent update.
    - Fuzzy match (any role) → LLM tries to combine the old and new
      answers.  If conflict detected, asks user follow-up questions.
    - Exact match in different role → asks user update-or-new.
    """
    if role_key not in profile.work_history:
        profile.work_history[role_key] = {}

    dup = _find_duplicate_key(profile, skill, role_key)

    if dup:
        dup_role, dup_key, match_type = dup

        if match_type == "exact" and dup_role == role_key:
            # Same role, same key → silently update
            if dup_key != skill:
                del profile.work_history[role_key][dup_key]
            profile.work_history[role_key][skill] = answer

        elif match_type == "fuzzy":
            # Fuzzy match — LLM tries to combine, asks user on conflict
            old_answer = profile.work_history[dup_role][dup_key]
            merged, conflict = _merge_answers(skill, old_answer, answer, model)

            if conflict:
                # Conflict detected — ask user follow-up questions
                from .conversation import conversational_qa

                click.echo(
                    click.style(
                        f"\n  Conflict with existing answer for \"{dup_key}\":",
                        fg="yellow",
                    )
                )
                click.echo(f"    {conflict}")
                resolved = conversational_qa(
                    context_type="profile conflict",
                    context_description=(
                        f"Previous answer for \"{dup_key}\": \"{old_answer}\". "
                        f"New answer: \"{answer}\". Conflict: {conflict}"
                    ),
                    initial_question="Which is correct, or can you clarify?",
                    model=model,
                )
                final = resolved if resolved else answer
            else:
                final = merged

            # Remove old key, save under new key in target role
            del profile.work_history[dup_role][dup_key]
            profile.work_history[role_key][skill] = final

        else:
            # Exact match in different role — ask user
            click.echo(
                f"\n  You already have this answer under [{dup_role}]:"
            )
            old = profile.work_history[dup_role][dup_key]
            click.echo(f"    \"{dup_key}\": {old[:120]}...")
            choice = click.prompt(
                "  Update existing entry, or save as new?",
                type=click.Choice(["update", "new"], case_sensitive=False),
                default="update",
            )
            if choice == "update":
                del profile.work_history[dup_role][dup_key]
                profile.work_history[role_key][skill] = answer
            else:
                profile.work_history[role_key][skill] = answer
    else:
        profile.work_history[role_key][skill] = answer

    # Keep legacy experience_bank in sync for pre-migration code paths
    profile.experience_bank[skill] = answer
    save_profile(profile, profile_name)


def get_all_experience(profile: Profile) -> dict[str, str]:
    """Return a flat dict of all experience across all roles.

    Merges work_history (preferred) with legacy experience_bank as fallback.
    If work_history is populated, it takes precedence.
    """
    if profile.work_history:
        flat: dict[str, str] = {}
        for _role, entries in profile.work_history.items():
            flat.update(entries)
        return flat
    return dict(profile.experience_bank)


def get_experience_by_role(profile: Profile) -> dict[str, dict[str, str]]:
    """Return work history grouped by role.

    Falls back to wrapping legacy experience_bank under a 'General' role.
    """
    if profile.work_history:
        return dict(profile.work_history)
    if profile.experience_bank:
        return {"General": dict(profile.experience_bank)}
    return {}


def format_work_history_text(profile: Profile) -> str:
    """Format work history as readable text for LLM prompts.

    Groups entries by role for structured context.
    """
    by_role = get_experience_by_role(profile)
    if not by_role:
        return ""
    lines = []
    for role, entries in by_role.items():
        lines.append(f"[{role}]")
        for skill, answer in entries.items():
            lines.append(f"  - {skill}: {answer}")
    return "\n".join(lines)


def lookup_experience(profile: Profile, skill: str) -> str | None:
    """Look up a saved answer across all roles.

    Uses case-insensitive matching on the skill key.
    Searches work_history first, falls back to legacy experience_bank.
    """
    skill_lower = skill.lower()
    # Search structured work_history
    for _role, entries in profile.work_history.items():
        for key, value in entries.items():
            if key.lower() == skill_lower:
                return value
    # Fallback to legacy experience_bank
    for key, value in profile.experience_bank.items():
        if key.lower() == skill_lower:
            return value
    return None


def lookup_experience_semantic(
    profile: Profile,
    gap_skills: list[str],
    model: str = DEFAULT_MODEL,
) -> dict[str, list[tuple[str, str]]]:
    """Match gap skills to experience entries using LLM semantic matching.

    Sends all gap skills + work history in ONE batch call.
    Returns a dict mapping gap skill -> list of (key, answer) tuples.
    Falls back to exact matching if LLM call fails.
    """
    all_experience = get_all_experience(profile)
    if not all_experience or not gap_skills:
        return {skill: [] for skill in gap_skills}

    # Format work history for the prompt (role-grouped if available)
    wh_text = format_work_history_text(profile)
    if not wh_text:
        wh_text = "\n".join(
            f"- {key}: {answer[:200]}" for key, answer in all_experience.items()
        )
    skills_text = "\n".join(f"- {skill}" for skill in gap_skills)

    try:
        raw = call_llm(
            model=model,
            max_tokens=MAX_TOKENS_EXPERIENCE_MATCH,
            system=EXPERIENCE_BANK_MATCH_SYSTEM,
            user_content=EXPERIENCE_BANK_MATCH_USER.format(
                gap_skills=skills_text,
                experience_bank=wh_text,
            ),
            purpose="experience bank matching",
        )
        data = parse_json_response(raw)
        matches_raw = data.get("matches", {})

        # Convert to (key, answer) tuples — search across all roles
        result: dict[str, list[tuple[str, str]]] = {}
        for skill in gap_skills:
            matched_keys = matches_raw.get(skill, [])
            result[skill] = [
                (k, all_experience[k])
                for k in matched_keys
                if k in all_experience
            ]
        return result
    except Exception:
        logger.warning("Semantic matching failed, falling back to exact match")
        result = {}
        for skill in gap_skills:
            exact = lookup_experience(profile, skill)
            result[skill] = [(skill, exact)] if exact else []
        return result


def check_conflicts(
    profile: Profile,
    model: str = DEFAULT_MODEL,
) -> list[dict[str, str]]:
    """Check for contradictions between resume and work history.

    Returns a list of conflict dicts with 'description', 'source_a',
    'source_b', and 'question' keys. Empty list if no conflicts.
    """
    from datetime import date

    all_exp = get_all_experience(profile)
    if not profile.base_resume or not all_exp:
        return []

    eb_text = format_work_history_text(profile)
    if not eb_text:
        eb_text = "\n".join(f"- {key}: {answer}" for key, answer in all_exp.items())

    try:
        raw = call_llm(
            model=model,
            max_tokens=MAX_TOKENS_CONFLICT_CHECK,
            system=CONFLICT_CHECK_SYSTEM,
            user_content=CONFLICT_CHECK_USER.format(
                resume_text=profile.base_resume,
                experience_bank=eb_text,
                today=date.today().strftime("%B %d, %Y"),
            ),
            purpose="conflict check",
        )
        data = parse_json_response(raw)
        return data.get("conflicts", [])
    except Exception:
        logger.warning("Conflict check failed, skipping")
        return []


def resolve_conflicts(
    profile: Profile,
    conflicts: list[dict[str, str]],
    profile_name: str = DEFAULT_PROFILE,
    model: str = DEFAULT_MODEL,
) -> None:
    """Walk through conflicts interactively using conversational Q&A.

    Uses the same follow-up engine as gap analysis so the LLM can ask
    clarifying questions if the user's answer is unclear or incomplete.
    Updates the experience bank entries in place and applies corrections
    to the resume text when needed.
    """
    from .conversation import conversational_qa

    if not conflicts:
        return

    click.echo(
        click.style(
            f"\nFound {len(conflicts)} potential conflict(s) in your profile:",
            fg="yellow",
            bold=True,
        )
    )

    resume_corrections: list[dict[str, str]] = []

    for i, conflict in enumerate(conflicts, 1):
        description = conflict.get("description", f"conflict_{i}")
        source_a = conflict.get("source_a", "?")
        source_b = conflict.get("source_b", "?")
        question = conflict.get("question", "Which is correct?")
        eb_keys = conflict.get("experience_bank_keys", [])
        involves_resume = conflict.get("involves_resume", False)

        click.echo(f"\n  Conflict {i}:")
        click.echo(f"    A: {source_a}")
        click.echo(f"    B: {source_b}")

        answer = conversational_qa(
            context_type="profile conflict",
            context_description=f"Conflict: {description}. "
            f'Statement A: "{source_a}" vs Statement B: "{source_b}"',
            initial_question=question,
            model=model,
        )
        if not answer:
            continue

        # Update the conflicting entries in place (work_history + legacy)
        updated_any = False
        for key in eb_keys:
            # Search work_history
            for _role, entries in profile.work_history.items():
                if key in entries:
                    entries[key] = answer
                    updated_any = True
            # Also update legacy experience_bank
            if key in profile.experience_bank:
                profile.experience_bank[key] = answer
                updated_any = True
        if not updated_any:
            # Save under the description in General role
            save_experience(
                profile, f"clarification: {description}", answer, profile_name,
                model=model,
            )

        if involves_resume:
            resume_corrections.append(
                {"description": description, "correction": answer}
            )

    save_profile(profile, profile_name)

    # Apply corrections to resume text if needed
    if resume_corrections and profile.base_resume:
        _apply_resume_corrections(profile, resume_corrections, profile_name, model)

    click.echo(click.style("  Conflicts resolved.", fg="green"))


def _apply_resume_corrections(
    profile: Profile,
    corrections: list[dict[str, str]],
    profile_name: str,
    model: str,
) -> None:
    """Apply factual corrections from conflict resolution to the resume."""
    corrections_text = "\n".join(
        f"- {c['description']}: {c['correction']}" for c in corrections
    )

    click.echo("\nUpdating resume with corrected facts...")
    try:
        updated = call_llm(
            model=model,
            max_tokens=4096,
            system=(
                "You are a resume editor. Apply the factual corrections below to the "
                "resume. ONLY change the specific facts mentioned — do not rewrite, "
                "reformat, or improve anything else. Return the full updated resume text."
            ),
            user_content=(
                f"**Resume:**\n{profile.base_resume}\n\n"
                f"**Corrections to apply:**\n{corrections_text}\n\n"
                "Return the updated resume with ONLY these corrections applied."
            ),
            purpose="resume correction",
        )
        if updated and updated.strip():
            profile.base_resume = updated.strip()
            save_profile(profile, profile_name)
            click.echo(
                click.style("  Resume updated with corrected facts.", fg="green")
            )
    except Exception:
        logger.warning("Failed to apply resume corrections, skipping")
        click.echo("  Could not auto-update resume. You can edit it manually.")


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


def migrate_profile(
    profile: Profile,
    profile_name: str = DEFAULT_PROFILE,
    model: str = DEFAULT_MODEL,
) -> bool:
    """Migrate a profile from flat experience_bank to structured work_history.

    Extracts education/certifications from resume via LLM, then groups
    flat experience bank entries by work role via LLM.
    Auto-backs up the profile before migration.

    Returns True if migration succeeded, False if skipped or failed.
    """
    if not profile.needs_migration:
        return False

    if not profile.base_resume:
        logger.info("No resume in profile, skipping migration")
        return False

    click.echo(
        click.style(
            "\nUpgrading your profile to structured format...",
            fg="cyan",
            bold=True,
        )
    )

    # Auto-backup before migration
    backup_path = backup_profile(profile_name)
    if backup_path:
        click.echo(f"  Profile backed up to: {backup_path}")

    # Step 1: Extract education and certifications from resume
    click.echo("  Extracting education and certifications...")
    try:
        raw = call_llm(
            model=model,
            max_tokens=MAX_TOKENS_MIGRATION,
            system=MIGRATE_EXTRACT_FACTS_SYSTEM,
            user_content=MIGRATE_EXTRACT_FACTS_USER.format(
                resume_text=profile.base_resume,
            ),
            purpose="migration: extract education/certs",
        )
        data = parse_json_response(raw)
        profile.education = data.get("education", [])
        profile.certifications = data.get("certifications", [])
        if profile.education:
            click.echo(f"    Found {len(profile.education)} education entries")
        if profile.certifications:
            click.echo(f"    Found {len(profile.certifications)} certifications")
    except Exception as e:
        logger.warning("Failed to extract education/certs: %s", e)
        click.echo(f"  Warning: Could not extract education/certs ({e})")

    # Step 2: Extract role keys from resume for grouping
    roles = _extract_roles_from_resume(profile.base_resume)
    if not roles:
        # Fallback: put everything under General
        logger.info("No roles detected, using General key")
        profile.work_history = {"General": dict(profile.experience_bank)}
        profile.schema_version = PROFILE_SCHEMA_VERSION
        profile.experience_bank = {}
        save_profile(profile, profile_name)
        click.echo("  Migration complete (all entries under General).")
        return True

    click.echo(f"  Found {len(roles)} work roles. Grouping experience entries...")

    # Step 3: Group experience bank entries by role via LLM
    eb_text = "\n".join(
        f"- {key}: {answer}" for key, answer in profile.experience_bank.items()
    )
    roles_text = "\n".join(f"- {role}" for role in roles)

    try:
        raw = call_llm(
            model=model,
            max_tokens=MAX_TOKENS_MIGRATION,
            system=MIGRATE_GROUP_EXPERIENCE_SYSTEM,
            user_content=MIGRATE_GROUP_EXPERIENCE_USER.format(
                resume_text=profile.base_resume,
                experience_bank=eb_text,
                roles=roles_text,
            ),
            purpose="migration: group experience by role",
        )
        data = parse_json_response(raw)
        work_history = data.get("work_history", {})

        if work_history:
            profile.work_history = work_history
            profile.schema_version = PROFILE_SCHEMA_VERSION
            profile.experience_bank = {}
            save_profile(profile, profile_name)

            total = sum(len(entries) for entries in work_history.values())
            click.echo(f"  Migration complete: {total} entries across {len(work_history)} roles.")
            return True
        else:
            logger.warning("LLM returned empty work_history, keeping flat format")
            click.echo("  Warning: Could not group entries. Keeping existing format.")
            return False
    except Exception as e:
        logger.warning("Migration grouping failed: %s", e)
        click.echo(f"  Warning: Migration failed ({e}). Keeping existing format.")
        return False


def _extract_roles_from_resume(resume_text: str) -> list[str]:
    """Extract work role keys from resume text using pattern matching.

    Looks for patterns like "Title — Company, Dates" or "Company | Title | Dates".
    Returns list of role key strings like "Company | Title | Dates".
    """
    import re

    roles = []
    lines = resume_text.splitlines()

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Pattern: "Title — Company, Dates" or "Title - Company, Dates"
        m = re.match(
            r"^(.+?)\s*[—–-]\s*(.+?),\s*"
            r"(\w+\.?\s+\d{4}\s*[—–-]\s*(?:\w+\.?\s+\d{4}|Present))",
            line,
        )
        if m:
            title, company, dates = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            roles.append(f"{company} | {title} | {dates}")
            continue

        # Pattern: dates on next line after "Title — Company"
        m2 = re.match(r"^(.+?)\s*[—–-]\s*(.+)$", line)
        if m2 and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            dm = re.match(
                r"^(\w+\.?\s+\d{4}\s*[—–-]\s*(?:\w+\.?\s+\d{4}|Present))$",
                next_line,
            )
            if dm:
                title = m2.group(1).strip()
                company = m2.group(2).strip()
                dates = dm.group(1).strip()
                roles.append(f"{company} | {title} | {dates}")

    return roles


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

    # Education
    if profile.education:
        lines.append("## Education")
        for edu in profile.education:
            degree = edu.get("degree", "")
            school = edu.get("school", "")
            year = edu.get("year", "")
            lines.append(f"- **{degree}** — {school} ({year})")
        lines.append("")

    # Certifications
    if profile.certifications:
        lines.append("## Certifications")
        for cert in profile.certifications:
            lines.append(f"- {cert}")
        lines.append("")

    # Work History (structured) or legacy Experience Bank
    by_role = get_experience_by_role(profile)
    if by_role:
        lines.append("## Work History & Experience")
        for role, entries in by_role.items():
            lines.append(f"\n### {role}")
            for skill, answer in entries.items():
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
