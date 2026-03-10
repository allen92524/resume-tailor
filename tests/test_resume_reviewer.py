"""Tests for resume_reviewer.py."""

import json
from unittest.mock import patch

import pytest

from src.resume_reviewer import review_resume, improve_resume, display_review
from src.models import ResumeReview


class TestReviewResume:
    def test_basic_review(self, sample_resume, mock_review):
        with patch(
            "src.resume_reviewer.call_api", return_value=json.dumps(mock_review)
        ):
            result = review_resume(sample_resume)

        assert isinstance(result, ResumeReview)
        assert result.overall_score == 72
        assert len(result.strengths) > 0
        assert len(result.weaknesses) > 0
        assert len(result.improved_bullets) > 0

    def test_review_json_parse_error(self, sample_resume):
        with patch("src.resume_reviewer.call_api", return_value="not json"):
            with pytest.raises(json.JSONDecodeError):
                review_resume(sample_resume)


class TestImproveResume:
    def test_improve_returns_text(self, sample_resume, mock_review):
        improved_text = "Sarah Chen\nImproved resume text here..."
        review = ResumeReview.from_dict(mock_review)

        with patch("src.resume_reviewer.call_api", return_value=improved_text):
            result = improve_resume(sample_resume, review)

        assert isinstance(result, str)
        assert "Sarah Chen" in result


class TestDisplayReview:
    def test_display_does_not_crash(self, mock_review):
        review = ResumeReview.from_dict(mock_review)
        display_review(review)

    def test_display_with_placeholders(self):
        review = ResumeReview.from_dict(
            {
                "overall_score": 65,
                "strengths": ["Good structure"],
                "weaknesses": [],
                "missing_keywords": ["scalability"],
                "improved_bullets": [
                    {
                        "original": "Built a system",
                        "improved": "Engineered a system reducing latency by [X%]",
                        "has_placeholders": True,
                    }
                ],
            }
        )
        display_review(review)

    def test_display_empty_review(self):
        review = ResumeReview(overall_score=0)
        display_review(review)
