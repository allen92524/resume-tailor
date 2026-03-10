"""Tests for jd_analyzer.py."""

import json
from unittest.mock import patch

import pytest

from src.jd_analyzer import analyze_jd
from src.models import JDAnalysis


class TestAnalyzeJD:
    def test_basic_analysis(self, sample_jd, mock_jd_analysis):
        response_json = json.dumps(mock_jd_analysis)

        with patch("src.jd_analyzer.call_llm", return_value=response_json):
            result = analyze_jd(sample_jd)

        assert isinstance(result, JDAnalysis)
        assert result.job_title == "Senior Platform Engineer"
        assert result.company == "Meridian Data Systems"
        assert "Python" in result.required_skills
        assert result.experience_level == "senior"

    def test_handles_markdown_code_block(self, sample_jd, mock_jd_analysis):
        wrapped = f"```json\n{json.dumps(mock_jd_analysis)}\n```"

        with patch("src.jd_analyzer.call_llm", return_value=wrapped):
            result = analyze_jd(sample_jd)

        assert result.job_title == "Senior Platform Engineer"

    def test_handles_bare_code_block(self, sample_jd, mock_jd_analysis):
        wrapped = f"```\n{json.dumps(mock_jd_analysis)}\n```"

        with patch("src.jd_analyzer.call_llm", return_value=wrapped):
            result = analyze_jd(sample_jd)

        assert result.job_title == "Senior Platform Engineer"

    def test_json_parse_error(self, sample_jd):
        with patch("src.jd_analyzer.call_llm", return_value="This is not JSON at all"):
            with pytest.raises(json.JSONDecodeError):
                analyze_jd(sample_jd)

    def test_with_reference_resume(
        self, sample_jd, sample_reference_resume, mock_jd_analysis
    ):
        mock_jd_analysis["style_insights"] = {
            "bullet_style": "metric-heavy, outcome-focused",
            "keyword_strategy": "natural weaving of role-relevant terms",
            "section_emphasis": "Experience prioritized with detailed bullets",
            "tone": "technical leadership",
            "notable_patterns": [
                "Uses specific scale numbers",
                "Mentions business impact",
            ],
        }
        response_json = json.dumps(mock_jd_analysis)

        with patch("src.jd_analyzer.call_llm", return_value=response_json):
            result = analyze_jd(sample_jd, reference_text=sample_reference_resume)

        assert result.style_insights is not None
        assert result.style_insights.tone == "technical leadership"

    def test_api_called_with_correct_model(self, sample_jd, mock_jd_analysis):
        response_json = json.dumps(mock_jd_analysis)

        with patch("src.jd_analyzer.call_llm", return_value=response_json) as mock_call:
            analyze_jd(sample_jd)

        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs["model"] == "claude"

    def test_api_called_with_custom_model(self, sample_jd, mock_jd_analysis):
        response_json = json.dumps(mock_jd_analysis)

        with patch("src.jd_analyzer.call_llm", return_value=response_json) as mock_call:
            analyze_jd(sample_jd, model="ollama:qwen3.5")

        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs["model"] == "ollama:qwen3.5"
