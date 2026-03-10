"""FastAPI REST API for resume-tailor."""

from __future__ import annotations

import os
import tempfile
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from src.compatibility_assessor import assess_compatibility
from src.config import DEFAULT_MODEL
from src.docx_builder import build_resume
from src.jd_analyzer import analyze_jd
from src.models import JDAnalysis, ResumeContent, ResumeReview
from src.resume_generator import generate_tailored_resume
from src.resume_reviewer import review_resume
from src.telemetry import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    ACTIVE_REQUESTS,
    RESUME_GENERATION_COUNT,
    tracer,
)

app = FastAPI(
    title="Resume Tailor API",
    description="AI-powered resume tailoring API using Claude",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── OpenTelemetry auto-instrumentation for FastAPI ────────────────────

FastAPIInstrumentor.instrument_app(app)


# ── Prometheus metrics middleware ─────────────────────────────────────


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """Track request count, duration, and active requests."""
    if request.url.path == "/metrics":
        return await call_next(request)

    ACTIVE_REQUESTS.inc()
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration = time.perf_counter() - start
    ACTIVE_REQUESTS.dec()

    endpoint = request.url.path
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code,
    ).inc()
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=endpoint,
    ).observe(duration)

    return response


# ── Prometheus metrics endpoint ───────────────────────────────────────


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Pydantic request/response schemas ──────────────────────────────────


class AnalyzeJDRequest(BaseModel):
    jd_text: str = Field(..., min_length=1, description="Job description text")
    model: str = Field(DEFAULT_MODEL, description="LLM model: 'claude' or 'ollama:<name>'")


class StyleInsightsResponse(BaseModel):
    bullet_style: str = ""
    keyword_strategy: str = ""
    section_emphasis: str = ""
    tone: str = ""
    notable_patterns: list[str] = []


class JDAnalysisResponse(BaseModel):
    job_title: str
    company: str | None = None
    required_skills: list[str]
    preferred_skills: list[str]
    key_responsibilities: list[str]
    keywords: list[str]
    experience_level: str
    industry: str | None = None
    culture_signals: list[str]
    style_insights: StyleInsightsResponse | None = None


class CompatibilityRequest(BaseModel):
    resume_text: str = Field(..., min_length=1, description="Resume text")
    jd_text: str = Field(..., min_length=1, description="Job description text")
    model: str = Field(DEFAULT_MODEL, description="LLM model: 'claude' or 'ollama:<name>'")


class CompatibilityResponse(BaseModel):
    match_score: int
    strong_matches: list[str]
    addressable_gaps: list[str]
    missing: list[str]
    recommendation: str
    proceed: bool


class GenerateRequest(BaseModel):
    resume_text: str = Field(..., min_length=1, description="Resume text")
    jd_text: str = Field(..., min_length=1, description="Job description text")
    additional_context: str = Field("", description="Extra context from gap answers")
    model: str = Field(DEFAULT_MODEL, description="LLM model: 'claude' or 'ollama:<name>'")


class ExperienceEntryResponse(BaseModel):
    title: str = ""
    company: str = ""
    dates: str = ""
    bullets: list[str] = []
    placeholder_bullets: list[int] = []
    placeholder_descriptions: dict[str, str] = {}


class EducationEntryResponse(BaseModel):
    degree: str = ""
    institution: str | None = None
    year: str | None = None


