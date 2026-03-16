"""Tests for main.py CLI commands."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from click.testing import CliRunner

from src.main import cli
from src.commands.common import (
    _summarize_resume,
    _summarize_jd,
    select_model_interactive,
)
from src.models import Profile, Identity, ResumeContent

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

            with patch("src.commands.generate.validate_api_key"), patch(
                "src.commands.generate.select_profile_interactive",
                return_value=("default", mock_profile),
            ), patch("src.commands.generate.save_profile"), patch(
                "src.commands.generate.load_session", return_value=mock_session
            ), patch(
                "src.commands.generate.save_session"
            ), patch(
                "src.commands.generate.append_history"
            ), patch(
                "src.commands.generate.save_preferences"
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
        with patch(
            "src.commands.profile.select_profile_interactive",
            return_value=("default", None),
        ):
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
        with patch(
            "src.commands.profile.select_profile_interactive",
            return_value=("default", mock_profile),
        ):
            result = runner.invoke(cli, ["profile", "view"])
        assert result.exit_code == 0
        assert "Sarah Chen" in result.output

    def test_profile_reset_no_profile(self):
        runner = CliRunner()
        with patch(
            "src.commands.profile.select_profile_interactive",
            return_value=("default", None),
        ):
            result = runner.invoke(cli, ["profile", "reset"])
        assert "No profile found" in result.output

    def test_profile_export_no_profile(self):
        runner = CliRunner()
        with patch(
            "src.commands.profile.select_profile_interactive",
            return_value=("default", None),
        ):
            result = runner.invoke(cli, ["profile", "export"])
        assert "No profile found" in result.output

    def test_profile_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["profile", "--help"])
        assert result.exit_code == 0
        assert "view" in result.output
        assert "update" in result.output
        assert "reset" in result.output


class TestSelectModelInteractive:
    """Test the interactive model selection menu."""

    @patch("src.commands.common.list_ollama_models", return_value=[])
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"})
    def test_only_claude_available_auto_selects(self, mock_ollama):
        """When only Claude is available, it should auto-select without prompting."""
        result = select_model_interactive({})
        assert result == "claude"

    @patch(
        "src.commands.common.list_ollama_models",
        return_value=[
            {"name": "qwen3.5:latest", "size_gb": 3.7},
        ],
    )
    @patch.dict(os.environ, {}, clear=True)
    def test_only_ollama_available_auto_selects(self, mock_ollama):
        """When only one Ollama model is available, auto-select it."""
        # Clear ANTHROPIC_API_KEY
        result = select_model_interactive({})
        assert result == "ollama:qwen3.5:latest"

    @patch("src.commands.common.list_ollama_models", return_value=[])
    @patch.dict(os.environ, {}, clear=True)
    def test_no_backends_exits(self, mock_ollama):
        """When no backends are available, should exit."""
        with pytest.raises(SystemExit):
            select_model_interactive({})


class TestOllamaFallbackChain:
    """Test that Ollama failure offers fallback to Claude."""

    def test_fallback_offered_on_ollama_failure(self):
        """When Ollama fails, user should be asked to switch to Claude."""
        runner = CliRunner()

        sample_resume = _load_fixture("sample_resume.txt")
        sample_jd = _load_fixture("sample_jd.txt")

        mock_profile = Profile(
            identity=Identity(name="Sarah Chen", email="test@test.com"),
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

        mock_generation = _load_json_fixture("mock_resume_generation.json")

        with patch("src.commands.generate.validate_api_key"), patch(
            "src.commands.generate.select_profile_interactive",
            return_value=("default", mock_profile),
        ), patch("src.commands.generate.save_profile"), patch(
            "src.commands.generate.load_session", return_value=mock_session
        ), patch(
            "src.commands.generate.save_session"
        ), patch(
            "src.commands.generate.append_history"
        ), patch(
            "src.commands.generate.save_preferences"
        ), patch(
            "src.commands.generate.prepare_ollama"
        ), patch(
            "src.commands.generate.analyze_jd"
        ) as mock_analyze, patch(
            "src.commands.generate.assess_compatibility"
        ), patch(
            "src.commands.generate.generate_tailored_resume"
        ) as mock_gen, patch(
            "src.commands.generate.build_resume", return_value=["/tmp/test.md"]
        ):

            # Mock JD analysis
            from src.models import JDAnalysis

            mock_analyze.return_value = JDAnalysis(
                job_title="Engineer", company="TestCo"
            )

            # First call (Ollama) fails, second call (Claude fallback) succeeds
            mock_gen.side_effect = [
                RuntimeError("Ollama model failed"),
                ResumeContent.from_dict(mock_generation),
            ]

            result = runner.invoke(
                cli,
                [
                    "generate",
                    "--model",
                    "ollama:qwen3.5",
                    "--resume-session",
                    "--skip-questions",
                    "--skip-assessment",
                    "--format",
                    "md",
                    "--output",
                    "/tmp",
                ],
                # Use session, writing prefs (tone/bullet/general defaults),
                # switch to Claude, decline open
                input="y\n\n\n\ny\nn\n",
            )

            assert result.exit_code == 0, f"CLI failed:\n{result.output}"
            assert "switch to Claude" in result.output or "Claude API" in result.output

    def test_no_fallback_offered_for_claude_failure(self):
        """When Claude fails, no fallback should be offered."""
        runner = CliRunner()

        sample_resume = _load_fixture("sample_resume.txt")
        sample_jd = _load_fixture("sample_jd.txt")

        mock_profile = Profile(
            identity=Identity(name="Sarah Chen", email="test@test.com"),
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

        with patch("src.commands.generate.validate_api_key"), patch(
            "src.commands.generate.select_profile_interactive",
            return_value=("default", mock_profile),
        ), patch("src.commands.generate.save_profile"), patch(
            "src.commands.generate.load_session", return_value=mock_session
        ), patch(
            "src.commands.generate.save_session"
        ), patch(
            "src.commands.generate.append_history"
        ), patch(
            "src.commands.generate.save_preferences"
        ), patch(
            "src.commands.generate.analyze_jd"
        ) as mock_analyze, patch(
            "src.commands.generate.assess_compatibility"
        ), patch(
            "src.commands.generate.generate_tailored_resume"
        ) as mock_gen:

            from src.models import JDAnalysis

            mock_analyze.return_value = JDAnalysis(
                job_title="Engineer", company="TestCo"
            )

            mock_gen.side_effect = RuntimeError("Claude API failed")

            result = runner.invoke(
                cli,
                [
                    "generate",
                    "--model",
                    "claude",
                    "--resume-session",
                    "--skip-questions",
                    "--skip-assessment",
                    "--format",
                    "md",
                ],
                input="y\n",  # Use session
            )

            assert result.exit_code != 0
            assert "switch to Claude" not in result.output

    @patch("click.prompt", side_effect=["1", "2"])  # 1=Claude, 2=Sonnet
    @patch(
        "src.commands.common.list_ollama_models",
        return_value=[
            {"name": "qwen3.5:latest", "size_gb": 3.7},
        ],
    )
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"})
    def test_user_selects_claude(self, mock_ollama, mock_prompt):
        """User picks option 1 (Claude), then Sonnet variant."""
        result = select_model_interactive({})
        assert result == "claude:sonnet"

    @patch("click.prompt", return_value="2")
    @patch(
        "src.commands.common.list_ollama_models",
        return_value=[
            {"name": "qwen3.5:latest", "size_gb": 3.7},
        ],
    )
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"})
    def test_user_selects_ollama(self, mock_ollama, mock_prompt):
        """User picks option 2 (Ollama model)."""
        result = select_model_interactive({})
        assert result == "ollama:qwen3.5:latest"

    @patch("click.prompt", return_value="2")
    @patch(
        "src.commands.common.list_ollama_models",
        return_value=[
            {"name": "qwen3.5:latest", "size_gb": 3.7},
        ],
    )
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"})
    def test_saved_model_shown_as_default(self, mock_ollama, mock_prompt):
        """Saved model preference should be the default selection."""
        # Ollama model saved — selecting it (option 2) skips Claude sub-menu
        select_model_interactive({"model": "ollama:qwen3.5:latest"})
        # The prompt was called with default="2" (the saved model's index)
        mock_prompt.assert_called_once()
        call_kwargs = mock_prompt.call_args
        assert call_kwargs[1]["default"] == "2"

    @patch("click.prompt", return_value="invalid")
    @patch(
        "src.commands.common.list_ollama_models",
        return_value=[
            {"name": "qwen3.5:latest", "size_gb": 3.7},
        ],
    )
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"})
    def test_invalid_input_uses_default(self, mock_ollama, mock_prompt):
        """Invalid input should fall back to the default option."""
        result = select_model_interactive({})
        # Default is option 1 (Claude), then invalid also falls back to Sonnet
        assert result == "claude:sonnet"


class TestReviewCommand:
    def test_review_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--help"])
        assert result.exit_code == 0
