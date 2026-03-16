"""Data models for resume-tailor."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StyleInsights:
    bullet_style: str = ""
    keyword_strategy: str = ""
    section_emphasis: str = ""
    tone: str = ""
    notable_patterns: list[str] = field(default_factory=list)


@dataclass
class JDAnalysis:
    job_title: str = ""
    company: str | None = None
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    key_responsibilities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    experience_level: str = ""
    industry: str | None = None
    culture_signals: list[str] = field(default_factory=list)
    style_insights: StyleInsights | None = None

    @classmethod
    def from_dict(cls, data: dict) -> JDAnalysis:
        si = data.pop("style_insights", None)
        obj = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if si and isinstance(si, dict):
            obj.style_insights = StyleInsights(
                **{
                    k: v
                    for k, v in si.items()
                    if k in StyleInsights.__dataclass_fields__
                }
            )
        return obj

    def to_dict(self) -> dict:
        d = {
            k: getattr(self, k)
            for k in self.__dataclass_fields__
            if k != "style_insights"
        }
        if self.style_insights:
            d["style_insights"] = {
                k: getattr(self.style_insights, k)
                for k in StyleInsights.__dataclass_fields__
            }
        return d


@dataclass
class ExperienceEntry:
    title: str = ""
    company: str = ""
    dates: str = ""
    bullets: list[str] = field(default_factory=list)
    placeholder_bullets: list[int] = field(default_factory=list)
    placeholder_descriptions: dict[str, str] = field(default_factory=dict)


@dataclass
class EducationEntry:
    degree: str = ""
    institution: str | None = None
    year: str | None = None


@dataclass
class ResumeContent:
    name: str = "Your Name"
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    summary: str | None = None
    experience: list[ExperienceEntry] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    publications: list[str] = field(default_factory=list)
    awards: list[str] = field(default_factory=list)
    volunteer: list[str] = field(default_factory=list)
    licenses: list[str] = field(default_factory=list)

    @staticmethod
    def _normalize_skills(skills: list[str] | dict[str, list[str]]) -> list[str]:
        """Convert skills dict (category -> items) to 'Category: item1, item2' strings."""
        if isinstance(skills, dict):
            return [
                f"{cat}: {', '.join(items)}" for cat, items in skills.items() if items
            ]
        return skills

    @classmethod
    def from_dict(cls, data: dict) -> ResumeContent:
        exp_list = [
            ExperienceEntry(
                **{
                    k: v
                    for k, v in e.items()
                    if k in ExperienceEntry.__dataclass_fields__
                }
            )
            for e in data.get("experience", [])
        ]
        edu_list = [
            EducationEntry(
                **{
                    k: v
                    for k, v in e.items()
                    if k in EducationEntry.__dataclass_fields__
                }
            )
            for e in data.get("education", [])
        ]
        return cls(
            name=data.get("name", "Your Name"),
            email=data.get("email"),
            phone=data.get("phone"),
            location=data.get("location"),
            linkedin=data.get("linkedin"),
            summary=data.get("summary"),
            experience=exp_list,
            skills=cls._normalize_skills(data.get("skills", [])),
            education=edu_list,
            certifications=data.get("certifications", []),
            publications=data.get("publications", []),
            awards=data.get("awards", []),
            volunteer=data.get("volunteer", []),
            licenses=data.get("licenses", []),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "linkedin": self.linkedin,
            "summary": self.summary,
            "experience": [
                {k: getattr(e, k) for k in ExperienceEntry.__dataclass_fields__}
                for e in self.experience
            ],
            "skills": self.skills,
            "education": [
                {k: getattr(e, k) for k in EducationEntry.__dataclass_fields__}
                for e in self.education
            ],
            "certifications": self.certifications,
            "publications": self.publications,
            "awards": self.awards,
            "volunteer": self.volunteer,
            "licenses": self.licenses,
        }


@dataclass
class EnrichmentQuestion:
    role: str = ""
    bullet_text: str = ""
    question: str = ""
    example_answers: str = ""
    category: str = ""


@dataclass
class EnrichmentAnalysis:
    detected_profession: str = ""
    detected_industry: str = ""
    strengths: list[str] = field(default_factory=list)
    questions: list[EnrichmentQuestion] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> EnrichmentAnalysis:
        questions = [
            EnrichmentQuestion(
                **{
                    k: v
                    for k, v in q.items()
                    if k in EnrichmentQuestion.__dataclass_fields__
                }
            )
            for q in data.get("questions", [])
        ]
        return cls(
            detected_profession=data.get("detected_profession", ""),
            detected_industry=data.get("detected_industry", ""),
            strengths=data.get("strengths", []),
            questions=questions,
        )

    def to_dict(self) -> dict:
        return {
            "detected_profession": self.detected_profession,
            "detected_industry": self.detected_industry,
            "strengths": self.strengths,
            "questions": [
                {k: getattr(q, k) for k in EnrichmentQuestion.__dataclass_fields__}
                for q in self.questions
            ],
        }


@dataclass
class GapEntry:
    skill: str = ""
    question: str = ""
    adjacent_skills: list[str] = field(default_factory=list)


@dataclass
class GapAnalysis:
    gaps: list[GapEntry] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> GapAnalysis:
        gaps = [
            GapEntry(
                **{k: v for k, v in g.items() if k in GapEntry.__dataclass_fields__}
            )
            for g in data.get("gaps", [])
        ]
        return cls(gaps=gaps, strengths=data.get("strengths", []))


@dataclass
class CompatibilityAssessment:
    match_score: int = 0
    strong_matches: list[str] = field(default_factory=list)
    addressable_gaps: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    recommendation: str = ""
    proceed: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> CompatibilityAssessment:
        obj = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        obj.proceed = obj.match_score >= 30
        return obj

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass
class ReviewWeakness:
    section: str = "General"
    issue: str = ""
    suggestion: str = ""


@dataclass
class ImprovedBullet:
    original: str = ""
    improved: str = ""
    has_placeholders: bool = False
    placeholder_descriptions: dict[str, str] = field(default_factory=dict)
    skipped_placeholders: list[str] = field(default_factory=list)


@dataclass
class ResumeReview:
    overall_score: int = 0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[ReviewWeakness] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    improved_bullets: list[ImprovedBullet] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ResumeReview:
        weaknesses = [
            ReviewWeakness(
                **{
                    k: v
                    for k, v in w.items()
                    if k in ReviewWeakness.__dataclass_fields__
                }
            )
            for w in data.get("weaknesses", [])
        ]
        bullets = [
            ImprovedBullet(
                **{
                    k: v
                    for k, v in b.items()
                    if k in ImprovedBullet.__dataclass_fields__
                }
            )
            for b in data.get("improved_bullets", [])
        ]
        return cls(
            overall_score=data.get("overall_score", 0),
            strengths=data.get("strengths", []),
            weaknesses=weaknesses,
            missing_keywords=data.get("missing_keywords", []),
            improved_bullets=bullets,
        )

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "strengths": self.strengths,
            "weaknesses": [
                {"section": w.section, "issue": w.issue, "suggestion": w.suggestion}
                for w in self.weaknesses
            ],
            "missing_keywords": self.missing_keywords,
            "improved_bullets": [
                {
                    "original": b.original,
                    "improved": b.improved,
                    "has_placeholders": b.has_placeholders,
                }
                for b in self.improved_bullets
            ],
        }


@dataclass
class Identity:
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Identity:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass
class Profile:
    identity: Identity = field(default_factory=Identity)
    base_resume: str = ""
    original_resume: str = ""
    writing_preferences: dict[str, str] = field(default_factory=dict)
    applications_since_review: int = 0
    # Structured work history: {"Company | Title | Dates": {"topic": "answer"}}
    work_history: dict[str, dict[str, str]] = field(default_factory=dict)
    # Immutable facts extracted from resume
    education: list[dict] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    # Legacy flat experience bank — kept for backward compatibility during migration
    experience_bank: dict[str, str] = field(default_factory=dict)
    # Schema version: 1 = flat experience_bank, 2 = structured work_history
    schema_version: int = 1
    history: list[dict] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def needs_migration(self) -> bool:
        """True if profile has old flat experience_bank that needs migration."""
        return self.schema_version < 2 and bool(self.experience_bank)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        identity = Identity.from_dict(data.get("identity", {}))
        return cls(
            identity=identity,
            base_resume=data.get("base_resume", ""),
            original_resume=data.get("original_resume", ""),
            writing_preferences=data.get("writing_preferences", {}),
            applications_since_review=data.get("applications_since_review", 0),
            work_history=data.get("work_history", {}),
            education=data.get("education", []),
            certifications=data.get("certifications", []),
            experience_bank=data.get("experience_bank", {}),
            schema_version=data.get("schema_version", 1),
            history=data.get("history", []),
            preferences=data.get("preferences", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict:
        return {
            "identity": self.identity.to_dict(),
            "base_resume": self.base_resume,
            "original_resume": self.original_resume,
            "writing_preferences": self.writing_preferences,
            "applications_since_review": self.applications_since_review,
            "work_history": self.work_history,
            "education": self.education,
            "certifications": self.certifications,
            "experience_bank": self.experience_bank,
            "schema_version": self.schema_version,
            "history": self.history,
            "preferences": self.preferences,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
