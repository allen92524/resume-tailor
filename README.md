[![CI](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml)

# Resume Tailor

**AI-powered CLI tool that generates tailored resumes for each job application.**

Paste your resume and a job description. Resume Tailor analyzes the role, identifies gaps in your experience, scores your fit, and generates an ATS-friendly resume — all from the terminal.

## Demo

```
$ python src/main.py generate

==================================================
  Resume Tailor - AI-Powered Resume Generator
==================================================

Using profile resume for Jane Doe

--- Step 2: Reference Resume (Optional) ---
Do you have a reference resume? (file path or Enter to skip):

--- Step 4: Target Job Description ---
Provide the job description: paste content below, or enter a file path.
/mnt/c/Users/user/Desktop/sr_platform_eng_jd.txt

  Words:    287
  Role:     Senior Platform Engineer
  Company:  Dataflow Inc.
Is this correct? [Y/n]:

--- Step 5: JD Analysis ---
Sending job description to Claude for analysis...
Analysis complete. Role: Senior Platform Engineer
Key skills identified: Python, Go, Kubernetes, distributed systems, CI/CD

--- Step 6: Gap Analysis & Follow-Up Questions ---
Comparing your resume against the job requirements...

Your resume already matches well on:
  - Python backend development
  - Cloud infrastructure (AWS)
  - CI/CD pipeline experience

I have a few questions based on gaps between your resume and the JD.

  Do you have experience with Go or similar systems languages?
  → Built internal CLI tools in Go for deployment automation

  Have you worked with data streaming technologies (Kafka, Kinesis)?
  → Used Kafka for event-driven microservices at Acme Corp

--- Step 7: Compatibility Assessment ---
==================================================
  Compatibility Assessment
==================================================

  Match Score: [████████████████░░░░] 78%

  Strong Matches:
    + Python backend and API development
    + Kubernetes and containerization
    + Mentoring and technical leadership

  Addressable Gaps:
    ~ Go experience (has related systems programming)

Match score: 78%. Proceed with generation? [Y/n]:

--- Step 8: Generating Tailored Resume ---
Generating tailored resume content...
Resume content generated.

--- Step 9: Building PDF ---

Done! Your tailored resume has been saved to:
  /home/user/projects/resume-tailor/output/Jane_Doe_Dataflow_Sr_Platform_Eng.pdf
```

## Features

- **Profile system** — save your resume once, reuse it for every application
- **Smart gap analysis** — identifies what's missing and asks targeted follow-up questions
- **Experience bank** — remembers your answers so you don't repeat yourself
- **Compatibility scoring** — 0-100% match score with detailed breakdown before you commit
- **Resume review** — standalone command to improve your base resume with AI feedback
- **Multi-format output** — DOCX, PDF, and Markdown
- **ATS-friendly formatting** — clean layout, no tables, proper heading structure
- **Multi-profile support** — manage resumes for different people on the same machine
- **Session restore** — re-run with `--resume-session` to try different answers
- **Dry-run mode** — test the full flow without spending API credits

## Quick Start

```bash
# 1. Clone
git clone https://github.com/your-username/resume-tailor.git
cd resume-tailor

# 2. Install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. System dependencies (for PDF output)
sudo apt install libreoffice-writer -y    # Ubuntu/Debian
# brew install --cask libreoffice         # macOS

# 4. Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 5. Run
python src/main.py generate
```

On first run, the tool walks you through creating a profile — paste your resume, review it, and you're set.

## Docker

```bash
# Build
docker build -t resume-tailor .

# Run
docker run -it \
  -e ANTHROPIC_API_KEY="your-key" \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v ~/Desktop:/output \
  resume-tailor generate --format pdf --output /output/

# Or with docker-compose
docker compose run resume-tailor
```

## How It Works

```
Your Resume + Job Description
         │
         ▼
   ┌─────────────┐
   │  JD Analysis │ ← Extract skills, keywords, company context
   └──────┬──────┘
          ▼
   ┌──────────────┐
   │ Gap Analysis  │ ← Find what's missing, ask follow-up questions
   └──────┬───────┘
          ▼
   ┌───────────────────┐
   │ Compatibility Score│ ← 0-100% match with go/no-go recommendation
   └───────┬───────────┘
           ▼
   ┌──────────────────┐
   │ Resume Generation │ ← Tailored content using your answers
   └───────┬──────────┘
           ▼
   DOCX / PDF / Markdown
```

## Commands

| Command | Description |
|---------|-------------|
| `generate` | Full pipeline — analyze JD, score fit, generate tailored resume |
| `review` | Review and improve your base resume with AI suggestions |
| `profile view` | Show your profile summary |
| `profile update` | Update name, email, phone, etc. |
| `profile edit` | Open profile.json in your editor |
| `profile export` | Print profile as markdown |
| `profile backup` | Create a timestamped backup |
| `profile restore` | Restore from a backup |
| `profile reset` | Delete profile and start over |

Key flags: `--format pdf`, `--skip-questions`, `--skip-assessment`, `--resume-session`, `--dry-run`, `--profile <name>`, `--verbose`

See [USAGE.md](USAGE.md) for the complete reference with all flags, workflows, and troubleshooting.

## Project Structure

```
src/
├── main.py                # CLI entry point (click commands)
├── api.py                 # API call helpers with retry logic
├── config.py              # Centralized configuration
├── models.py              # Data models (dataclasses)
├── profile.py             # Profile management (~/.resume-tailor/)
├── session.py             # Session save/restore
├── resume_parser.py       # Parse resume from text/docx/pdf
├── jd_analyzer.py         # Analyze job descriptions
├── gap_analyzer.py        # Compare resume vs JD requirements
├── compatibility_assessor.py  # Score resume-JD match
├── resume_generator.py    # Generate tailored resume content
├── resume_reviewer.py     # Review and improve base resume
├── docx_builder.py        # Build DOCX/PDF/Markdown output
├── prompts.py             # Prompt template loader
└── prompts/               # Prompt templates (Markdown files)
```

## Contributing

```bash
# Install dev dependencies
make dev-install

# Run tests
make test

# Run linter
make lint

# Format code
make format

# Run the tool
make run
```

## License

MIT
