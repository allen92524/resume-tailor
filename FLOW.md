# Resume Tailor — User Flow

This is the single source of truth for the generate command flow.
Code must match this flow exactly. Update this file BEFORE changing code.

## Generate Flow

### Step 1: Resume Input
- If profile exists with a base resume → use it, show "Using profile resume for {name}"
- If no profile → ask user to paste or provide file path
- Supported formats: .txt, .md, .docx, .pdf
- Auto-detect Windows paths and convert to WSL format

### Step 2: Reference Resume (Optional)
- Ask: "Do you have a reference resume from someone in a similar role? (file path or Enter to skip)"
- If provided → parse and hold for later analysis

### Step 3: Resume Review
- Send resume to Claude for standalone quality review
- Show: score, strengths, weaknesses, missing keywords, suggested bullet improvements
- Suggested improvements use [X%] placeholders, never fabricated metrics
- Ask: "Would you like to incorporate these suggestions? (y/n)"
- If yes → improve resume, ask user to fill in placeholders, save to profile

### Step 4: JD Input
- Ask user to paste or provide file path to target job description
- Show word count and detected role, ask to confirm

### Step 5: JD Analysis
- Send JD + reference resume (if provided) to Claude
- Extract: role, company, required skills, preferred skills, keywords, responsibilities

### Step 6: Gap Analysis & Follow-Up Questions
- Compare resume against JD analysis
- Show strengths (what already matches)
- Ask smart questions about gaps — plain English, with examples, max 2 sentences
- Check experience bank for saved answers, reuse with option to update
- Save new answers to experience bank
- Also ask generic questions: additional skills, what to emphasize, preferred title

### Step 7: Compatibility Assessment
- Score 0-100% match
- Show: strong matches, addressable gaps, missing items
- Recommendation on whether to proceed
- If score < 30% → warn user
- Ask: "Proceed with generation? (y/n)"

### Step 8: Generate Tailored Resume
- Send resume + JD analysis + gap answers + reference insights to Claude
- Use [X%] and [number] placeholders, never fabricate metrics
- Ask user to fill in each placeholder with context shown
- Strip % from user input to avoid double %%

### Step 9: Output
- Build DOCX with professional formatting
- Use profile identity for contact info (always override)
- Filename: Name_Company_Role.format (e.g. Jane_Doe_Google_Sr_Platform_Eng.pdf)
- If user chose PDF → convert DOCX to PDF
- Ask: "Also save as PDF/DOCX?" (offer the other format)
- Open file with wslview on WSL
- Save to application history in profile

## CLI Flags
- `--format [docx|pdf|md|all]` — output format (default: docx)
- `--output PATH` — output directory or file path
- `--skip-questions` — skip gap analysis questions
- `--skip-assessment` — skip compatibility score
- `--model MODEL` — LLM model: `claude` (default) or `ollama:<name>`
- `--dry-run` — use mock API responses
- `--resume-session` — reuse last session input
- `--reference PATH` — reference resume file path
- `--verbose` — show debug logging
