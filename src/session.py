"""Session save/restore for resume-tailor."""

import json
import logging
import os
from datetime import datetime, timezone

from .config import DEFAULT_PROFILE, get_profile_dir, SESSION_FILENAME

logger = logging.getLogger(__name__)

# Legacy session file path (used for "default" profile backwards compat)
SESSION_FILE = os.path.join(os.path.dirname(__file__), "..", SESSION_FILENAME)


def _get_session_path(profile_name: str = DEFAULT_PROFILE) -> str:
    """Return the session file path for a given profile."""
    return os.path.join(get_profile_dir(profile_name), SESSION_FILENAME)


def save_session(
    resume_text: str,
    jd_text: str,
    answers: dict | None = None,
    profile_name: str = DEFAULT_PROFILE,
) -> str:
    """Save resume, JD text, and optional Q&A answers to a session file.

    Returns the file path.
    """
    path = os.path.abspath(_get_session_path(profile_name))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "resume_text": resume_text,
        "jd_text": jd_text,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    if answers is not None:
        data["answers"] = answers
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Session saved to %s", path)
    return path


def load_session(profile_name: str = DEFAULT_PROFILE) -> dict | None:
    """Load a saved session. Returns dict with resume_text and jd_text, or None."""
    path = os.path.abspath(_get_session_path(profile_name))
    if not os.path.isfile(path):
        # Fallback: check legacy session file for default profile
        if profile_name == DEFAULT_PROFILE:
            legacy = os.path.abspath(SESSION_FILE)
            if os.path.isfile(legacy):
                logger.debug("Loading legacy session from %s", legacy)
                with open(legacy, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
        logger.debug("No session file found at %s", path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Session loaded from %s", path)
    return data