class ResumeContentResponse(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    summary: str | None = None
    experience: list[ExperienceEntryResponse]
    skills: list[str]
    education: list[EducationEntryResponse]
    certifications: list[str]


class ReviewRequest(BaseModel):
    resume_text: str = Field(..., min_length=1, description="Resume text")
    model: str = Field(DEFAULT_MODEL, description="LLM model: 'claude' or 'ollama:<name>'")


class ReviewWeaknessResponse(BaseModel):
    section: str = "General"
    issue: str = ""
    suggestion: str = ""


class ImprovedBulletResponse(BaseModel):
    original: str = ""
    improved: str = ""
    has_placeholders: bool = False


class ReviewResponse(BaseModel):
    overall_score: int
    strengths: list[str]
    weaknesses: list[ReviewWeaknessResponse]
    missing_keywords: list[str]
    improved_bullets: list[ImprovedBulletResponse]


class HealthResponse(BaseModel):
    status: str
    api_key_set: bool


class ErrorResponse(BaseModel):
    detail: str


# ── Helper to convert dataclasses to response models ───────────────────


def _jd_analysis_to_response(analysis: JDAnalysis) -> JDAnalysisResponse:
    d = analysis.to_dict()
    return JDAnalysisResponse(**d)


def _resume_content_to_response(content: ResumeContent) -> ResumeContentResponse:
    return ResumeContentResponse(**content.to_dict())


def _review_to_response(review: ResumeReview) -> ReviewResponse:
    return ReviewResponse(**review.to_dict())


# ── Endpoints ──────────────────────────────────────────────────────────


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        api_key_set=bool(os.environ.get("ANTHROPIC_API_KEY")),
    )


@app.post(
    "/api/v1/analyze-jd",
    response_model=JDAnalysisResponse,
    responses={500: {"model": ErrorResponse}},
)
async def analyze_jd_endpoint(request: AnalyzeJDRequest):
    """Analyze a job description and return structured analysis."""
    with tracer.start_as_current_span("analyze_jd_endpoint"):
        try:
            analysis = analyze_jd(request.jd_text, model=request.model)
            return _jd_analysis_to_response(analysis)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/v1/assess-compatibility",
    response_model=CompatibilityResponse,
    responses={500: {"model": ErrorResponse}},
)
async def assess_compatibility_endpoint(request: CompatibilityRequest):
    """Assess compatibility between a resume and job description."""
    with tracer.start_as_current_span("assess_compatibility_endpoint"):
        try:
            jd_analysis = analyze_jd(request.jd_text, model=request.model)
            assessment = assess_compatibility(request.resume_text, jd_analysis, model=request.model)
            return CompatibilityResponse(**assessment.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/v1/generate",
    response_model=ResumeContentResponse,
    responses={500: {"model": ErrorResponse}},
)
async def generate_resume_endpoint(request: GenerateRequest):
    """Generate a tailored resume as JSON."""
    with tracer.start_as_current_span("generate_resume_endpoint"):
        try:
            jd_analysis = analyze_jd(request.jd_text, model=request.model)
            resume = generate_tailored_resume(
                request.resume_text, jd_analysis, request.additional_context,
                model=request.model,
            )
            RESUME_GENERATION_COUNT.inc()
            return _resume_content_to_response(resume)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/v1/generate/pdf",
    responses={
        200: {"content": {"application/pdf": {}}},
        500: {"model": ErrorResponse},
    },
)
async def generate_pdf_endpoint(request: GenerateRequest):
    """Generate a tailored resume and return as PDF download."""
    with tracer.start_as_current_span("generate_pdf_endpoint"):
        try:
            jd_analysis = analyze_jd(request.jd_text, model=request.model)
            resume = generate_tailored_resume(
                request.resume_text, jd_analysis, request.additional_context,
                model=request.model,
            )
            RESUME_GENERATION_COUNT.inc()
            with tempfile.TemporaryDirectory() as tmpdir:
                paths = build_resume(
                    resume, output_dir=tmpdir, formats=["pdf"], jd_analysis=jd_analysis
                )
                if not paths:
                    raise HTTPException(
                        status_code=500,
                        detail="PDF generation failed. Is libreoffice-writer installed?",
                    )
                pdf_path = paths[0]
                filename = os.path.basename(pdf_path)
                return FileResponse(
                    pdf_path,
                    media_type="application/pdf",
                    filename=filename,
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/v1/review",
    response_model=ReviewResponse,
    responses={500: {"model": ErrorResponse}},
)
async def review_resume_endpoint(request: ReviewRequest):
    """Review a resume and return score, strengths, weaknesses, and suggestions."""
    with tracer.start_as_current_span("review_resume_endpoint"):
        try:
            review = review_resume(request.resume_text, model=request.model)
            return _review_to_response(review)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
