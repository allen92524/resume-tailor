# Prompt Templates

Overview of all prompt templates, when each fires, and how they connect in the generation flow.

## Flow

```
User provides resume + JD
        │
        ▼
  jd_analysis.md          ← Analyze JD, extract requirements + company context
        │
        ▼
  gap_analysis.md          ← Compare resume vs JD, surface gaps and strengths
        │
        ▼
  (user answers gap questions)
        │
        ▼
  compatibility_assessment.md  ← Score how well the resume matches the JD
        │
        ▼
  resume_generation.md     ← Generate tailored resume content
```

Standalone flows (not part of the main generate pipeline):

```
  resume_review.md         ← Review a resume for quality (used by `review` command)
        │
        ▼
  resume_improve.md        ← Rewrite resume incorporating review feedback
```

```
  contact_extraction.md    ← Extract name/email/phone from resume text (used by profile save)
```

## Prompt Files

| File | Purpose | Key Inputs | Output |
|------|---------|------------|--------|
| `jd_analysis.md` | Extract structured requirements, keywords, and company context from a job description | JD text, optional reference resume | JSON with skills, responsibilities, keywords, company_context, style_insights |
| `resume_generation.md` | Generate a tailored resume matching the target JD | Original resume, JD analysis, user additions | JSON with full resume structure |
| `gap_analysis.md` | Identify skill gaps and strengths between resume and JD | Original resume, JD analysis | JSON with gaps (questions) and strengths |
| `compatibility_assessment.md` | Score resume-to-JD fit from a recruiter's perspective | Original resume, JD analysis | JSON with match_score, matches, gaps, recommendation |
| `resume_review.md` | Review resume quality, suggest improvements | Resume text | JSON with score, weaknesses, improved_bullets |
| `resume_improve.md` | Rewrite resume incorporating review feedback | Resume text, review JSON | Plain text improved resume |
| `contact_extraction.md` | Parse contact info from resume text | Resume text | JSON with name, email, phone, etc. |

## Shared Rules

`shared_rules.md` contains reusable rule blocks referenced by multiple prompts via `{%SECTION_NAME%}` markers:

| Section | Used By | Description |
|---------|---------|-------------|
| `TRUTHFULNESS` | resume_generation, resume_improve, gap_analysis | Never fabricate experience or skills |
| `METRICS_NO_PLACEHOLDERS` | resume_generation | Preserve real metrics, never use [X%] placeholders |
| `METRICS_WITH_PLACEHOLDERS` | resume_review, resume_improve | Preserve real metrics, use [X%] placeholders for missing ones |
| `DATES` | resume_generation | Never modify employment dates |

## Editing Prompts

Each prompt file uses `---` separators to split sections:
- **Section 1**: System prompt (persona and role)
- **Section 2**: User prompt template (with `{placeholder}` variables for runtime data)
- **Section 3+** (optional): Variant user prompts (e.g., jd_analysis has a reference-resume variant)

To reference shared rules, use `{%SECTION_NAME%}` in any prompt section. The loader replaces these with content from `shared_rules.md` at load time.

Format placeholders use single braces `{variable}` and are filled at runtime via Python `.format()`. Use double braces `{{` / `}}` for literal braces in JSON templates.
