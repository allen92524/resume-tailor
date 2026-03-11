[![CI](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml)

[English](README.md) | [中文](README_CN.md)

# Resume Tailor

**Turn any job posting into a tailored resume in 5 minutes.**

You have one resume. Every job is different. Resume Tailor reads the job description, figures out what matters, asks you a few questions, and generates a polished, ATS-friendly resume — as DOCX, PDF, or Markdown.

Works with the Claude API (best quality) or free local models via Ollama (no account needed).

## How It Works

```
Your Resume + Job Description
         │
         ▼
   ┌─────────────┐
   │  JD Analysis │ ← Extracts skills, keywords, what the company cares about
   └──────┬──────┘
          ▼
   ┌──────────────┐
   │ Gap Analysis  │ ← Finds what's missing, asks you targeted questions
   └──────┬───────┘
          ▼
   ┌───────────────────┐
   │ Compatibility Score│ ← Shows 0-100% match before you commit
   └───────┬───────────┘
           ▼
   ┌──────────────────┐
   │ Resume Generation │ ← Writes tailored content using your real experience
   └───────┬──────────┘
           ▼
   DOCX / PDF / Markdown
```

## Quick Start

Pick **one** of the three options below. Option B is easiest if you don't want to pay for an API key.

---

### Option A: Docker + Claude API (best quality)

Claude gives the best resume output. You need an API key ($0.01-0.05 per resume).

**1. Get an API key** (takes 1 minute)

Go to https://console.anthropic.com/settings/keys → create a key → copy it. It starts with `sk-ant-`.

**2. Clone and build**

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor
docker build -t resume-tailor .
```

**3. Generate your first resume**

```bash
# Linux / macOS
docker run -it \
  -e ANTHROPIC_API_KEY="sk-ant-your-key-here" \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --format pdf --output /output/

# Windows (PowerShell)
docker run -it `
  -e ANTHROPIC_API_KEY="sk-ant-your-key-here" `
  -v $env:USERPROFILE\.resume-tailor:/root/.resume-tailor `
  -v ${PWD}\output:/output `
  resume-tailor generate --format pdf --output /output/
```

The tool walks you through it: paste your resume, paste the job description, answer a few questions, get your tailored resume.

---

### Option B: Docker + Ollama (free, runs locally)

No API key, no account, no cost. Everything runs on your machine. Requires ~4 GB of RAM.

**1. Clone and start**

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor

# Start the Ollama container (downloads ~2 GB on first run)
docker compose -f docker-compose.full.yml up -d ollama
```

**2. Download a model** (one-time, ~2 GB)

```bash
docker compose -f docker-compose.full.yml exec ollama ollama pull qwen3.5
```

**3. Generate your first resume**

```bash
docker compose -f docker-compose.full.yml run --rm resume-tailor
```

---

### Accessing local files in Docker

When running with Docker (Options A or B), your **Downloads**, **Desktop**, and **Documents** folders are automatically mounted read-only into the container. You can reference files using their original paths — they're converted automatically:

```
~/Downloads/resume.pdf       → /mnt/downloads/resume.pdf
~/Documents/my_resume.docx   → /mnt/documents/my_resume.docx
~/Desktop/job_posting.txt    → /mnt/desktop/job_posting.txt
```

You can also place files in the `input/` folder in the project directory — they'll be available at `/mnt/input/` inside the container.

---

### Option C: Install locally (no Docker)

Best if you want to hack on the code or avoid Docker.

**1. Clone and install**

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Install LibreOffice** (only needed for PDF output)

```bash
# Ubuntu / Debian
sudo apt install libreoffice-writer -y

# macOS
brew install --cask libreoffice

# Windows — download from https://www.libreoffice.org/download/
# Or just use --format docx to skip this step
```

**3. Set up your AI backend**

```bash
# Option 1: Claude API (best quality)
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
python src/main.py generate

# Option 2: Ollama (free, local)
# Install Ollama: https://ollama.com/download
ollama pull qwen3.5
python src/main.py generate --model ollama:qwen3.5
```

---

## What Your First Run Looks Like

```
$ python src/main.py generate

==================================================
  Resume Tailor - AI-Powered Resume Generator
==================================================

Using profile resume for Jane Doe

--- Step 4: Target Job Description ---
Provide the job description: paste content below, or enter a file path.
/path/to/job_posting.txt

  Words:    287
  Role:     Senior Platform Engineer
  Company:  Dataflow Inc.
Is this correct? [Y/n]:

--- Step 5: JD Analysis ---
Analysis complete. Role: Senior Platform Engineer
Key skills identified: Python, Go, Kubernetes, distributed systems, CI/CD

--- Step 6: Gap Analysis & Follow-Up Questions ---
Your resume already matches well on:
  - Python backend development
  - Cloud infrastructure (AWS)
  - CI/CD pipeline experience

I have a few questions based on gaps between your resume and the JD.

  Do you have experience with Go or similar systems languages?
  → Built internal CLI tools in Go for deployment automation

--- Step 7: Compatibility Assessment ---
  Match Score: [████████████████░░░░] 78%

  Strong Matches:
    + Python backend and API development
    + Kubernetes and containerization

Match score: 78%. Proceed with generation? [Y/n]:

--- Step 8: Generating Tailored Resume ---
Resume content generated.

Done! Your tailored resume has been saved to:
  output/Jane_Doe_Dataflow_Sr_Platform_Eng.pdf
```

## Features

- **Save your resume once, reuse everywhere** — profile system remembers your resume and contact info
- **Smart gap analysis** — AI identifies what's missing and asks targeted questions
- **Experience bank** — remembers your answers so you never re-type the same thing
- **Match score** — see a 0-100% compatibility score before you commit to generating
- **Resume review** — standalone command to improve your base resume with AI feedback
- **Multi-format** — output as DOCX, PDF, or Markdown
- **ATS-friendly** — clean formatting that passes automated screening systems
- **Multi-profile** — manage resumes for different people on the same machine
- **Session restore** — re-run with `--resume-session` to try different answers
- **Dry-run mode** — test the full flow without using API credits
- **Local or cloud AI** — use Claude API or free local Ollama models

## Commands

| Command | What it does |
|---------|-------------|
| `generate` | Full pipeline: analyze job posting, score your fit, generate tailored resume |
| `review` | Get AI feedback on your base resume and apply improvements |
| `profile view` | See what's in your profile |
| `profile update` | Change your name, email, phone, etc. |
| `profile edit` | Open your profile in a text editor |
| `profile export` | Print your profile as readable text |
| `profile backup` | Save a backup copy of your profile |
| `profile restore` | Restore a previous backup |
| `profile reset` | Delete your profile and start fresh |

### Key Flags

| Flag | Works with | What it does |
|------|-----------|-------------|
| `--format pdf` | `generate` | Output as PDF (also: `docx`, `md`, `all`) |
| `--model ollama:qwen3.5` | `generate`, `review` | Use a local model instead of Claude |
| `--skip-questions` | `generate` | Skip the follow-up questions |
| `--skip-assessment` | `generate` | Skip the compatibility score |
| `--resume-session` | `generate` | Reuse inputs from your last run |
| `--dry-run` | `generate` | Test without calling any AI |
| `--profile wife` | any | Use a different profile |
| `--verbose` | any | Show detailed logs |

See [USAGE.md](USAGE.md) for the complete reference with all flags, workflows, and troubleshooting.

## REST API

Resume Tailor also runs as a web API for programmatic access.

```bash
# Start the server
make api

# Health check
curl http://localhost:8000/api/v1/health

# Generate a resume
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer..."}'
```

API docs at http://localhost:8000/docs (interactive Swagger UI).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/analyze-jd` | Analyze a job description |
| `POST` | `/api/v1/assess-compatibility` | Score resume vs job match (0-100%) |
| `POST` | `/api/v1/generate` | Generate tailored resume (JSON) |
| `POST` | `/api/v1/generate/pdf` | Generate and download as PDF |
| `POST` | `/api/v1/review` | Review resume with AI feedback |

## Supported Ollama Models

Any Ollama model works. Some popular choices:

| Model | Flag | Notes |
|-------|------|-------|
| Qwen 3.5 | `--model ollama:qwen3.5` | Good all-around, recommended |
| Devstral | `--model ollama:devstral` | Strong at technical resumes |
| Gemma 3 | `--model ollama:gemma3` | Lightweight option |

## Privacy

Resume Tailor stores all data locally on your machine:

- **Profiles** are saved to `~/.resume-tailor/` (or `$HOME/.resume-tailor/` in Docker). They never leave your machine.
- **Generated resumes** are written to the `output/` directory. Nothing is uploaded anywhere.
- **API calls** send your resume text and job description to the LLM provider (Anthropic or your local Ollama). If you use Ollama, all processing stays on your machine.
- **Git safety** — a pre-commit hook scans for emails, phone numbers, and LinkedIn URLs to prevent accidental commits of personal info. Run `make check-secrets` to scan the full repo anytime.

To enable the pre-commit hook:

```bash
git config core.hooksPath .githooks
```

## Contributing

```bash
make dev-install   # Install dev dependencies
make test          # Run tests
make lint          # Run linter
make format        # Format code
make check-secrets # Scan repo for personal info patterns
```

## License

MIT
