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
3. **Experience bank** — raw user answers reused across applications
4. **Writing preferences** — captured from user feedback during output review
5. **Model selection first** — before any LLM call, user picks Claude API or Ollama
6. **Profile identity overrides LLM output** — contact info always from profile, never from generation
7. **No placeholders in generation** — generation prompt must never produce [X%] or [number]
8. **Industry timeline awareness** — use terminology appropriate to each role's time period
9. **Smart follow-up on "No"** — suggest adjacent skills before accepting No
10. **Docker = Claude API only** — Ollama (local models) is only for local installs, never inside Docker. LLM models are too large for containers (huge images, slow pulls, heavy resources). `docker-compose.full.yml` was removed.

## Known Issues to Watch
- Local Ollama models produce lower quality output than Claude API
- JSON parsing from Ollama needs repair logic and JSON mode
- Branch protection blocks direct pushes — use PR workflow
- Auto-release uses tags via GitHub API, not commits to main
- Docker path conversion needed for file access inside containers

## Testing Requirements
- Run `make lint` and `make test` before every commit
- 476+ tests must pass
- Test with real Docker containers, not just mocked unit tests
- Test on different machines (WSL, Mac) to catch platform issues
- Use E2E_CHECKLIST.md for manual testing before releases

## Git Workflow
- Feature branch → PR → squash merge → auto tag + release
- Commit messages: `feat:` for features, `fix:` for fixes, `docs:` for docs
- Never commit personal info — pre-commit hook checks for this
