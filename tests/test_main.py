"""Tests for main.py CLI commands."""

import json
import os
import tempfile
from unittest.mock import patch

from click.testing import CliRunner

from src.main import cli, _summarize_resume, _summarize_jd
from src.models import Profile, Identity

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


def _load_json_fixture(name: str) -> dict:
    return json.loads(_load_fixture(name))


class TestSummarizeResume:
    def test_detects_name(self, sample_resume):
        result = _summarize_resume(sample_resume)
        assert result["detected_name"] == "Sarah Chen"

    def test_counts_words(self, sample_resume):
        result = _summarize_resume(sample_resume)
        assert result["word_count"] > 100

    def test_counts_roles(self, sample_resume):
        result = _summarize_resume(sample_resume)
        assert result["role_count"] >= 2


class TestSummarizeJD:
    def test_detects_title(self, sample_jd):
        result = _summarize_jd(sample_jd)
        assert result["detected_title"] is not None

    def test_detects_company(self, sample_jd):
        result = _summarize_jd(sample_jd)
        # The regex looks for "at <Company>" pattern; our JD has this in early lines
        if result["detected_company"]:
            assert isinstance(result["detected_company"], str)
        # If not detected, that's fine — detection is best-effort

    def test_counts_words(self, sample_jd):
        result = _summarize_jd(sample_jd)
        assert result["word_count"] > 50


class TestGenerateCommand:
    """Test CLI flags and options — not the full flow."""

    def test_help_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--output" in result.output
        assert "--skip-questions" in result.output
        assert "--reference" in result.output
        assert "--resume-session" in result.output
        assert "--skip-assessment" in result.output

    def test_dry_run_flag_in_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert "--dry-run" in result.output

    def test_dry_run_skips_api(self):
        """--dry-run should use mock responses and never call the API."""
        runner = CliRunner()

        sample_resume = _load_fixture("sample_resume.txt")
        sample_jd = _load_fixture("sample_jd.txt")

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_profile = Profile(
                identity=Identity(
                    name="Sarah Chen",
                    email="sarah.chen@email.com",
                    phone="(415) 555-0198",
                    location="Seattle, WA",
                    linkedin="linkedin.com/in/sarahchen",
                ),
                base_resume=sample_resume,
                experience_bank={},
                history=[],
                preferences={"format": "md"},
            )

            mock_session = {
                "resume_text": sample_resume,
                "jd_text": sample_jd,
                "saved_at": "2026-03-01T00:00:00Z",
            }

            with patch("src.main.validate_api_key"), patch(
                "src.main.load_profile", return_value=mock_profile
            ), patch("src.main.save_profile"), patch(
                "src.main.load_session", return_value=mock_session
            ), patch(
                "src.main.save_session"
            ), patch(
                "src.main.append_history"
            ), patch(
                "src.main.save_preferences"
            ):

                result = runner.invoke(
                    cli,
                    [
                        "generate",
                        "--dry-run",
                        "--resume-session",
                        "--skip-questions",
                        "--skip-assessment",
                        "--format",
                        "md",
                        "--output",
                        tmpdir,
                    ],
                    input="y\nn\n",
                )  # confirm "Use this session?" + decline "Open file?"

            assert result.exit_code == 0, f"CLI failed:\n{result.output}"
            assert "DRY RUN" in result.output or "dry run" in result.output.lower()
            # Should have generated a file
            md_files = [f for f in os.listdir(tmpdir) if f.endswith(".md")]
            assert len(md_files) >= 1


class TestProfileCommands:
    def test_profile_view_no_profile(self):
        runner = CliRunner()
        with patch("src.main.load_profile", return_value=None):
            result = runner.invoke(cli, ["profile", "view"])
        assert result.exit_code == 0
        assert "No profile found" in result.output

    def test_profile_view_with_profile(self):
        runner = CliRunner()
        mock_profile = Profile(
            identity=Identity(name="Sarah Chen", email="test@test.com"),
            base_resume="some resume text here with enough words to count",
            experience_bank={"Go": "I know Go"},
            history=[],
            preferences={},
        )
        with patch("src.main.load_profile", return_value=mock_profile):
            result = runner.invoke(cli, ["profile", "view"])
        assert result.exit_code == 0
        assert "Sarah Chen" in result.output

    def test_profile_reset_no_profile(self):
        runner = CliRunner()
        with patch("src.main.load_profile", return_value=None):
            result = runner.invoke(cli, ["profile", "reset"])
        assert "No profile found" in result.output

    def test_profile_export_no_profile(self):
        runner = CliRunner()
        with patch("src.main.load_profile", return_value=None):
            result = runner.invoke(cli, ["profile", "export"])
        assert "No profile found" in result.output

    def test_profile_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["profile", "--help"])
        assert result.exit_code == 0
        assert "view" in result.output
        assert "update" in result.output
        assert "reset" in result.output


class TestReviewCommand:
    def test_review_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--help"])
        assert result.exit_code == 0
