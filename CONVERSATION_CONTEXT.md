# Conversation Context for Claude Code

This file summarizes key decisions and context from the development conversation.
Claude Code should read this to understand the project history and design philosophy.

## Core Philosophy
- Always ask users questions before making changes — never assume
- One question at a time, simple language, give examples
- When user says "I don't know", help them discover the answer from a different angle
- Confirm before saving — show what will change and get approval
- Never fabricate metrics, dates, education, or certifications
- Career growth should show progression in verbs and industry-relevant terminology
- Tool should work for ANY career field, not just engineering

## Key Design Decisions
1. **Original resume preserved** — stored as `original_resume` in profile, never modified
2. **Base resume** — improved version through user-confirmed Q&A, used for all generations
3. **Experience bank** — LLM-managed knowledge base, user never directly edits text (see #19)
4. **Writing preferences** — captured upfront before generation, saved to profile (see #17)
5. **Model selection first** — before any LLM call, user picks Claude API or Ollama
6. **Profile identity overrides LLM output** — contact info always from profile, never from generation
7. **No placeholders in generation** — generation prompt must never produce [X%] or [number]
8. **Industry timeline awareness** — use terminology appropriate to each role's time period
9. **Smart follow-up on "No"** — suggest adjacent skills before accepting No
10. **Docker = Claude API only** — Ollama (local models) is only for local installs, never inside Docker. LLM models are too large for containers (huge images, slow pulls, heavy resources). `docker-compose.full.yml` was removed.
11. **Enrichment-first onboarding** — new users get targeted questions about missing facts (team size, metrics, scope) BEFORE any resume improvement. The LLM detects profession/industry first, ensuring questions and examples are role-appropriate. No placeholders needed since real data is gathered upfront. Replaces the old review-first flow that generated placeholder-stuffed bullets and engineering-biased suggestions.
12. **Profession-neutral prompts** — all prompts detect the candidate's profession before generating feedback. Metric types, keyword suggestions, and examples must match the candidate's actual field, not default to software engineering.
13. **Conflict resolution updates source data** — when conflicts are found between resume and experience bank, resolved answers update the original entries in place (not stacked as clarification entries). If the conflict involves resume text, the resume is auto-corrected. Conflict check includes today's date to avoid false timeline flags.
14. **Conversational Q&A everywhere** — all user-facing questions (gap analysis, conflict resolution, enrichment) use the `conversational_qa` engine with follow-up questions, not plain `click.prompt`. This helps users who give vague or incomplete answers.
15. **Unified Step 7 analysis** — replaced separate gap analysis + semantic matching + synthesis with ONE unified LLM call that sees resume + work history + JD together. Returns strengths, gaps, conflicts, and prioritized questions in one pass. Gaps and conflicts mixed naturally in one conversational flow.
16. **Step 8 sees gap answers** — compatibility assessment receives `user_additions` (gap answers) so the score reflects what the user told us, not just what's on the resume.
17. **Writing preferences asked once** — collected upfront before generation, saved to profile. No section-by-section review loop. Users can update via `profile edit`.
18. **No redundant re-enrichment** — periodic maintenance (every 10 apps) only reviews the experience bank, not re-enrichment of the already-improved resume. Step 3b ("anything new?") handles resume updates.
19. **LLM-managed structured work history** — replaced flat `experience_bank` with `work_history` grouped by `"Company | Title | Dates"`. Added `education` (list) and `certifications` (list) as immutable facts. Users never directly edit work history — all changes go through conversational Q&A. Existing profiles auto-migrate on first `generate` (LLM groups entries by role, extracts education/certs from resume, auto-backup before migration).
20. **MCP integration (Model Context Protocol)** — URL fetching for JD input (Step 5) and reference resumes (Step 4) via `mcp-server-fetch`. Optional Brave Search for company research (Step 7, needs `BRAVE_API_KEY`). Most JS-rendered job sites (LinkedIn, Greenhouse, etc.) fail gracefully with fallback to manual paste.
21. **URL extraction validation** — fetched pages are truncated to 30K chars before LLM processing. LLM responses are checked for apology/failure signals and minimum word count (150+ words for a real JD) to prevent showing error messages as job descriptions.

## Known Issues to Watch
- Local Ollama models produce lower quality output than Claude API
- JSON parsing from Ollama needs repair logic and JSON mode
- Branch protection blocks direct pushes — use PR workflow
- Auto-release uses tags via GitHub API, not commits to main
- Docker path conversion needed for file access inside containers
- Most job board URLs (LinkedIn, Greenhouse, Ashby, Lever) are JS-rendered and fail MCP fetch — users must paste JD manually for these sites
- Chinese translations (README_CN.md, USAGE_CN.md) need updating with recent features

## Testing Requirements
- Run `make lint` and `make test` before every commit
- 527+ tests must pass
- Test with real Docker containers, not just mocked unit tests
- Test on different machines (WSL, Mac) to catch platform issues
- Use E2E_CHECKLIST.md for manual testing before releases

## Git Workflow
- Feature branch → PR → squash merge → auto tag + release
- Commit messages: `feat:` for features, `fix:` for fixes, `docs:` for docs
- Never commit personal info — pre-commit hook checks for this
