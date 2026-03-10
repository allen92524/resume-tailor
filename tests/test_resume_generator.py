"""Tests for resume_generator.py."""

import json
from unittest.mock import patch

import pytest

from src.resume_generator import generate_tailored_resume
from src.models import JDAnalysis, ResumeContent


class TestGenerateTailoredResume:
    def test_basic_generation(
        self, sample_resume, mock_jd_analysis, mock_resume_generation
    ):
        response_json = json.dumps(mock_resume_generation)
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.resume_generator.call_llm", return_value=response_json):
            result = generate_tailored_resume(sample_resume, jd)

        assert isinstance(result, ResumeContent)
        assert result.name == "Sarah Chen"
        assert len(result.experience) == 3
        assert len(result.skills) > 0
        assert len(result.education) == 2

    def test_with_user_additions(
        self, sample_resume, mock_jd_analysis, mock_resume_generation
    ):
        response_json = json.dumps(mock_resume_generation)
        jd = JDAnalysis.from_dict(mock_jd_analysis)
        additions = "Additional skills: Go programming, gRPC experience"

        with patch(
            "src.resume_generator.call_llm", return_value=response_json
        ) as mock_call:
            generate_tailored_resume(sample_resume, jd, additions)

        # Verify user_additions was included in the API call
        call_kwargs = mock_call.call_args
        assert "Go programming" in call_kwargs.kwargs["user_content"]

    def test_placeholder_detection(
        self, sample_resume, mock_jd_analysis, mock_resume_generation
    ):
        response_json = json.dumps(mock_resume_generation)
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.resume_generator.call_llm", return_value=response_json):
            result = generate_tailored_resume(sample_resume, jd)

        # Second experience entry should have placeholder_bullets = [1]
        nexus = result.experience[1]
        assert nexus.placeholder_bullets == [1]
        assert "[X%]" in nexus.bullets[1]

        # First and third entries should have no placeholders
        assert result.experience[0].placeholder_bullets == []
        assert result.experience[2].placeholder_bullets == []

    def test_handles_markdown_code_block(
        self, sample_resume, mock_jd_analysis, mock_resume_generation
    ):
        wrapped = f"```json\n{json.dumps(mock_resume_generation)}\n```"
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.resume_generator.call_llm", return_value=wrapped):
            result = generate_tailored_resume(sample_resume, jd)

        assert result.name == "Sarah Chen"

    def test_json_parse_error(self, sample_resume, mock_jd_analysis):
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.resume_generator.call_llm", return_value="Not valid JSON"):
            with pytest.raises(json.JSONDecodeError):
                generate_tailored_resume(sample_resume, jd)

    def test_resume_data_structure(
        self, sample_resume, mock_jd_analysis, mock_resume_generation
    ):
        response_json = json.dumps(mock_resume_generation)
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.resume_generator.call_llm", return_value=response_json):
            result = generate_tailored_resume(sample_resume, jd)

        # Verify all expected attributes
        for attr in (
            "name",
            "email",
            "phone",
            "location",
            "linkedin",
            "summary",
            "experience",
            "skills",
            "education",
            "certifications",
        ):
            assert hasattr(result, attr)

        # Verify experience entry structure
        for exp in result.experience:
            assert hasattr(exp, "title")
            assert hasattr(exp, "company")
            assert hasattr(exp, "dates")
            assert hasattr(exp, "bullets")
            assert isinstance(exp.bullets, list)
