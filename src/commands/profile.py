"""Profile CLI subcommands."""

import os

import click

from src.config import DEFAULT_PROFILE
from src.profile import (
    save_profile,
    delete_profile,
    export_as_markdown,
    backup_profile,
    list_backups,
    restore_profile,
    select_profile_interactive,
)


@click.group()
def profile():
    """Manage your resume-tailor profile."""
    pass


@profile.command("view")
@click.pass_context
def profile_view(ctx):
    """Show full profile summary."""
    pname = ctx.obj["profile_name"]
    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname
    if not prof:
        click.echo("No profile found. Run `generate` first to create one.")
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

    # Education
    if prof.education:
        click.echo("\n  Education:")
        for edu in prof.education:
            click.echo(f"    - {edu.get('degree', '')} — {edu.get('school', '')} ({edu.get('year', '')})")

    # Certifications
    if prof.certifications:
        click.echo(f"\n  Certifications: {', '.join(prof.certifications)}")

    # Work history / experience bank
    from src.profile import get_experience_by_role

    by_role = get_experience_by_role(prof)
    if by_role:
        total = sum(len(e) for e in by_role.values())
        click.echo(f"\n  Work history: {total} entries across {len(by_role)} roles")
        for role, entries in by_role.items():
            click.echo(f"    [{role}]")
            for skill, answer in entries.items():
                preview = answer[:60] + "..." if len(answer) > 60 else answer
                click.echo(f"      - {skill}: {preview}")

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
    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname
    if not prof:
        click.echo("No profile found. Run `generate` first to create one.")
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
    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname
    if not prof:
        click.echo("No profile found. Nothing to reset.")
        return

    from src.profile import get_all_experience

    name = prof.identity.name or "Unknown"
    history_count = len(prof.history)
    bank_count = len(get_all_experience(prof))

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
    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname
    if not prof:
        click.echo("No profile found. Run `generate` first to create one.")
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
    """Edit your saved resume in an interactive text editor."""
    pname = ctx.obj["profile_name"]
    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname
    if not prof:
        click.echo("No profile found. Run `generate` first to create one.")
        return

    if not prof.base_resume:
        click.echo("No resume saved in this profile yet.")
        return

    click.echo("\nWhat would you like to edit?\n")
    click.echo("  1. Resume")
    click.echo("  2. Contact info (name, email, phone, etc.)")
    click.echo("  3. Experience bank (review and correct your saved answers)")
    click.echo()

    choice = click.prompt("Choose", type=click.IntRange(1, 3), default=1)

    if choice == 1:
        # Full-screen prompt_toolkit editor — best UX for editing long free-form text.
        _edit_resume_interactive(prof, pname)
    elif choice == 2:
        # Simple field-by-field prompts — 6 short fields don't need a full-screen editor.
        _edit_contact_interactive(prof, pname)
    else:
        # Q&A review — user confirms or corrects each entry via conversational
        # Q&A. No direct text editing to prevent unpredictable changes.
        _edit_experience_bank_interactive(prof, pname)


def _check_and_resolve_conflicts(prof, pname: str) -> None:
    """Check for contradictions and resolve via conversational Q&A.

    Called after saving edits to resume (option 1) or experience bank (option 3).
    Delegates to the shared check_conflicts + resolve_conflicts from src/profile.py
    which uses conversational Q&A (not plain click.prompt).
    """
    from src.commands.common import select_model_interactive, validate_api_key
    from src.profile import check_conflicts, resolve_conflicts

    from src.profile import get_all_experience

    if not prof.base_resume or not get_all_experience(prof):
        return

    click.echo("\nChecking for contradictions...")

    # Use saved model preference or ask
    model = prof.preferences.get("model", "")
    if not model:
        model = select_model_interactive({})
    validate_api_key(model)

    conflicts = check_conflicts(prof, model=model)
    if conflicts:
        resolve_conflicts(prof, conflicts, pname, model=model)
    else:
        click.echo(click.style("  No contradictions found.", fg="green"))


