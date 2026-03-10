"""Tests for the FastAPI REST API endpoints."""

import json
import os

from fastapi.testclient import TestClient

from src.models import (
    CompatibilityAssessment,
    JDAnalysis,
    ResumeContent,
    ResumeReview,
)
from src.web import app

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return f.read()


def _load_json_fixture(name: str) -> dict:
    return json.loads(_load_fixture(name))


# ── Health endpoint ────────────────────────────────────────────────────


class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "api_key_set" in data

    def test_health_reports_api_key_status(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        resp = client.get("/api/v1/health")
        assert resp.json()["api_key_set"] is True

    def test_health_reports_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        resp = client.get("/api/v1/health")
        assert resp.json()["api_key_set"] is False


# ── Analyze JD endpoint ───────────────────────────────────────────────


class TestAnalyzeJD:
    def test_analyze_jd_success(self, monkeypatch):
        mock_data = _load_json_fixture("mock_jd_analysis.json")
        mock_analysis = JDAnalysis.from_dict(mock_data.copy())

        monkeypatch.setattr("src.web.analyze_jd", lambda jd_text, **kw: mock_analysis)

        resp = client.post(
            "/api/v1/analyze-jd", json={"jd_text": "Some job description"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_title"] == "Senior Platform Engineer"
        assert data["company"] == "Meridian Data Systems"
        assert "Python" in data["required_skills"]
        assert len(data["key_responsibilities"]) > 0

    def test_analyze_jd_empty_text(self):
        resp = client.post("/api/v1/analyze-jd", json={"jd_text": ""})
        assert resp.status_code == 422

    def test_analyze_jd_missing_field(self):
        resp = client.post("/api/v1/analyze-jd", json={})
        assert resp.status_code == 422

    def test_analyze_jd_api_error(self, monkeypatch):
        def raise_error(jd_text, **kw):
            raise RuntimeError("API call failed")

        monkeypatch.setattr("src.web.analyze_jd", raise_error)

        resp = client.post(
            "/api/v1/analyze-jd", json={"jd_text": "Some job description"}
        )
        assert resp.status_code == 500
        assert "API call failed" in resp.json()["detail"]


# ── Assess compatibility endpoint ─────────────────────────────────────


class TestAssessCompatibility:
    def test_assess_compatibility_success(self, monkeypatch):
        mock_jd = _load_json_fixture("mock_jd_analysis.json")
        mock_compat = _load_json_fixture("mock_compatibility.json")

        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: JDAnalysis.from_dict(mock_jd.copy()),
        )
        monkeypatch.setattr(
            "src.web.assess_compatibility",
            lambda resume_text, jd_analysis, **kw: CompatibilityAssessment.from_dict(
                mock_compat.copy()
            ),
        )

        resp = client.post(
            "/api/v1/assess-compatibility",
            json={"resume_text": "My resume", "jd_text": "A job description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_score"] == 78
        assert data["proceed"] is True
        assert len(data["strong_matches"]) > 0

    def test_assess_compatibility_empty_resume(self):
        resp = client.post(
            "/api/v1/assess-compatibility",
            json={"resume_text": "", "jd_text": "A job description"},
        )
        assert resp.status_code == 422

    def test_assess_compatibility_empty_jd(self):
        resp = client.post(
            "/api/v1/assess-compatibility",
            json={"resume_text": "My resume", "jd_text": ""},
        )
        assert resp.status_code == 422

    def test_assess_compatibility_api_error(self, monkeypatch):
        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: (_ for _ in ()).throw(RuntimeError("fail")),
        )

        resp = client.post(
            "/api/v1/assess-compatibility",
            json={"resume_text": "My resume", "jd_text": "A job description"},
        )
        assert resp.status_code == 500


# ── Generate resume endpoint ──────────────────────────────────────────


class TestGenerate:
    def test_generate_success(self, monkeypatch):
        mock_jd = _load_json_fixture("mock_jd_analysis.json")
        mock_resume = _load_json_fixture("mock_resume_generation.json")

        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: JDAnalysis.from_dict(mock_jd.copy()),
        )
        monkeypatch.setattr(
            "src.web.generate_tailored_resume",
            lambda resume_text, jd_analysis, user_additions="", **kw: ResumeContent.from_dict(
                mock_resume.copy()
            ),
        )

        resp = client.post(
            "/api/v1/generate",
            json={"resume_text": "My resume", "jd_text": "A job description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Sarah Chen"
        assert len(data["experience"]) > 0
        assert len(data["skills"]) > 0

    def test_generate_with_additional_context(self, monkeypatch):
        mock_jd = _load_json_fixture("mock_jd_analysis.json")
        mock_resume = _load_json_fixture("mock_resume_generation.json")

        captured = {}

        def mock_gen(resume_text, jd_analysis, user_additions="", **kw):
            captured["user_additions"] = user_additions
            return ResumeContent.from_dict(mock_resume.copy())

        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: JDAnalysis.from_dict(mock_jd.copy()),
        )
        monkeypatch.setattr("src.web.generate_tailored_resume", mock_gen)

        resp = client.post(
            "/api/v1/generate",
            json={
                "resume_text": "My resume",
                "jd_text": "A job description",
                "additional_context": "I know Go from side projects",
            },
        )
        assert resp.status_code == 200
        assert captured["user_additions"] == "I know Go from side projects"

    def test_generate_api_error(self, monkeypatch):
        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: (_ for _ in ()).throw(RuntimeError("fail")),
        )

        resp = client.post(
            "/api/v1/generate",
            json={"resume_text": "My resume", "jd_text": "A job description"},
        )
        assert resp.status_code == 500


# ── Generate PDF endpoint ─────────────────────────────────────────────


class TestGeneratePDF:
    def test_generate_pdf_success(self, monkeypatch, tmp_path):
        mock_jd = _load_json_fixture("mock_jd_analysis.json")
        mock_resume = _load_json_fixture("mock_resume_generation.json")

        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: JDAnalysis.from_dict(mock_jd.copy()),
        )
        monkeypatch.setattr(
            "src.web.generate_tailored_resume",
            lambda resume_text, jd_analysis, user_additions="", **kw: ResumeContent.from_dict(
                mock_resume.copy()
            ),
        )

        # Create a fake PDF file to simulate build_resume output
        fake_pdf = tmp_path / "Test_Resume.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake content")

        monkeypatch.setattr(
            "src.web.build_resume",
            lambda resume, output_dir, formats, jd_analysis: [str(fake_pdf)],
        )

        resp = client.post(
            "/api/v1/generate/pdf",
            json={"resume_text": "My resume", "jd_text": "A job description"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_generate_pdf_build_failure(self, monkeypatch):
        mock_jd = _load_json_fixture("mock_jd_analysis.json")
        mock_resume = _load_json_fixture("mock_resume_generation.json")

        monkeypatch.setattr(
            "src.web.analyze_jd",
            lambda jd_text, **kw: JDAnalysis.from_dict(mock_jd.copy()),
        )
        monkeypatch.setattr(
            "src.web.generate_tailored_resume",
            lambda resume_text, jd_analysis, user_additions="", **kw: ResumeContent.from_dict(
                mock_resume.copy()
            ),
        )
        monkeypatch.setattr(
            "src.web.build_resume",
            lambda resume, output_dir, formats, jd_analysis: [],
        )

        resp = client.post(
            "/api/v1/generate/pdf",
            json={"resume_text": "My resume", "jd_text": "A job description"},
        )
        assert resp.status_code == 500
        assert "PDF generation failed" in resp.json()["detail"]


# ── Review endpoint ───────────────────────────────────────────────────


class TestReview:
    def test_review_success(self, monkeypatch):
        mock_review_data = _load_json_fixture("mock_review.json")

        monkeypatch.setattr(
            "src.web.review_resume",
            lambda resume_text, **kw: ResumeReview.from_dict(mock_review_data.copy()),
        )

        resp = client.post(
            "/api/v1/review", json={"resume_text": "My resume content here"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 72
        assert len(data["strengths"]) > 0
        assert len(data["weaknesses"]) > 0
        assert len(data["improved_bullets"]) > 0

    def test_review_empty_resume(self):
        resp = client.post("/api/v1/review", json={"resume_text": ""})
        assert resp.status_code == 422

    def test_review_api_error(self, monkeypatch):
        def raise_error(resume_text, **kw):
            raise RuntimeError("API call failed")

        monkeypatch.setattr("src.web.review_resume", raise_error)

        resp = client.post(
            "/api/v1/review", json={"resume_text": "My resume content"}
        )
        assert resp.status_code == 500
        assert "API call failed" in resp.json()["detail"]
