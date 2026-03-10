"""Tests for gap_analyzer.py."""

import json
from unittest.mock import patch

import pytest

from src.gap_analyzer import analyze_gaps
from src.models import JDAnalysis, GapAnalysis


class TestAnalyzeGaps:
    def test_basic_gap_analysis(
        self, sample_resume, mock_jd_analysis, mock_gap_analysis
    ):
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch(
            "src.gap_analyzer.call_llm", return_value=json.dumps(mock_gap_analysis)
        ):
            result = analyze_gaps(sample_resume, jd)

        assert isinstance(result, GapAnalysis)
        assert len(result.gaps) == 5
        assert len(result.strengths) == 7

    def test_gap_structure(self, sample_resume, mock_jd_analysis, mock_gap_analysis):
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch(
            "src.gap_analyzer.call_llm", return_value=json.dumps(mock_gap_analysis)
        ):
            result = analyze_gaps(sample_resume, jd)

        for gap in result.gaps:
            assert gap.skill
            assert gap.question

    def test_handles_markdown_code_block(
        self, sample_resume, mock_jd_analysis, mock_gap_analysis
    ):
        wrapped = f"```json\n{json.dumps(mock_gap_analysis)}\n```"
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.gap_analyzer.call_llm", return_value=wrapped):
            result = analyze_gaps(sample_resume, jd)

        assert len(result.gaps) == 5

    def test_json_parse_error(self, sample_resume, mock_jd_analysis):
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.gap_analyzer.call_llm", return_value="invalid json response"):
            with pytest.raises(json.JSONDecodeError):
                analyze_gaps(sample_resume, jd)
