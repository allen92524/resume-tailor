"""Thin loader that reads prompt templates from src/prompts/ and exposes them
as module-level variables so the rest of the codebase is unchanged.

Supports shared rule inclusion via {%SECTION_NAME%} markers that are replaced
with content from shared_rules.md at load time.
"""

import re
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# ---------------------------------------------------------------------------
# Shared rules loader
# ---------------------------------------------------------------------------
_SHARED_RULES: dict[str, str] = {}


def _load_shared_rules() -> dict[str, str]:
    """Parse shared_rules.md into a dict of section_name -> content."""
    path = _PROMPTS_DIR / "shared_rules.md"
    if not path.exists():
        return {}
    text = path.read_text()
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(\S+)", line)
        if m:
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = m.group(1)
            current_lines = []
        else:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()
    return sections


_SHARED_RULES = _load_shared_rules()


def _inject_shared(text: str) -> str:
    """Replace {%SECTION%} markers with content from shared_rules.md."""

    def replacer(m: re.Match) -> str:
        name = m.group(1)
        return _SHARED_RULES.get(name, m.group(0))

    return re.sub(r"\{%(\w+)%\}", replacer, text)


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------


def _load(filename: str) -> tuple[str, ...]:
    """Load a prompt template file split by '---' separators.

    Returns a tuple of stripped sections (system, user, and any extra variants).
    Shared rule markers ({%NAME%}) are expanded before returning.
    """
    text = (_PROMPTS_DIR / filename).read_text()
    sections = text.split("\n---\n")
    return tuple(_inject_shared(s.strip()) for s in sections)


# JD Analysis — has 3 sections: system, user, user_with_reference
_jd = _load("jd_analysis.md")
JD_ANALYSIS_SYSTEM = _jd[0]
JD_ANALYSIS_USER = _jd[1]
JD_ANALYSIS_WITH_REFERENCE_USER = _jd[2]

# Resume Generation
_rg = _load("resume_generation.md")
RESUME_GENERATION_SYSTEM = _rg[0]
RESUME_GENERATION_USER = _rg[1]

# Gap Analysis
_ga = _load("gap_analysis.md")
GAP_ANALYSIS_SYSTEM = _ga[0]
GAP_ANALYSIS_USER = _ga[1]

# Compatibility Assessment
_ca = _load("compatibility_assessment.md")
COMPATIBILITY_ASSESSMENT_SYSTEM = _ca[0]
COMPATIBILITY_ASSESSMENT_USER = _ca[1]

# Resume Review
_rr = _load("resume_review.md")
RESUME_REVIEW_SYSTEM = _rr[0]
RESUME_REVIEW_USER = _rr[1]

# Resume Improve
_ri = _load("resume_improve.md")
RESUME_IMPROVE_SYSTEM = _ri[0]
RESUME_IMPROVE_USER = _ri[1]

# Resume Enrich (enrichment analysis)
_re_enrich = _load("resume_enrich.md")
RESUME_ENRICH_SYSTEM = _re_enrich[0]
RESUME_ENRICH_USER = _re_enrich[1]

# Resume Improve (enrichment variant — no placeholders)
_rie = _load("resume_improve_enriched.md")
RESUME_IMPROVE_ENRICHED_SYSTEM = _rie[0]
RESUME_IMPROVE_ENRICHED_USER = _rie[1]

# Contact Extraction
_ce = _load("contact_extraction.md")
CONTACT_EXTRACTION_SYSTEM = _ce[0]
CONTACT_EXTRACTION_USER = _ce[1]

# Conversational Follow-up
_cf = _load("conversational_followup.md")
CONVERSATIONAL_FOLLOWUP_SYSTEM = _cf[0]
CONVERSATIONAL_FOLLOWUP_USER = _cf[1]

# Single Bullet Improvement
_bi = _load("bullet_improve_single.md")
BULLET_IMPROVE_SINGLE_SYSTEM = _bi[0]
BULLET_IMPROVE_SINGLE_USER = _bi[1]

# Conflict Check
_cc = _load("conflict_check.md")
CONFLICT_CHECK_SYSTEM = _cc[0]
CONFLICT_CHECK_USER = _cc[1]

# Experience Bank Matching
_ebm = _load("experience_bank_match.md")
EXPERIENCE_BANK_MATCH_SYSTEM = _ebm[0]
EXPERIENCE_BANK_MATCH_USER = _ebm[1]

# Extract JD from web page
_ej = _load("extract_jd.md")
EXTRACT_JD_SYSTEM = _ej[0]
EXTRACT_JD_USER = _ej[1]

# Extract resume from web page
_er = _load("extract_resume.md")
EXTRACT_RESUME_SYSTEM = _er[0]
EXTRACT_RESUME_USER = _er[1]

# Experience synthesis (combine related entries for a gap skill)
_es = _load("experience_synthesize.md")
EXPERIENCE_SYNTHESIZE_SYSTEM = _es[0]
EXPERIENCE_SYNTHESIZE_USER = _es[1]

# Migration: extract education and certifications from resume
_mef = _load("migrate_extract_facts.md")
MIGRATE_EXTRACT_FACTS_SYSTEM = _mef[0]
MIGRATE_EXTRACT_FACTS_USER = _mef[1]

# Migration: group flat experience bank entries by work role
_mge = _load("migrate_group_experience.md")
MIGRATE_GROUP_EXPERIENCE_SYSTEM = _mge[0]
MIGRATE_GROUP_EXPERIENCE_USER = _mge[1]
