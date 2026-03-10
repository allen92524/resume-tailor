"""Tests for compatibility_assessor.py."""

import json
from unittest.mock import patch

import pytest

from src.compatibility_assessor import assess_compatibility, display_assessment
from src.models import JDAnalysis, CompatibilityAssessment


class TestAssessCompatibility:
    def test_basic_assessment(
        self, sample_resume, mock_jd_analysis, mock_compatibility
    ):
        # Remove "proceed" — the model computes it from match_score
        raw = {k: v for k, v in mock_compatibility.items() if k != "proceed"}
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.compatibility_assessor.call_api", return_value=json.dumps(raw)):
            result = assess_compatibility(sample_resume, jd)

        assert isinstance(result, CompatibilityAssessment)
        assert result.match_score == 78
        assert result.proceed is True
        assert len(result.strong_matches) > 0

    def test_low_score_sets_proceed_false(self, sample_resume, mock_jd_analysis):
        raw = {
            "match_score": 20,
            "strong_matches": [],
            "addressable_gaps": ["Some gap"],
            "missing": ["Many things"],
            "recommendation": "Poor fit.",
        }
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.compatibility_assessor.call_api", return_value=json.dumps(raw)):
            result = assess_compatibility(sample_resume, jd)

        assert result.match_score == 20
        assert result.proceed is False

    def test_borderline_score(self, sample_resume, mock_jd_analysis):
        raw = {
            "match_score": 30,
            "strong_matches": ["One thing"],
            "addressable_gaps": [],
            "missing": [],
            "recommendation": "Stretch role.",
        }
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.compatibility_assessor.call_api", return_value=json.dumps(raw)):
            result = assess_compatibility(sample_resume, jd)

        assert result.proceed is True  # 30 >= 30

    def test_json_parse_error(self, sample_resume, mock_jd_analysis):
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.compatibility_assessor.call_api", return_value="not json"):
            with pytest.raises(json.JSONDecodeError):
                assess_compatibility(sample_resume, jd)


class TestDisplayAssessment:
    def test_display_does_not_crash(self, mock_compatibility):
        assessment = CompatibilityAssessment.from_dict(mock_compatibility)
        display_assessment(assessment)

    def test_display_empty_assessment(self):
        assessment = CompatibilityAssessment(match_score=0)
        display_assessment(assessment)
