"""Tests for session.py."""

from unittest.mock import patch

import pytest

from src.session import save_session, load_session


@pytest.fixture(autouse=True)
def temp_session_dir(tmp_path):
    """Redirect session storage to temp directory."""
    with patch("src.session.get_profile_dir", return_value=str(tmp_path)), patch(
        "src.session.SESSION_FILE", str(tmp_path / ".session.json")
    ):
        yield tmp_path


class TestSession:
    def test_save_and_load(self):
        save_session("resume text", "jd text")
        session = load_session()
        assert session["resume_text"] == "resume text"
        assert session["jd_text"] == "jd text"
        assert "saved_at" in session

    def test_save_with_answers(self):
        answers = {"gap_answers": ["Go: I know Go"], "extra_skills": "Rust"}
        save_session("resume", "jd", answers=answers)
        session = load_session()
        assert session["answers"]["gap_answers"] == ["Go: I know Go"]
        assert session["answers"]["extra_skills"] == "Rust"

    def test_load_returns_none_when_no_file(self):
        assert load_session() is None

    def test_save_overwrites_previous(self):
        save_session("old resume", "old jd")
        save_session("new resume", "new jd")
        session = load_session()
        assert session["resume_text"] == "new resume"

    def test_save_without_answers(self):
        save_session("resume", "jd")
        session = load_session()
        assert "answers" not in session
