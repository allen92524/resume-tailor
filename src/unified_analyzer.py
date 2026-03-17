"""Unified analysis: compare candidate profile against JD in one LLM call.

Replaces the separate gap analysis + experience bank matching + synthesis
calls with a single unified call that sees resume + work history + JD together.
Returns strengths, gaps, conflicts, and prioritized questions in one pass.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date

from .api import parse_json_response
from .config import DEFAULT_MODEL, MAX_TOKENS_UNIFIED_ANALYSIS
from .llm_client import call_llm
from .models import JDAnalysis, Profile
from .profile import format_work_history_text
from .prompts import UNIFIED_ANALYSIS_SYSTEM, UNIFIED_ANALYSIS_USER

logger = logging.getLogger(__name__)


@dataclass
class UnifiedQuestion:
    """A question from the unified analysis — either a gap or a conflict."""

    skill: str = ""
    question: str = ""
    type: str = "gap"  # "gap" or "conflict"
    context: str = ""
    suggested_role: str = "General"


@dataclass
class UnifiedAnalysis:
    """Result of the unified analysis."""

    strengths: list[str] = field(default_factory=list)
    questions: list[UnifiedQuestion] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedAnalysis":
        questions = [
            UnifiedQuestion(
                skill=q.get("skill", ""),
                question=q.get("question", ""),
                type=q.get("type", "gap"),
                context=q.get("context", ""),
                suggested_role=q.get("suggested_role", "General"),
            )
            for q in data.get("questions", [])
        ]
        return cls(
            strengths=data.get("strengths", []),
            questions=questions,
        )


def unified_analysis(
    profile: Profile,
    jd_analysis: JDAnalysis,
    model: str = DEFAULT_MODEL,
) -> UnifiedAnalysis:
    """Run unified analysis: compare full profile against JD in one LLM call.

    Sends resume + structured work history + education + certifications + JD
    analysis to the LLM. Returns strengths, gaps, conflicts, and questions.
    """
    logger.info("Running unified analysis")

    # Format work history
    wh_text = format_work_history_text(profile)
    if not wh_text:
        wh_text = "(No work history entries yet)"

    # Format education
    edu_text = "\n".join(
        f"- {e.get('degree', '')} — {e.get('school', '')} ({e.get('year', '')})"
        for e in profile.education
    ) if profile.education else "(None)"

    # Format certifications
    cert_text = ", ".join(profile.certifications) if profile.certifications else "(None)"

    # Build explicit list of already-answered topics
    answered = []
    for role, entries in profile.work_history.items():
        for skill in entries:
            if skill:  # skip empty keys
                answered.append(f"- {skill} (role: {role})")
    answered_text = "\n".join(answered) if answered else "(None yet)"

    response_text = call_llm(
        model=model,
        max_tokens=MAX_TOKENS_UNIFIED_ANALYSIS,
        system=UNIFIED_ANALYSIS_SYSTEM,
        user_content=UNIFIED_ANALYSIS_USER.format(
            resume_text=profile.base_resume,
            work_history=wh_text,
            education=edu_text,
            certifications=cert_text,
            jd_analysis=json.dumps(jd_analysis.to_dict(), indent=2),
            answered_topics=answered_text,
            today=date.today().strftime("%B %d, %Y"),
        ),
        purpose="unified analysis",
    )

    try:
        data = parse_json_response(response_text)
    except Exception:
        logger.warning(
            "Failed to parse unified analysis response. Raw:\n%s", response_text
        )
        raise

    return UnifiedAnalysis.from_dict(data)
