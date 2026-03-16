# Resume Tailor — User Flow

This is the single source of truth for the generate command flow.
Code must match this flow exactly. Update this file BEFORE changing code.

## Generate Flow

### Step 1: Model Selection
- First thing the user sees, before any LLM calls
- If `--model` flag provided → use it (e.g. `claude`, `claude:sonnet`, `claude:opus`, `ollama:gemma3`)
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
  - Enrich resume via LLM: detect profession/industry, identify strengths, find information gaps
  - Show detected profession and strengths
  - Walk through enrichment questions — targeted Q&A about missing facts (team size, metrics, scope, achievements)
  - Questions ask for FACTS the candidate knows, not quality judgments
  - Most recent role first, profession-appropriate examples (e.g. "e.g. 5, 10, 20+" not "e.g. 99.9% uptime")
  - Use user's real answers to improve resume — no placeholders needed
  - Never change education, certifications, job titles, or dates without explicit confirmation
  - Show improved resume and get confirmation before saving
  - Save improved version as `base_resume`, original stays as `original_resume`
  - Save raw answers to experience bank for future reuse
  - Extract contact info via LLM
  - Save profile

### Step 2b: Periodic Experience Bank Review (returning users)
- If `applications_since_review >= 10`:
  - Offer experience bank review: keep, update, or delete each saved answer
  - If user made any edits → run conflict check (1 LLM call) to detect contradictions
  - If conflicts found → walk user through each one with clarifying questions
  - Reset counter
- Note: Baseline resume refresh is handled by Step 3b ("anything new?"), not here.
  This avoids redundant re-enrichment of an already-improved resume.

### Step 3: Resume Input
- If profile has a base resume → use it, show "Using profile resume for {name}" with a tip to run `profile` command
- If no profile resume → ask user to paste or provide file path
- Supported formats: .txt, .md, .docx, .pdf
- Auto-detect Windows paths and convert to WSL format

### Step 3b: Returning User Check
- If profile exists, ask: "Anything new since your last application? New skills, projects, certifications?"
- If yes → update `base_resume` via LLM, save new info to experience bank
- After save → run conflict check (1 LLM call) to detect contradictions
- If conflicts found → walk user through each one with clarifying questions
- If no → proceed with existing baseline

### Step 4: Reference Resume (Optional)
- Ask: "Do you have a reference resume from someone in a similar role? (file path or Enter to skip)"
- If provided → parse and hold for later analysis

### Step 5: JD Input
- Ask user to paste or provide file path to target job description
- Show word count and detected role, ask to confirm

### Step 6: JD Analysis
- Send JD + reference resume (if provided) to LLM
- Extract: role, company, required skills, preferred skills, keywords, responsibilities

### Step 7: Gap Analysis & Follow-Up Questions
- Compare resume against JD analysis
- Show strengths (what already matches)
- **Semantic experience bank matching** (1 batch LLM call):
  - Send all gap skills + experience bank to LLM in ONE call
  - LLM returns which experience bank entries are relevant to each gap
  - Matches by meaning, not just exact name (e.g. "AI coding tools" matches "GitHub Copilot experience")
  - Falls back to exact matching if LLM call fails
- For each gap with a matching experience bank entry:
  - Show saved answer, offer to reuse, update, or skip
- For gaps with no match:
  - Ask smart questions — ordered by importance to the JD
  - Question style: simple, concrete with profession-appropriate examples
  - Smart follow-up on "No" answers: suggest adjacent skills
- Save new answers to experience bank
- After all new answers saved → run conflict check (1 LLM call)
- If conflicts found → walk user through each one with clarifying questions
- Also ask generic questions: additional skills, what to emphasize, preferred title

### Step 8: Compatibility Assessment
- Score 0-100% match using resume + JD analysis + gap answers
- Gap answers are included so the score reflects what the user told us
  (without this, skills like "AI coding tools" appear as "Missing" even
  after the user confirmed having experience)
- Show: strong matches, addressable gaps, missing items
- Recommendation on whether to proceed
- If score < 30% → warn user
- Ask: "Proceed with generation? (y/n)"

### Step 8b: Writing Preferences (first run only)
- If no writing preferences saved in profile → ask upfront:
  - Preferred tone (professional, conversational, technical)
  - Bullet style (concise, detailed, quantified)
  - Any other preferences
- Save to profile — only asked once, reused for all future generations
- If preferences already exist → skip this step

### Step 9: Generate Tailored Resume
- Send resume + JD analysis + gap answers + reference insights + writing preferences to LLM
- Career growth rules: different language per role seniority, no verb repetition, timeline-aware terminology
- Use [X%] and [number] placeholders, never fabricate metrics
- Ask user to fill in each placeholder with context shown
- Strip % from user input to avoid double %%

### Step 9b: Preview Generated Resume
- Show generated resume section by section (summary, experience, skills)
- Read-only preview — no feedback loop
- Writing preferences are already applied from Step 8b

### Step 10: Output
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
- `profile edit` — interactive editor (resume, contact info, or raw JSON)
- `profile export` — export as markdown
- `profile backup` — create timestamped backup
- `profile restore` — restore from backup