def _edit_resume_interactive(prof, pname: str) -> None:
    """Edit the resume in a full-screen text editor powered by prompt_toolkit."""
    from prompt_toolkit import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.document import Document
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.layout.layout import Layout

    line_count = len(prof.base_resume.splitlines())
    click.echo(f"\nOpening resume editor ({line_count} lines)...")

    bindings = KeyBindings()
    saved = {"result": None}

    @bindings.add("c-s")
    def _save(event):
        """Ctrl+S to save and exit."""
        saved["result"] = event.app.current_buffer.text
        event.app.exit()

    @bindings.add("c-c")
    def _cancel(event):
        """Ctrl+C to cancel."""
        event.app.exit()

    buffer = Buffer(
        document=Document(prof.base_resume, cursor_position=0),
        multiline=True,
    )

    editor_window = Window(content=BufferControl(buffer=buffer), wrap_lines=True)
    status_bar = Window(
        content=FormattedTextControl(
            lambda: [
                ("bg:#005fff fg:white bold", " Ctrl+S "),
                ("bg:#444444 fg:white", " Save  "),
                ("bg:#cc4444 fg:white bold", " Ctrl+C "),
                ("bg:#444444 fg:white", " Cancel  "),
                ("bg:#333333 fg:#aaaaaa", f" Line {buffer.document.cursor_position_row + 1}/{len(buffer.document.lines)} "),
            ]
        ),
        height=1,
    )

    layout = Layout(HSplit([editor_window, status_bar]))
    app = Application(layout=layout, key_bindings=bindings, full_screen=True)

    try:
        app.run()
    except KeyboardInterrupt:
        click.echo("\nCancelled. No changes made.")
        return

    edited = saved["result"]
    if edited is None:
        click.echo("\nCancelled. No changes made.")
        return

    edited = edited.strip()
    if not edited:
        click.echo("Empty resume. No changes made.")
        return

    if edited == prof.base_resume:
        click.echo("No changes detected.")
        return

    old_words = len(prof.base_resume.split())
    new_words = len(edited.split())
    click.echo(f"\nResume changed: {old_words} words -> {new_words} words")

    if click.confirm("Save changes?", default=True):
        prof.base_resume = edited
        save_profile(prof, pname)
        click.echo("Resume updated.")
        _check_and_resolve_conflicts(prof, pname)
    else:
        click.echo("Cancelled.")


def _edit_contact_interactive(prof, pname: str) -> None:
    """Edit contact info with simple prompts (same as profile update)."""
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


def _edit_experience_bank_interactive(prof, pname: str) -> None:
    """Review work history entries via Q&A — user confirms or corrects each one.

    Users never directly edit the text. Instead, each entry is shown
    grouped by role, and the user confirms it's correct or uses
    conversational Q&A to provide an updated answer.
    """
    from src.conversation import conversational_qa
    from src.profile import get_experience_by_role, save_experience

    by_role = get_experience_by_role(prof)
    if not by_role:
        click.echo("No saved answers yet. Run `generate` to build your work history.")
        return

    total = sum(len(e) for e in by_role.values())
    click.echo(
        f"\nReviewing {total} saved answers across {len(by_role)} roles. "
        "Confirm each one or correct it.\n"
    )

    changed = False
    for role, entries in by_role.items():
        click.echo(click.style(f"\n  [{role}]", bold=True))
        for skill, answer in list(entries.items()):
            click.echo(f"\n    {skill}:")
            click.echo(f"      {answer}")
            if not click.confirm("      Is this still correct?", default=True):
                updated = conversational_qa(
                    context_type="experience review",
                    context_description=(
                        f"Reviewing saved answer for '{skill}' "
                        f"at '{role}'. Previous answer: \"{answer}\""
                    ),
                    initial_question=(
                        f"What would you like to change about your "
                        f"answer for '{skill}'?"
                    ),
                    model="claude",
                )
                if updated:
                    save_experience(prof, skill, updated, pname, role_key=role)
                    changed = True
                    click.echo("      Updated.")

    if changed:
        click.echo("\nWork history updated.")
        _check_and_resolve_conflicts(prof, pname)
    else:
        click.echo("\nNo changes made.")


@profile.command("export")
@click.pass_context
def profile_export(ctx):
    """Export profile as formatted markdown."""
    pname = ctx.obj["profile_name"]
    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname
    if not prof:
        click.echo("No profile found. Run `generate` first to create one.")
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
