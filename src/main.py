"""CLI entry point for resume-tailor."""

import os
import sys

import click

# Allow running as `python src/main.py` from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import DEFAULT_PROFILE
from src.commands.common import setup_logging


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
    setup_logging(verbose)


# Register commands from submodules
from src.commands.generate import generate  # noqa: E402
from src.commands.review import review  # noqa: E402
from src.commands.profile import profile  # noqa: E402

cli.add_command(generate)
cli.add_command(review)
cli.add_command(profile)


if __name__ == "__main__":
    cli()
