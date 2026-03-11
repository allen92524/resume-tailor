"""Tests for resume_generator.py."""

import json
from unittest.mock import patch

from src.resume_generator import (
    generate_tailored_resume,
    validate_resume_content,
    _validate_education,
    _validate_certifications,
    _validate_experience,
)
from src.models import (
    JDAnalysis,
    ResumeContent,
    EducationEntry,
    ExperienceEntry,
)


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

    def test_json_parse_fallback(self, sample_resume, mock_jd_analysis):
        """When LLM returns unparseable text, returns ResumeContent with defaults."""
        jd = JDAnalysis.from_dict(mock_jd_analysis)

        with patch("src.resume_generator.call_llm", return_value="Not valid JSON"):
            result = generate_tailored_resume(sample_resume, jd)

        assert result.experience == []

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


class TestValidateResumeContent:
    """Test content validation to prevent LLM hallucinations."""

    ORIGINAL_RESUME = (
        "Sarah Chen\nsarah@example.com\n555-123-4567\n"
        "San Francisco, CA\n\n"
        "Experience:\n"
        "Senior Software Engineer at TechCorp\n"
        "2020 - Present\n"
        "- Built scalable microservices\n\n"
        "Software Engineer at StartupInc\n"
        "2017 - 2020\n"
        "- Developed REST APIs\n\n"
        "Education:\n"
        "B.S. Computer Science, Stanford University, 2017\n"
        "M.S. Data Science, MIT, 2019\n\n"
        "Certifications:\n"
        "AWS Solutions Architect\n"
        "Certified Kubernetes Administrator\n"
    )

    def test_valid_education_passes(self):
        """Education that exists in original should not be modified."""
        edu = EducationEntry(
            degree="B.S. Computer Science",
            institution="Stanford University",
            year="2017",
        )
        _validate_education(edu, self.ORIGINAL_RESUME.lower())
        # Should not raise or modify
        assert edu.degree == "B.S. Computer Science"

    def test_hallucinated_degree_warns(self, caplog):
        """Hallucinated degree should trigger a warning."""
        edu = EducationEntry(
            degree="Ph.D. Quantum Computing",
            institution="Stanford University",
            year="2017",
        )
        import logging
        with caplog.at_level(logging.WARNING):
            _validate_education(edu, self.ORIGINAL_RESUME.lower())
        assert "Hallucination detected: degree" in caplog.text

    def test_hallucinated_institution_warns(self, caplog):
        edu = EducationEntry(
            degree="B.S. Computer Science",
            institution="Harvard University",
            year="2017",
        )
        import logging
        with caplog.at_level(logging.WARNING):
            _validate_education(edu, self.ORIGINAL_RESUME.lower())
        assert "Hallucination detected: institution" in caplog.text

    def test_hallucinated_education_year_warns(self, caplog):
        edu = EducationEntry(
            degree="B.S. Computer Science",
            institution="Stanford University",
            year="2015",
        )
        import logging
        with caplog.at_level(logging.WARNING):
            _validate_education(edu, self.ORIGINAL_RESUME.lower())
        assert "Hallucination detected: education year" in caplog.text

    def test_valid_certifications_kept(self):
        certs = ["AWS Solutions Architect", "Certified Kubernetes Administrator"]
        result = _validate_certifications(certs, self.ORIGINAL_RESUME.lower())
        assert result == certs

    def test_hallucinated_cert_removed(self, caplog):
        certs = ["AWS Solutions Architect", "Google Cloud Professional"]
        import logging
        with caplog.at_level(logging.WARNING):
            result = _validate_certifications(certs, self.ORIGINAL_RESUME.lower())
        assert result == ["AWS Solutions Architect"]
        assert "Google Cloud Professional" in caplog.text

    def test_all_certs_hallucinated(self, caplog):
        certs = ["Fake Cert 1", "Fake Cert 2"]
        import logging
        with caplog.at_level(logging.WARNING):
            result = _validate_certifications(certs, self.ORIGINAL_RESUME.lower())
        assert result == []

    def test_empty_certs_handled(self):
        result = _validate_certifications([], self.ORIGINAL_RESUME.lower())
        assert result == []

    def test_valid_experience_dates(self):
        """Experience with dates found in original should not warn."""
        exp = ExperienceEntry(
            title="Senior Software Engineer",
            company="TechCorp",
            dates="2020 - Present",
        )
        _validate_experience(exp, self.ORIGINAL_RESUME.lower())
        # No warning expected

    def test_hallucinated_experience_year_warns(self, caplog):
        exp = ExperienceEntry(
            title="Senior Software Engineer",
            company="TechCorp",
            dates="2018 - Present",
        )
        import logging
        with caplog.at_level(logging.WARNING):
            _validate_experience(exp, self.ORIGINAL_RESUME.lower())
        assert "Hallucination detected: year '2018'" in caplog.text

    def test_contact_info_cleared(self):
        """Contact info should always be cleared (profile overrides)."""
        generated = ResumeContent(
            name="Sarah Chen",
            email="fake@llm.com",
            phone="000-000-0000",
            location="Hallucinated City",
            linkedin="linkedin.com/fake",
        )
        result = validate_resume_content(generated, self.ORIGINAL_RESUME)
        assert result.email is None
        assert result.phone is None
        assert result.location is None
        assert result.linkedin is None
        # Name is preserved (docx_builder overrides from profile anyway)
        assert result.name == "Sarah Chen"

    def test_full_validation_integration(self):
        """End-to-end: validate a generated resume against original."""
        generated = ResumeContent(
            name="Sarah Chen",
            email="fake@email.com",
            education=[
                EducationEntry(
                    degree="B.S. Computer Science",
                    institution="Stanford University",
                    year="2017",
                ),
            ],
            certifications=["AWS Solutions Architect", "Fake Cert"],
            experience=[
                ExperienceEntry(
                    title="Senior Software Engineer",
                    company="TechCorp",
                    dates="2020 - Present",
                ),
            ],
        )
        result = validate_resume_content(generated, self.ORIGINAL_RESUME)
        assert result.email is None  # Contact cleared
        assert len(result.certifications) == 1  # Fake cert removed
        assert result.certifications[0] == "AWS Solutions Architect"
