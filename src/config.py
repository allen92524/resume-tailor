"""Centralized configuration for resume-tailor."""

import os

# Claude API settings
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS_JD_ANALYSIS = 2048
MAX_TOKENS_GAP_ANALYSIS = 2048
MAX_TOKENS_COMPATIBILITY = 2048
MAX_TOKENS_RESUME_GENERATION = 4096
MAX_TOKENS_CONTACT_EXTRACTION = 1024
MAX_TOKENS_REVIEW = 4096
MAX_TOKENS_IMPROVE = 4096
MAX_TOKENS_VALIDATE = 1

# Retry settings (tenacity)
RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_WAIT = 2  # seconds
RETRY_MAX_WAIT = 8  # seconds

# Output defaults
DEFAULT_OUTPUT_FORMAT = "docx"

# Default profile name
DEFAULT_PROFILE = "default"


def get_profile_dir(profile_name: str = DEFAULT_PROFILE) -> str:
    """Return the directory for a given profile name."""
    return os.path.join(os.path.expanduser("~/.resume-tailor"), profile_name)


def get_profile_path(profile_name: str = DEFAULT_PROFILE) -> str:
    """Return the profile.json path for a given profile name."""
    return os.path.join(get_profile_dir(profile_name), "profile.json")


# Session
SESSION_FILENAME = ".session.json"
