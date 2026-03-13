"""Tests for resume_enricher.py."""

import json
from unittest.mock import patch

from src.resume_enricher import (
    enrich_resume,
    display_enrichment,
    improve_resume_with_enrichment,
)
from src.models import EnrichmentAnalysis


class TestEnrichResume:
    def test_parses_response(self, sample_resume, mock_enrichment):
        with patch(
            "src.resume_enricher.call_llm",
            return_value=json.dumps(mock_enrichment),
        ):
            result = enrich_resume(sample_resume)

        assert isinstance(result, EnrichmentAnalysis)
        assert result.detected_profession == "AI/NLP Platform Lead"
        assert result.detected_industry == "Enterprise AI"
        assert len(result.strengths) == 3
        assert len(result.questions) == 5

    def test_questions_have_required_fields(self, sample_resume, mock_enrichment):
        with patch(
            "src.resume_enricher.call_llm",
            return_value=json.dumps(mock_enrichment),
        ):
            result = enrich_resume(sample_resume)

        for q in result.questions:
            assert q.role, "Each question must reference a role"
            assert q.question, "Each question must have question text"
            assert q.category, "Each question must have a category"

    def test_json_parse_failure_raises(self, sample_resume):
        with patch("src.resume_enricher.call_llm", return_value="not json"):
            try:
                enrich_resume(sample_resume)
                assert False, "Should have raised"
            except Exception:
                pass


class TestDisplayEnrichment:
    def test_does_not_crash(self, mock_enrichment):
        enrichment = EnrichmentAnalysis.from_dict(mock_enrichment)
        display_enrichment(enrichment)

    def test_empty_enrichment(self):
        enrichment = EnrichmentAnalysis()
        display_enrichment(enrichment)

    def test_no_industry(self):
        enrichment = EnrichmentAnalysis(
            detected_profession="Teacher",
            detected_industry="",
            strengths=["Good classroom management"],
        )
        display_enrichment(enrichment)


class TestImproveResumeWithEnrichment:
    def test_returns_improved_text(self, sample_resume, mock_enrichment):
        improved_text = "Jane Doe\nImproved resume with real data..."
        enrichment = EnrichmentAnalysis.from_dict(mock_enrichment)
        answers = {
            "How many people were on your team?": "12",
            "How many agent behaviors did you ship?": "25",
        }

        with patch(
            "src.resume_enricher.call_llm", return_value=improved_text
        ) as mock_llm:
            result = improve_resume_with_enrichment(sample_resume, enrichment, answers)

        assert isinstance(result, str)
        assert "Jane Doe" in result
        # Verify enrichment JSON was passed to the LLM
        call_args = mock_llm.call_args
        user_content = call_args.kwargs.get(
            "user_content", call_args.args[3] if len(call_args.args) > 3 else ""
        )
        assert "12" in user_content
        assert "25" in user_content

    def test_skips_unanswered_questions(self, sample_resume, mock_enrichment):
        enrichment = EnrichmentAnalysis.from_dict(mock_enrichment)
        answers = {"How many people were on your team?": "12"}

        with patch(
            "src.resume_enricher.call_llm", return_value="Improved text"
        ) as mock_llm:
            improve_resume_with_enrichment(sample_resume, enrichment, answers)

        call_args = mock_llm.call_args
        user_content = call_args.kwargs.get(
            "user_content", call_args.args[3] if len(call_args.args) > 3 else ""
        )
        # Only the answered question should appear in enrichment JSON
        assert "12" in user_content
        assert "How many agent behaviors" not in user_content

    def test_empty_answers(self, sample_resume, mock_enrichment):
        enrichment = EnrichmentAnalysis.from_dict(mock_enrichment)

        with patch("src.resume_enricher.call_llm", return_value="Same text"):
            result = improve_resume_with_enrichment(sample_resume, enrichment, {})

        assert result == "Same text"
