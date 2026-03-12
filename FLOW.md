# Resume Tailor — User Flow

This is the single source of truth for the generate command flow.
Code must match this flow exactly. Update this file BEFORE changing code.

## Generate Flow

### Step 1: Model Selection
- First thing the user sees, before any LLM calls
- If `--model` flag provided → use it (e.g. `claude`, `claude:sonnet`, `claude:opus`, `ollama:qwen3.5`)
- If `--dry-run` → use default model with mock responses
- Otherwise → show interactive menu (auto-detects Claude API key and Ollama models)
  - If user selects Claude → show sub-menu for variant: Haiku (fast/cheap), Sonnet (balanced, default), Opus (most capable)
  - Selected variant saved to profile preferences as `claude:<variant>`
- Validate/prepare the chosen backend (API key check or Ollama readiness)
- Every LLM call logs: "Calling {model_name} for {purpose}..."
- Selected model is used for ALL subsequent LLM calls including profile setup

### Step 2: Profile Setup
- If profile exists with a base resume → use it
- If no profile → first-run setup using the selected model:
  - Collect base resume (paste or file path)
  - Save as `original_resume` (never modified after this)
  - Review resume via LLM, show score/suggestions
  - Walk through each weakness with targeted Q&A (simple, concrete questions with examples)
  - Use user's answers to improve specific bullets — only change what user confirmed
  - Never change education, certifications, job titles, or dates without explicit confirmation
  - Show improved resume and get confirmation before saving
  - Save improved version as `base_resume`, original stays as `original_resume`
  - Save raw answers to experience bank for future reuse
  - Extract contact info via LLM
  - Save profile

### Step 2b: Periodic Maintenance (returning users)
- If `applications_since_review >= 10`:
  - Ask: "Want to review your baseline resume?"
  - If yes → run review with Q&A, update `base_resume`, reset counter
  - Also offer experience bank review: keep, update, or delete each saved answer

### Step 3: Resume Input
- If profile has a base resume → use it, show "Using profile resume for {name}" with a tip to run `profile` command
- If no profile resume → ask user to paste or provide file path
- Supported formats: .txt, .md, .docx, .pdf
- Auto-detect Windows paths and convert to WSL format

### Step 3b: Returning User Check
- If profile exists, ask: "Anything new since your last application? New skills, projects, certifications?"
- If yes → update `base_resume` via LLM, save new info to experience bank
- If no → proceed with existing baseline

### Step 4: Reference Resume (Optional)
- Ask: "Do you have a reference resume from someone in a similar role? (file path or Enter to skip)"
- If provided → parse and hold for later analysis

### Step 5: Resume Review (first-time only)
- Send resume to LLM for standalone quality review
- Show: score, strengths, weaknesses, missing keywords, suggested bullet improvements
- Walk through each weakness with targeted Q&A (not "incorporate suggestions? y/n")
- Question style: simple, concrete with examples (e.g. "How many servers? e.g. 30, 100, 500+")
- Most recent role first, work backwards
- Build on previous answers — don't re-ask
- Ask prerequisites first if questions have dependencies
- Use user's answers to improve specific bullets — only change what user confirmed
- Never change education, certifications, job titles, or dates
- Save each raw answer to experience bank
- Show improved resume preview and get confirmation before saving

### Step 6: JD Input
- Ask user to paste or provide file path to target job description
- Show word count and detected role, ask to confirm

### Step 7: JD Analysis
- Send JD + reference resume (if provided) to LLM
- Extract: role, company, required skills, preferred skills, keywords, responsibilities

### Step 8: Gap Analysis & Follow-Up Questions
- Compare resume against JD analysis
- Show strengths (what already matches)
- Ask smart questions about gaps — ordered by importance to the JD
- Question style: simple, concrete with examples, matching Step 5 style
- Build on what user already answered in Step 5 and experience bank — don't re-ask
- Check experience bank for saved answers, reuse with option to update
- Smart follow-up on "No" answers: suggest adjacent skills (e.g. "Even related experience counts. For example: Docker, ECS/Fargate, container orchestration. Have you done anything like that?")
- If user still says no → save "No" and move on
- If user gives a partial answer → save it
- Save new answers to experience bank
- Also ask generic questions: additional skills, what to emphasize, preferred title

### Step 9: Compatibility Assessment
- Score 0-100% match
- Show: strong matches, addressable gaps, missing items
- Recommendation on whether to proceed
- If score < 30% → warn user
- Ask: "Proceed with generation? (y/n)"

### Step 10: Generate Tailored Resume
- Send resume + JD analysis + gap answers + reference insights + writing preferences to LLM
- Career growth rules: different language per role seniority, no verb repetition, timeline-aware terminology
- Use [X%] and [number] placeholders, never fabricate metrics
- Ask user to fill in each placeholder with context shown
- Strip % from user input to avoid double %%

### Step 10b: Section-by-Section Review
- Show generated resume section by section (summary, experience, skills)
- For each section ask: "Looks good? (Enter to accept, or type feedback)"
- Capture writing style preferences from feedback (e.g. "too formal", "shorter bullets")
- Save writing preferences to profile for all future generations

### Step 11: Output
- Build DOCX with professional formatting
- Use profile identity for contact info (always override)
- Filename: Name_Company_Role.format (e.g. Jane_Doe_Google_Sr_Platform_Eng.pdf)
- If user chose PDF → convert DOCX to PDF
- Ask: "Also save as PDF/DOCX?" (offer the other format)
- Open file with wslview on WSL
- Save to application history in profile
- Increment `applications_since_review` counter

## Profile Structure
```json
{
  "identity": { "name", "email", "phone", "location", "linkedin", "github" },
  "base_resume": "improved version, updated through user-confirmed changes only",
  "original_resume": "first uploaded resume, never modified",
  "writing_preferences": { "tone": "...", "bullet_length": "...", ... },
  "applications_since_review": 0,
  "experience_bank": { "skill": "saved answer" },
  "history": [{ "date", "company", "role", "match_score", "output_file" }],
  "preferences": { "format", "output_path", "model" },
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp"
}
```

## CLI Flags
- `--format [docx|pdf|md|all]` — output format (default: docx)
- `--output PATH` — output directory or file path
- `--skip-questions` — skip gap analysis questions
- `--skip-assessment` — skip compatibility score
- `--model MODEL` — LLM model: `claude` (default), `claude:haiku`, `claude:sonnet`, `claude:opus`, or `ollama:<name>`
- `--dry-run` — use mock API responses
- `--resume-session` — reuse last session input
- `--reference PATH` — reference resume file path
- `--verbose` — show debug logging

## Profile Commands
- `profile view` — show full profile summary
- `profile update` — interactively update identity fields
- `profile reset` — delete profile and start over
- `profile reset-baseline` — revert base_resume back to original_resume
- `profile edit` — open profile.json in editor
- `profile export` — export as markdown
- `profile backup` — create timestamped backup
- `profile restore` — restore from backup
