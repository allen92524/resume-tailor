# Resume Tailor - AI-Powered Resume Generator

## Project Overview
A CLI tool that takes a user's existing resume and a target job description (JD), asks clarifying questions, and generates a tailored resume optimized for the specific role. Uses the Anthropic Claude API or local Ollama models for intelligent content generation and outputs to DOCX format.

## Tech Stack
- **Language:** Python 3.12+
- **AI:** Anthropic Claude API (`anthropic` SDK), local Ollama models (`httpx`)
- **Document Generation:** `python-docx` for DOCX output, LibreOffice for PDF conversion
- **CLI Framework:** `click` for CLI interface
- **Resume Parsing:** `python-docx` for DOCX input, `PyPDF2` for PDF input

## Project Structure
```
resume-tailor/
├── CLAUDE.md              # This file - project instructions
├── README.md              # User-facing documentation
├── USAGE.md               # Quick reference guide for all commands/flags
├── FLOW.md                # Source of truth for generate command flow
├── Makefile               # Dev commands: make test, make lint, make run, deploy, release
├── VERSION                # Current semantic version (e.g. 1.3.0)
├── Dockerfile             # Container image definition
├── docker-compose.yml     # Docker Compose (connects to host Ollama)
├── docker-compose.full.yml # Docker Compose with bundled Ollama container
├── .dockerignore          # Docker build ignore rules
├── .gitattributes         # Line ending and binary file rules
├── requirements.txt       # Python dependencies (runtime)
├── requirements-dev.txt   # Dev dependencies (ruff, black, pytest)
├── .github/
│   └── workflows/
│       └── ci.yml         # GitHub Actions CI (lint + test on push/PR)
├── src/
│   ├── __init__.py
│   ├── main.py            # CLI entry point (click commands)
│   ├── web.py             # FastAPI REST API entry point
│   ├── api.py             # Claude API call helpers with retry logic
│   ├── llm_client.py      # Unified LLM client (Claude + Ollama)
│   ├── telemetry.py       # OpenTelemetry tracing & Prometheus metrics
│   ├── config.py          # Centralized configuration constants
│   ├── models.py          # Data models (dataclasses for all structured data)
│   ├── profile.py         # User profile management (~/.resume-tailor/)
│   ├── session.py         # Session save/restore for --resume-session
│   ├── resume_parser.py   # Parse input resume (text/docx/pdf)
│   ├── jd_analyzer.py     # Analyze job description with Claude
│   ├── gap_analyzer.py    # Compare resume vs JD requirements
│   ├── compatibility_assessor.py # Score resume-JD match
│   ├── resume_generator.py # Generate tailored resume content via Claude
│   ├── resume_reviewer.py # Review and improve base resume
│   ├── docx_builder.py    # Build formatted DOCX/PDF/MD output
│   ├── prompts.py         # Thin loader for prompt template files
│   └── prompts/           # Prompt template files (system + user per file)
│       ├── PROMPTS.md     # Prompt documentation
│       └── *.md           # Individual prompt templates
├── helm/                  # Helm chart for Kubernetes deployment
│   └── resume-tailor/
│       ├── Chart.yaml     # Chart metadata and version
│       ├── values.yaml    # Default configuration values
│       ├── dashboards/
│       │   └── resume-tailor-dashboard.json  # Grafana dashboard definition
│       └── templates/
│           ├── _helpers.tpl           # Helm helper functions
│           ├── deployment.yaml        # K8s Deployment
│           ├── service.yaml           # K8s Service
│           ├── ingress.yaml           # K8s Ingress
│           ├── configmap.yaml         # Non-sensitive config
│           ├── secret.yaml            # API key secret
│           ├── servicemonitor.yaml    # Prometheus ServiceMonitor
│           ├── configmap-grafana-dashboard.yaml  # Grafana dashboard ConfigMap
│           └── NOTES.txt              # Post-install notes
├── argocd/                # GitOps deployment with ArgoCD
│   ├── application.yaml   # ArgoCD Application manifest
│   └── README.md          # ArgoCD setup instructions
├── grafana/               # Standalone Grafana dashboard
│   └── resume-tailor-dashboard.json
├── scripts/
│   └── bump-version.sh   # Semantic versioning bump script
├── tests/                 # Test suite
│   ├── conftest.py        # Pytest configuration & fixtures
│   ├── fixtures/          # Mock data for tests
│   └── test_*.py          # Test modules
├── examples/
│   ├── sample_resume.txt  # Example resume for testing
│   └── sample_jd.txt      # Example JD for testing
└── output/                # Generated resumes go here
```

## Architecture & Design Decisions

### CLI Commands
- `generate` — Full resume tailoring pipeline (see FLOW.md for detailed steps)
- `review` — Review and improve the base resume stored in profile
- `profile` — Manage profile (view, update, edit, export, backup, restore, reset)

### Generate Flow
See [FLOW.md](FLOW.md) for the authoritative step-by-step flow.

