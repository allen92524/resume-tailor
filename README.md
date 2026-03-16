[![CI](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/allen92524/resume-tailor/actions/workflows/ci.yml)

[English](README.md) | [中文](README_CN.md)

# Resume Tailor

**Turn any job posting into a tailored resume in 5 minutes.**

You have one resume. Every job is different. Resume Tailor reads the job description, figures out what matters, asks you a few questions, and generates a polished resume — as DOCX, PDF, or Markdown.

## What You Need

- **Docker** ([download here](https://www.docker.com/products/docker-desktop/)) — recommended, nothing else to install
- **An AI backend** (pick one):
  - **Claude API** (best quality, ~$0.01-0.05 per resume) — [get an API key](https://console.anthropic.com/settings/keys)
  - **Ollama** (free, runs on your computer) — [install here](https://ollama.com/download)
- **Optional:** Brave Search API key for company research — [free tier, 2,000 searches/month](https://brave.com/search/api/)

## Quick Start (Docker — easiest)

Docker includes everything: Python, all dependencies, and PDF support. Nothing else to install.

### 1. Download

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor
```

### 2. Choose your AI and run

**Option A: Claude API** (best quality, ~$0.03 per resume)

Get your API key at https://console.anthropic.com/settings/keys (starts with `sk-ant-`), then:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
docker compose run --rm resume-tailor generate
```

**Option B: Ollama** (completely free)

Install Ollama from https://ollama.com/download, then:

```bash
ollama pull gemma3

# macOS / Windows / WSL2 (Docker Desktop)
docker compose run --rm resume-tailor generate --model ollama:gemma3

# Linux (native Docker)
make docker-ollama MODEL=ollama:gemma3
```

> The Docker container connects to Ollama running on your machine. No LLM models are stored inside the container.

That's it! The tool walks you through everything step by step. PDF output works out of the box.

<details>
<summary>Alternative: Local install (without Docker)</summary>

If you prefer not to use Docker, you can install directly. Requires Python 3.12+.

```bash
git clone https://github.com/allen92524/resume-tailor.git
cd resume-tailor
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-your-key-here"   # if using Claude
export BRAVE_API_KEY="your-brave-key"              # optional: enables company research
python src/main.py generate
```

> For PDF output with local install, you'll also need LibreOffice: `sudo apt install libreoffice-writer` (Linux) or `brew install --cask libreoffice` (macOS). Or just use `--format docx`.

</details>

---

## What Happens When You Run It

```
$ python src/main.py generate

==================================================
  Resume Tailor - AI-Powered Resume Generator
==================================================

--- Step 1: Your Resume ---
Paste your resume below (or enter a file path like ~/Downloads/resume.pdf).
Type END on its own line when done.

--- Step 4: Target Job Description ---
Paste a URL, file path, or the job description text.

https://jobs.example.com/senior-platform-engineer
  Fetching job posting from URL...
  Extracted job description (350 words):
  Role:     Senior Platform Engineer
  Company:  Dataflow Inc.
Use this job description? [Y/n]: y

--- Step 6: Gap Analysis ---
Your resume already matches well on:
  + Python backend development
  + Cloud infrastructure (AWS)

I have a few questions to strengthen your resume:
  Do you have experience with Go?
  → Built internal CLI tools in Go for deployment automation

--- Step 7: Compatibility Score ---
  Match Score: [████████████████░░░░] 78%

Proceed with generation? [Y/n]: y

--- Step 8: Generating Tailored Resume ---
Done! Your tailored resume has been saved to:
  output/Jane_Doe_Dataflow_Sr_Platform_Eng.pdf
```

## Features

- **Just answer questions** — the AI does the writing, you provide the facts
- **Paste a URL** — just paste the job posting link, no need to copy-paste the text
- **Remembers everything** — save your resume once, reuse it for every application
- **Smart questions** — only asks about gaps between your resume and the job posting
- **Match score** — see a 0-100% compatibility score before generating
- **Experience bank** — remembers your answers so you never retype the same thing
- **Resume review** — get AI feedback to improve your base resume
- **Multiple formats** — DOCX, PDF, or Markdown output
- **ATS-friendly** — clean formatting that passes automated resume screening
- **Multiple profiles** — manage resumes for different people on the same machine
- **Privacy first** — your data stays on your machine, nothing is uploaded

## Common Tasks

> **How it works:** The first time you run the tool, it asks for your resume and saves it as your profile. After that, it remembers you — just paste the job description and go.
>
> If you have multiple profiles (e.g., one for you, one for your spouse), the tool will show a menu to pick the right one.
>
> Each example below shows both the **Docker** command and the **local Python** command. Use whichever you set up.

### Apply to a new job

The main command. Paste the job description, answer a few questions, get a tailored resume.

```bash
# Local
python src/main.py generate

# Docker
docker compose run --rm resume-tailor generate
```

### Get your resume reviewed and improved

Get AI feedback on your base resume with suggestions to make it stronger.

```bash
# Local
python src/main.py review

# Docker
docker compose run --rm resume-tailor review
```

### Choose output format

```bash
# PDF (Docker includes PDF support; local needs LibreOffice)
python src/main.py generate --format pdf
docker compose run --rm resume-tailor generate --format pdf --output /output/

# Markdown
python src/main.py generate --format md
docker compose run --rm resume-tailor generate --format md --output /output/

# All formats at once (DOCX + PDF + Markdown)
python src/main.py generate --format all
docker compose run --rm resume-tailor generate --format all --output /output/
```

> Local PDF requires LibreOffice: `sudo apt install libreoffice-writer` (Linux) or `brew install --cask libreoffice` (macOS). Docker includes it automatically.

### Choose AI model

```bash
# Best quality (Claude Opus)
python src/main.py generate --model claude:opus
docker compose run --rm resume-tailor generate --model claude:opus

# Fastest and cheapest (Claude Haiku)
python src/main.py generate --model claude:haiku
docker compose run --rm resume-tailor generate --model claude:haiku

# Free with local Ollama
python src/main.py generate --model ollama:gemma3
docker compose run --rm resume-tailor generate --model ollama:gemma3
```

> When you run without `--model`, you'll be asked to choose interactively.

### Use a reference resume

If you have a resume from someone in a similar role, you can use it as a reference to guide the output style.

```bash
# Local
python src/main.py generate --reference ~/Downloads/colleague_resume.pdf

# Docker (place the file in the project folder first)
docker compose run --rm resume-tailor generate --reference /app/colleague_resume.pdf
```

### Resume for someone else (multiple profiles)

Each profile has its own saved resume, experience bank, and history.

```bash
# Local
python src/main.py --profile wife generate
python src/main.py --profile wife review
python src/main.py --profile wife profile view

# Docker
docker compose run --rm resume-tailor --profile wife generate
docker compose run --rm resume-tailor --profile wife review
docker compose run --rm resume-tailor --profile wife profile view
```

### Manage your profile

```bash
# See what's saved
python src/main.py profile view
docker compose run --rm resume-tailor profile view

# Update your name, email, phone, or LinkedIn (interactive prompts, just press Enter to skip)
python src/main.py profile update
docker compose run --rm resume-tailor profile update

# Export profile as formatted markdown
python src/main.py profile export
docker compose run --rm resume-tailor profile export

# Back up your profile (creates a timestamped copy)
python src/main.py profile backup
docker compose run --rm resume-tailor profile backup

# Restore from a backup
python src/main.py profile restore
docker compose run --rm resume-tailor profile restore

# Undo all resume improvements, go back to what you originally pasted
python src/main.py profile reset-baseline
docker compose run --rm resume-tailor profile reset-baseline

# Delete everything and start over
python src/main.py profile reset
docker compose run --rm resume-tailor profile reset

# Edit your profile (interactive menu: resume, contact info, or raw JSON)
python src/main.py profile edit
docker compose run --rm resume-tailor profile edit
```

### Quick generate (skip questions)

Skip the Q&A step and go straight to generation. Useful when the job is a close match.

```bash
# Local
python src/main.py generate --skip-questions --skip-assessment

# Docker
docker compose run --rm resume-tailor generate --skip-questions --skip-assessment
```

### Retry with different answers

Re-load the resume and job description from your last run so you can answer differently.

```bash
# Local
python src/main.py generate --resume-session

# Docker
docker compose run --rm resume-tailor generate --resume-session
```

### Test without using AI credits

Run the full flow with mock data — no API key needed.

```bash
# Local
python src/main.py generate --dry-run

# Docker
docker compose run --rm resume-tailor generate --dry-run
```

See [USAGE.md](USAGE.md) for the complete reference with all flags, workflows, and troubleshooting.

## For Developers

<details>
<summary>Docker, REST API, Kubernetes, and more</summary>

### Docker details

Docker Compose is the easiest way to run (see Quick Start above). For manual `docker run`:

```bash
docker build -t resume-tailor .

# Claude API
docker run -it --rm \
  -e ANTHROPIC_API_KEY="sk-ant-your-key" \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --format pdf --output /output/

# Ollama (macOS / Windows / WSL2 — Docker Desktop)
docker run -it --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --model ollama:gemma3 --format pdf --output /output/

# Ollama (Linux — native Docker, uses host networking)
docker run -it --rm \
  --network host \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --model ollama:gemma3 --format pdf --output /output/
```

> No LLM models are stored inside the container. The Docker image connects to Ollama running on your host machine. Generated files are automatically owned by your user (not root).

### REST API

```bash
make api    # Start server at http://localhost:8000
```

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/analyze-jd` | Analyze a job description |
| `POST` | `/api/v1/assess-compatibility` | Score resume vs job match (0-100%) |
| `POST` | `/api/v1/generate` | Generate tailored resume (JSON) |
| `POST` | `/api/v1/generate/pdf` | Generate and download as PDF |
| `POST` | `/api/v1/review` | Review resume with AI feedback |

API docs: http://localhost:8000/docs

### Kubernetes (Helm)

```bash
make helm-install
kubectl port-forward svc/resume-tailor 8000:8000
```

See [USAGE.md](USAGE.md) for Helm values, ArgoCD setup, and monitoring.

### Contributing

```bash
make dev-install   # Install dev dependencies
make test          # Run tests
make lint          # Run linter
make format        # Format code
make check-secrets # Scan for accidentally committed personal info
```

</details>

## Privacy

- **Profiles** are saved locally at `~/.resume-tailor/`. They never leave your machine.
- **Generated resumes** go to the `output/` folder. Nothing is uploaded.
- **Claude API** sends your resume and job description to Anthropic for processing. If you use **Ollama**, everything stays on your machine.

## License

This project is licensed under the [MIT License](LICENSE).
