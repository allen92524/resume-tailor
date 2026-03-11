"""Conversational Q&A engine for resume weakness and gap analysis interviews."""

import logging

import click

from .api import parse_json_response
from .config import (
    DEFAULT_MODEL,
    MAX_CONVERSATIONAL_FOLLOWUPS,
    MAX_TOKENS_FOLLOWUP,
    MAX_TOKENS_BULLET_IMPROVE,
)
from .llm_client import call_llm
from .prompts import (
    CONVERSATIONAL_FOLLOWUP_SYSTEM,
    CONVERSATIONAL_FOLLOWUP_USER,
    BULLET_IMPROVE_SINGLE_SYSTEM,
    BULLET_IMPROVE_SINGLE_USER,
)

logger = logging.getLogger(__name__)


def conversational_qa(
    *,
    context_type: str,
    context_description: str,
    initial_question: str,
    bullet_text: str = "",
    model: str = DEFAULT_MODEL,
    max_followups: int = MAX_CONVERSATIONAL_FOLLOWUPS,
) -> str | None:
    """Run a conversational Q&A loop for a single weakness or gap.

    Asks the initial question, then uses the LLM to decide whether to
    ask follow-ups, accept the answer, or give up gracefully.

    Returns the consolidated user answers as a string, or None if skipped.
    """
    # Ask the initial question
    answer = click.prompt(
        f"    {initial_question}",
        default="",
        show_default=False,
    ).strip()

    if not answer:
        return None

    # Build conversation history
    history: list[dict[str, str]] = [
        {"role": "interviewer", "message": initial_question},
        {"role": "candidate", "message": answer},
    ]
    all_answers: list[str] = [answer]

    for attempt in range(1, max_followups + 1):
        # Ask LLM what to do next
        history_text = "\n".join(
            f"{turn['role'].capitalize()}: {turn['message']}"
            for turn in history
        )

        user_content = CONVERSATIONAL_FOLLOWUP_USER.format(
            context_type=context_type,
            context_description=context_description,
            bullet_text=bullet_text or "(none)",
            conversation_history=history_text,
            attempt_number=attempt,
            max_attempts=max_followups,
        )

        try:
            raw = call_llm(
                system=CONVERSATIONAL_FOLLOWUP_SYSTEM,
                user_content=user_content,
                model=model,
                max_tokens=MAX_TOKENS_FOLLOWUP,
            )
            result = parse_json_response(raw)
        except Exception:
            logger.debug("Follow-up LLM call failed, accepting current answers")
            break

        action = result.get("action", "accept")
        acknowledgment = result.get("acknowledgment", "")
        message = result.get("message", "")

        if action == "accept":
            if acknowledgment:
                click.echo(click.style(f"    {acknowledgment}", fg="green"))
            break

        if action == "give_up":
            if message:
                click.echo(click.style(f"    {message}", fg="yellow"))
            break

        # action == "ask" — follow up
        if acknowledgment:
            click.echo(click.style(f"    {acknowledgment}", fg="green"))

        followup_answer = click.prompt(
            f"    {message}",
            default="",
            show_default=False,
        ).strip()

        history.append({"role": "interviewer", "message": message})

        if followup_answer:
            history.append({"role": "candidate", "message": followup_answer})
            all_answers.append(followup_answer)
        else:
            # User skipped the follow-up — stop asking
            history.append({"role": "candidate", "message": "(skipped)"})
            break

    return " | ".join(all_answers)


def generate_improved_bullet(
    *,
    original_bullet: str,
    weakness_context: str,
    user_answers: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Call the LLM to rewrite a single bullet using gathered answers.

    Returns the improved bullet text.
    """
    user_content = BULLET_IMPROVE_SINGLE_USER.format(
        original_bullet=original_bullet,
        weakness_context=weakness_context,
        user_answers=user_answers,
    )

    result = call_llm(
        system=BULLET_IMPROVE_SINGLE_SYSTEM,
        user_content=user_content,
        model=model,
        max_tokens=MAX_TOKENS_BULLET_IMPROVE,
    )

    # Strip any quotes or whitespace the LLM may have added
    return result.strip().strip('"').strip("'")


def confirm_bullet(bullet: str) -> str | None:
    """Show an improved bullet and ask for confirmation.

    Returns the bullet text (possibly edited), or None if rejected.
    """
    click.echo(f'\n    Preview: "{bullet}"')
    choice = click.prompt(
        "    Accept? [y]es / [n]o / [e]dit",
        default="y",
        show_default=False,
    ).strip().lower()

    if choice in ("y", "yes", ""):
        return bullet
    elif choice in ("e", "edit"):
        edited = click.prompt(
            "    Edit bullet",
            default=bullet,
            show_default=False,
        ).strip()
        return edited if edited else None
    else:
        return None