### LLM Backend
- Supports Claude API (default) and local Ollama models via `src/llm_client.py`
- `--model claude` (default) uses Anthropic API; `--model ollama:<name>` uses local Ollama
- Claude API uses `anthropic` Python SDK with retry logic (`tenacity`) in `src/api.py`
- Claude model: `claude-sonnet-4-5-20250929` (configured in `src/config.py`)
- Ollama communicates via REST API at `http://localhost:11434/api/chat` using `httpx`
- All prompts stored in `src/prompts/` as Markdown template files, loaded by `src/prompts.py`
- Shared rules in `src/prompts/shared_rules.md`, injected via `{%SECTION%}` markers
- Use structured output (JSON) for parsed data
- API calls: JD analysis, gap analysis, compatibility assessment, resume generation, resume review/improve, contact extraction
- Each API call tracked with OpenTelemetry spans and Prometheus metrics via `src/telemetry.py`

### REST API (FastAPI)
- Entry point: `src/web.py`, run with `make api` or `uvicorn src.web:app`
- Endpoints under `/api/v1/`: health, analyze-jd, assess-compatibility, generate, generate/pdf, review
- `/metrics` endpoint exposes Prometheus metrics
- CORS middleware enabled, OpenTelemetry auto-instrumentation on all routes

### Observability
- `src/telemetry.py` sets up OpenTelemetry tracing and Prometheus metrics
- Traces export to console by default; set `OTEL_EXPORTER_OTLP_ENDPOINT` for OTLP collector
- Prometheus metrics: HTTP request count/duration/active, Claude API calls/duration, resume generations
- Grafana dashboard in `grafana/resume-tailor-dashboard.json` (also provisioned via Helm)
- Kubernetes: enable ServiceMonitor and Grafana dashboard via Helm values

### Deployment
- **Docker:** `Dockerfile` for containerized builds
- **Helm:** Chart in `helm/resume-tailor/` for Kubernetes deployment
- **ArgoCD:** GitOps auto-deploy from `argocd/application.yaml` — watches `main` branch
- **CI/CD:** GitHub Actions (`.github/workflows/ci.yml`) runs lint + tests on push/PR

### Versioning
- Semantic versioning tracked in `VERSION` file
- `scripts/bump-version.sh` updates VERSION, Helm Chart.yaml, commits, and tags
- Makefile targets: `release-patch`, `release-minor`, `release-major`, `release-push`

### DOCX Output Format
- Clean, professional, ATS-friendly format
- Sections: Header (name/contact), Summary, Experience, Skills, Education, Certifications
- No tables for layout (ATS can't parse them well), use paragraphs with proper heading styles
- Consistent fonts: Calibri, 10.5pt body, 14pt name
- Filename: `Name_Company_Role.docx` (descriptive, not timestamped)

## Development Phases

### Phase 1: MVP — Done
- [x] Project scaffold
- [x] Basic CLI with click
- [x] Text input for resume and JD (paste into terminal)
- [x] Claude API integration for JD analysis
- [x] Claude API integration for resume generation
- [x] DOCX output with clean formatting
- [x] End-to-end flow working

### Phase 2: Interactive Q&A — Done
- [x] Add follow-up questions after resume/JD input (gap analysis)
- [x] Compatibility assessment with match score
- [x] Add `--verbose` flag to show debug logging
- [x] Profile system with experience bank and application history
- [x] Resume review and improvement workflow
- [x] Session save/restore (`--resume-session`)
- [x] Multi-profile support (`--profile`)
- [ ] Let user select which sections to include

### Phase 3: File Input Support — Done
- [x] Parse DOCX resume input
- [x] Parse PDF resume input
- [x] Auto-detect file format
- [x] PDF output via LibreOffice conversion
- [x] Markdown output

### Phase 4: REST API & Infrastructure — Done
- [x] FastAPI REST API with all core endpoints
- [x] Docker containerization
- [x] Helm chart for Kubernetes deployment
- [x] ArgoCD GitOps auto-deploy
- [x] OpenTelemetry tracing and Prometheus metrics
- [x] Grafana dashboard (standalone + Helm-provisioned)
- [x] ServiceMonitor for Prometheus Operator
- [x] GitHub Actions CI pipeline
- [x] Automated semantic versioning with release scripts

### Phase 5: Web UI (Future)
- [ ] Streamlit or Next.js frontend
- [ ] Side-by-side comparison view
- [ ] Resume history/versioning

## Coding Standards
- Use type hints throughout
- Docstrings on all public functions
- Handle API errors gracefully (rate limits, network issues)
- Never hardcode API keys - use environment variable `ANTHROPIC_API_KEY`
- Keep prompts in `src/prompts/` template files, loaded by `prompts.py` — not scattered in logic files
- Print clear progress messages to the user during generation
- Never commit files containing real personal info. Always use example data (e.g., `user@example.com`, `Jane Doe`) in tests and docs

## Environment Setup
```bash
cd resume-tailor
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
```

## Running

See [USAGE.md](USAGE.md) for the complete quick reference guide with all commands, flags, workflows, and troubleshooting.

```bash
python src/main.py generate
```

## Git Workflow
- After every code change, run `pytest tests/ -v` to verify nothing is broken. Never commit if tests fail.
- Then commit with `git add -A && git commit -m "description of change"`
- Never commit broken code
- Use descriptive commit messages
- A pre-commit hook (`.githooks/pre-commit`) scans for personal info — configure with `git config core.hooksPath .githooks`

## Key Reminders
- The ANTHROPIC_API_KEY must be set as an environment variable
- Output goes to the `output/` directory with timestamped filenames
- ATS-friendly formatting is critical - no fancy layouts, no tables for structure
- The tool is for personal use to help with job applications

## Project Context
Read CONVERSATION_CONTEXT.md for the full history of design decisions and project philosophy.

