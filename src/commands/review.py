"""Review CLI command."""

import logging
import sys

import click

from src.llm_client import is_ollama_model, get_ollama_model_name, prepare_ollama, resolve_claude_model
from src.models import ReviewWeakness
from src.resume_reviewer import (
    review_resume,
    improve_resume,
    display_review,
    resolve_resume_placeholders,
)
from src.profile import save_profile, get_preferences, save_experience, select_profile_interactive
from src.commands.common import validate_api_key, select_model_interactive

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--model",
    default=None,
    help="LLM model to use. 'claude' for Anthropic API, or 'ollama:<name>' for local Ollama.",
)
@click.pass_context
def review(ctx, model):
    """Review your base resume for quality and get improvement suggestions."""
    pname = ctx.obj["profile_name"]

    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname
    if not prof:
        click.echo("No profile found. Run `generate` first to create one.")
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
        try:
            resolve_claude_model(model)
        except ValueError as e:
            click.echo(f"Error: {e}")
            sys.exit(1)

    # Migrate profile if needed (flat experience_bank → structured work_history)
    if prof.needs_migration:
        from src.profile import migrate_profile

        migrate_profile(prof, pname, model=model)

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

    answers, all_skipped = _ask_weakness_questions(review_result, model=model)

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

            # Save answers to work history under "Review Improvements"
            for issue, answer in answers.items():
                save_experience(prof, issue, answer, pname)
        else:
            click.echo("Keeping existing resume.")
