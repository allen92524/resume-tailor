"""Centralized configuration for resume-tailor."""

import os

# LLM settings
DEFAULT_MODEL = "claude"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "300"))  # seconds
OLLAMA_RETRY_ATTEMPTS = 3
OLLAMA_RETRY_DELAY = 10  # seconds between retries
OLLAMA_READY_TIMEOUT = 30  # seconds to wait for Ollama to be ready
OLLAMA_HARD_TIMEOUT = 300  # 5 minutes hard cap per call
OLLAMA_MIN_RESPONSE_LENGTH = 100  # chars — shorter is likely broken
OLLAMA_MAX_RESPONSE_LENGTH = 50000  # chars — longer is likely broken
OLLAMA_CONTEXT_WARN_TOKENS = 4000  # warn if estimated tokens exceed this

# Alias for backward compatibility within call_api
MODEL = CLAUDE_MODEL
MAX_TOKENS_JD_ANALYSIS = 2048
MAX_TOKENS_GAP_ANALYSIS = 2048
MAX_TOKENS_COMPATIBILITY = 2048
MAX_TOKENS_RESUME_GENERATION = 4096
MAX_TOKENS_CONTACT_EXTRACTION = 1024
MAX_TOKENS_REVIEW = 4096
MAX_TOKENS_IMPROVE = 4096
MAX_TOKENS_VALIDATE = 1
MAX_GAP_QUESTIONS = 10

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
