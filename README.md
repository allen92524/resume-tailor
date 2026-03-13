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
Paste the job description (or enter a file path).

  Role:     Senior Platform Engineer
  Company:  Dataflow Inc.
Is this correct? [Y/n]: y

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

### Apply to a new job

```bash
# Local
python src/main.py generate

# Docker
docker compose run --rm resume-tailor generate
```

### Get your resume reviewed and improved

```bash
# Local
python src/main.py review

# Docker
docker compose run --rm resume-tailor review
```

### Output as PDF

```bash
# Docker (PDF works out of the box)
docker compose run --rm resume-tailor generate --format pdf --output /output/

# Local install (requires LibreOffice)
python src/main.py generate --format pdf
```

> Local install only: PDF requires LibreOffice. Install it: `sudo apt install libreoffice-writer` (Linux) or `brew install --cask libreoffice` (macOS). Docker includes it automatically.

### Manage your profile

```bash
# Local
python src/main.py profile view
python src/main.py profile edit
python src/main.py profile reset

# Docker
docker compose run --rm resume-tailor profile view
docker compose run --rm resume-tailor profile edit
docker compose run --rm resume-tailor profile reset
```

### Manage a resume for someone else

```bash
# Local
python src/main.py --profile wife generate
python src/main.py --profile wife profile view

# Docker
docker compose run --rm resume-tailor --profile wife generate
docker compose run --rm resume-tailor --profile wife profile view
```

### Choose a specific Claude model

```bash
# Use the most capable model
python src/main.py generate --model claude:opus

# Use the fastest/cheapest model
python src/main.py generate --model claude:haiku
```

When you run interactively (no `--model` flag), you'll be asked to choose between Haiku, Sonnet, and Opus after selecting Claude.

### Retry with different answers

```bash
python src/main.py generate --resume-session
```

### Skip straight to generation (no questions)

```bash
python src/main.py generate --skip-questions --skip-assessment
```

### Test the full flow without using any AI

```bash
python src/main.py generate --dry-run
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
