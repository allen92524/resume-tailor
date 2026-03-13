"""Tests for the prompts loader — verifies all prompt files load from prompts/ directory."""

import os

import pytest

from src import prompts

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "prompts")

# Every variable the codebase imports from prompts.py
EXPECTED_VARIABLES = [
    "JD_ANALYSIS_SYSTEM",
    "JD_ANALYSIS_USER",
    "JD_ANALYSIS_WITH_REFERENCE_USER",
    "RESUME_GENERATION_SYSTEM",
    "RESUME_GENERATION_USER",
    "GAP_ANALYSIS_SYSTEM",
    "GAP_ANALYSIS_USER",
    "COMPATIBILITY_ASSESSMENT_SYSTEM",
    "COMPATIBILITY_ASSESSMENT_USER",
    "RESUME_REVIEW_SYSTEM",
    "RESUME_REVIEW_USER",
    "RESUME_IMPROVE_SYSTEM",
    "RESUME_IMPROVE_USER",
    "CONTACT_EXTRACTION_SYSTEM",
    "CONTACT_EXTRACTION_USER",
    "RESUME_ENRICH_SYSTEM",
    "RESUME_ENRICH_USER",
    "RESUME_IMPROVE_ENRICHED_SYSTEM",
    "RESUME_IMPROVE_ENRICHED_USER",
]

EXPECTED_FILES = [
    "jd_analysis.md",
    "resume_generation.md",
    "gap_analysis.md",
    "compatibility_assessment.md",
    "resume_review.md",
    "resume_improve.md",
    "contact_extraction.md",
    "resume_enrich.md",
    "resume_improve_enriched.md",
]

SUPPORT_FILES = [
    "shared_rules.md",
    "PROMPTS.md",
]


class TestPromptsDirectory:
    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_prompt_file_exists(self, filename):
        assert os.path.isfile(os.path.join(PROMPTS_DIR, filename))

    @pytest.mark.parametrize("filename", SUPPORT_FILES)
    def test_support_file_exists(self, filename):
        assert os.path.isfile(os.path.join(PROMPTS_DIR, filename))

    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_prompt_file_has_separator(self, filename):
        with open(os.path.join(PROMPTS_DIR, filename)) as f:
            content = f.read()
        assert "\n---\n" in content, f"{filename} missing --- separator"

    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_prompt_file_has_system_and_user(self, filename):
        with open(os.path.join(PROMPTS_DIR, filename)) as f:
            content = f.read()
        sections = content.split("\n---\n")
        assert len(sections) >= 2, f"{filename} needs at least 2 sections"
        assert len(sections[0].strip()) > 0, f"{filename} system prompt is empty"
        assert len(sections[1].strip()) > 0, f"{filename} user prompt is empty"


class TestSharedRules:
    def test_shared_rules_loads(self):
        assert len(prompts._SHARED_RULES) > 0

    @pytest.mark.parametrize(
        "section",
        [
            "TRUTHFULNESS",
            "METRICS_NO_PLACEHOLDERS",
            "METRICS_WITH_PLACEHOLDERS",
            "DATES",
        ],
    )
    def test_shared_rules_has_section(self, section):
        assert section in prompts._SHARED_RULES
        assert len(prompts._SHARED_RULES[section]) > 10

    def test_no_unresolved_markers_in_loaded_prompts(self):
        """All {%SECTION%} markers should be resolved after loading."""
        import re

        for var_name in EXPECTED_VARIABLES:
            value = getattr(prompts, var_name)
            unresolved = re.findall(r"\{%\w+%\}", value)
            assert (
                not unresolved
            ), f"{var_name} has unresolved shared rule markers: {unresolved}"

    def test_truthfulness_injected_in_resume_generation(self):
        assert "Never fabricate" in prompts.RESUME_GENERATION_USER

    def test_metrics_no_placeholders_injected(self):
        assert "NEVER invent or fabricate metrics" in prompts.RESUME_GENERATION_USER
        assert "strictly forbidden" in prompts.RESUME_GENERATION_USER

    def test_metrics_with_placeholders_injected_in_review(self):
        assert "NEVER invent or fabricate metrics" in prompts.RESUME_REVIEW_USER

    def test_metrics_with_placeholders_injected_in_improve(self):
        assert "NEVER invent or fabricate metrics" in prompts.RESUME_IMPROVE_USER

    def test_dates_injected_in_resume_generation(self):
        assert "NEVER modify" in prompts.RESUME_GENERATION_USER

    def test_truthfulness_injected_in_enrichment(self):
        assert "Never fabricate" in prompts.RESUME_ENRICH_USER

    def test_metrics_no_placeholders_injected_in_enriched_improve(self):
        assert "NEVER invent or fabricate metrics" in prompts.RESUME_IMPROVE_ENRICHED_USER
        assert "strictly forbidden" in prompts.RESUME_IMPROVE_ENRICHED_USER


class TestCompanyContext:
    def test_jd_analysis_has_company_context(self):
        assert "company_context" in prompts.JD_ANALYSIS_USER

    def test_jd_analysis_with_reference_has_company_context(self):
        assert "company_context" in prompts.JD_ANALYSIS_WITH_REFERENCE_USER

    def test_resume_generation_references_company_context(self):
        assert "company_context" in prompts.RESUME_GENERATION_USER

    def test_compatibility_references_company_context(self):
        assert "company_context" in prompts.COMPATIBILITY_ASSESSMENT_USER

    def test_gap_analysis_references_company_context(self):
        assert "company_context" in prompts.GAP_ANALYSIS_USER

    def test_resume_review_references_company_context(self):
        assert "company context" in prompts.RESUME_REVIEW_USER


class TestPromptsLoader:
    @pytest.mark.parametrize("var_name", EXPECTED_VARIABLES)
    def test_variable_exists(self, var_name):
        assert hasattr(prompts, var_name), f"prompts.{var_name} not found"

    @pytest.mark.parametrize("var_name", EXPECTED_VARIABLES)
    def test_variable_is_nonempty_string(self, var_name):
        value = getattr(prompts, var_name)
        assert isinstance(value, str)
        assert len(value) > 10

    def test_jd_analysis_has_three_variants(self):
        sections = prompts._load("jd_analysis.md")
        assert len(sections) == 3

    def test_user_prompts_have_format_placeholders(self):
        """User prompts should contain at least one {placeholder}."""
        user_vars = [v for v in EXPECTED_VARIABLES if v.endswith("_USER")]
        for var_name in user_vars:
            value = getattr(prompts, var_name)
            assert "{" in value, f"{var_name} has no format placeholders"

    def test_system_prompts_have_no_format_placeholders(self):
        """System prompts should NOT contain single-brace format placeholders."""
        system_vars = [v for v in EXPECTED_VARIABLES if v.endswith("_SYSTEM")]
        for var_name in system_vars:
            value = getattr(prompts, var_name)
            # System prompts shouldn't have {var} style placeholders
            import re

            singles = re.findall(r"(?<!\{)\{[a-z_]+\}(?!\})", value)
            assert not singles, f"{var_name} has unexpected placeholders: {singles}"

    def test_jd_analysis_with_reference_has_reference_text(self):
        assert "{reference_text}" in prompts.JD_ANALYSIS_WITH_REFERENCE_USER

    def test_resume_generation_has_resume_and_jd(self):
        assert "{resume_text}" in prompts.RESUME_GENERATION_USER
        assert "{jd_analysis}" in prompts.RESUME_GENERATION_USER

    def test_contact_extraction_has_resume_text(self):
        assert "{resume_text}" in prompts.CONTACT_EXTRACTION_USER
