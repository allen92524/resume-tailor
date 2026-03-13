"""Profile CLI subcommands."""

import os

import click

from src.config import DEFAULT_PROFILE, get_profile_path
from src.profile import (
    save_profile,
    delete_profile,
    open_in_editor,
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
    """Open profile.json in the default editor."""
    pname = ctx.obj["profile_name"]
    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname
    if not prof:
        click.echo("No profile found. Run `generate` first to create one.")
        return
    path = get_profile_path(pname)

    click.echo(f"Opening {path}...")
    open_in_editor(path)


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
