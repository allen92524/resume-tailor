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

## Kubernetes Deployment

Deploy the API to Kubernetes using the included Helm chart.

### Prerequisites

- [Helm](https://helm.sh/docs/intro/install/) v3+
- A Kubernetes cluster (or [minikube](https://minikube.sigs.k8s.io/) for local development)

### Quick start with minikube

```bash
# Build the Docker image and load it into minikube
docker build -t resume-tailor:latest .
minikube image load resume-tailor:latest

# Install the Helm chart
make helm-install
# or: helm upgrade --install resume-tailor helm/resume-tailor --set apiKey=$ANTHROPIC_API_KEY

# Port-forward to access the API
kubectl port-forward svc/resume-tailor 8000:8000
curl http://localhost:8000/api/v1/health
```

### Helm commands

```bash
make helm-install    # Install or upgrade the release
make helm-uninstall  # Remove the release
make helm-template   # Render templates locally (dry-run)
```

### Configuration

Override defaults in `helm/resume-tailor/values.yaml` or pass `--set` flags:

```bash
helm upgrade --install resume-tailor helm/resume-tailor \
  --set apiKey=$ANTHROPIC_API_KEY \
  --set replicaCount=3 \
  --set ingress.enabled=true \
  --set ingress.host=resume-tailor.example.com
```

| Value | Default | Description |
|-------|---------|-------------|
| `replicaCount` | `1` | Number of pod replicas |
| `image.repository` | `resume-tailor` | Docker image repository |
| `image.tag` | `latest` | Docker image tag |
| `service.port` | `8000` | Service port |
| `ingress.enabled` | `false` | Enable Ingress resource |
| `ingress.host` | `resume-tailor.local` | Ingress hostname |
| `apiKey` | `""` | Anthropic API key (stored as Secret) |
| `resources.limits.cpu` | `500m` | CPU limit |
| `resources.limits.memory` | `512Mi` | Memory limit |

## ArgoCD GitOps Deployment

Automate deployments with ArgoCD — any push to `main` that changes the Helm chart will auto-deploy to your cluster.

### Setup

```bash
# 1. Create the API key secret
kubectl create secret generic resume-tailor-api-key \
  --from-literal=api-key=$ANTHROPIC_API_KEY

# 2. Apply the ArgoCD application
kubectl apply -f argocd/application.yaml

# Or use the Makefile shortcut
make argocd-setup
```

### How it works

- ArgoCD watches `helm/resume-tailor` in the repo for changes on `main`
- **Automated sync** with self-heal and prune enabled
- Manual cluster drift is automatically corrected

```bash
make argocd-status   # Check sync status
```

See [argocd/README.md](argocd/README.md) for full details.

## Observability

The API includes built-in OpenTelemetry tracing and Prometheus metrics.

### Prometheus Metrics

The `/metrics` endpoint exposes metrics in Prometheus format:

```bash
# Start the API
make api

# View raw metrics
make metrics
# or: curl http://localhost:8000/metrics
```

Available metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total requests by method, endpoint, status code |
| `http_request_duration_seconds` | Histogram | Request latency by method and endpoint |
| `http_active_requests` | Gauge | Currently in-flight requests |
| `claude_api_calls_total` | Counter | Claude API calls by model and status |
| `claude_api_call_duration_seconds` | Histogram | Claude API call latency by model |
| `resume_generations_total` | Counter | Total successful resume generations |

### OpenTelemetry Tracing

Traces are exported to the console by default. To send traces to an OTLP collector:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
make api
```

### Grafana Dashboard

A pre-built dashboard is available at `grafana/resume-tailor-dashboard.json`. Import it into Grafana manually or deploy via Helm (see below).

Panels: Request Rate, Response Time (P50/P95/P99), Error Rate, Claude API Latency, Active Requests, Resume Generations.

### Kubernetes Monitoring

Enable the Prometheus ServiceMonitor and Grafana dashboard auto-import in Helm:

```bash
helm upgrade --install resume-tailor helm/resume-tailor \
  --set apiKey=$ANTHROPIC_API_KEY \
  --set metrics.serviceMonitor.enabled=true \
  --set metrics.grafanaDashboard.enabled=true
```

| Value | Default | Description |
|-------|---------|-------------|
| `metrics.serviceMonitor.enabled` | `false` | Create a ServiceMonitor for Prometheus Operator |
| `metrics.serviceMonitor.interval` | `30s` | Scrape interval |
| `metrics.grafanaDashboard.enabled` | `false` | Create a ConfigMap for Grafana sidecar auto-import |

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

## REST API

Resume Tailor also provides a FastAPI REST API for programmatic access.

### Start the server

```bash
make api
# or: uvicorn src.web:app --reload --port 8000
```

API docs are available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check — returns status and API key presence |
| `POST` | `/api/v1/analyze-jd` | Analyze a job description, returns structured skills/keywords/responsibilities |
| `POST` | `/api/v1/assess-compatibility` | Score resume-JD match (0-100%) with detailed breakdown |
| `POST` | `/api/v1/generate` | Generate a tailored resume as JSON |
| `POST` | `/api/v1/generate/pdf` | Generate a tailored resume and download as PDF |
| `POST` | `/api/v1/review` | Review a resume — score, strengths, weaknesses, improved bullets |

### Example requests

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Analyze a job description
curl -X POST http://localhost:8000/api/v1/analyze-jd \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "We are looking for a Senior Python Developer..."}'

# Assess compatibility
curl -X POST http://localhost:8000/api/v1/assess-compatibility \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer..."}'

# Generate tailored resume
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer...", "additional_context": "I also know Go"}'

# Generate and download PDF
curl -X POST http://localhost:8000/api/v1/generate/pdf \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer..."}' \
  -o resume.pdf

# Review resume
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe, Software Engineer..."}'
```

## Project Structure

```
resume-tailor/
├── src/
│   ├── main.py                # CLI entry point (click commands)
│   ├── web.py                 # FastAPI REST API entry point
│   ├── api.py                 # API call helpers with retry logic
│   ├── telemetry.py           # OpenTelemetry tracing & Prometheus metrics
│   ├── config.py              # Centralized configuration
│   ├── models.py              # Data models (dataclasses)
│   ├── profile.py             # Profile management (~/.resume-tailor/)
│   ├── session.py             # Session save/restore
│   ├── resume_parser.py       # Parse resume from text/docx/pdf
│   ├── jd_analyzer.py         # Analyze job descriptions
│   ├── gap_analyzer.py        # Compare resume vs JD requirements
│   ├── compatibility_assessor.py  # Score resume-JD match
│   ├── resume_generator.py    # Generate tailored resume content
│   ├── resume_reviewer.py     # Review and improve base resume
│   ├── docx_builder.py        # Build DOCX/PDF/Markdown output
│   ├── prompts.py             # Prompt template loader
│   └── prompts/               # Prompt templates (Markdown files)
├── helm/resume-tailor/        # Helm chart for Kubernetes
├── argocd/                    # ArgoCD GitOps deployment
├── grafana/                   # Standalone Grafana dashboard
├── scripts/                   # Release versioning scripts
├── tests/                     # Test suite with fixtures
└── VERSION                    # Semantic version file
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

### All Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Create venv and install runtime dependencies |
| `make dev-install` | Install runtime + dev dependencies |
| `make test` | Run pytest |
| `make lint` | Run ruff linter |
| `make format` | Run black formatter |
| `make run` | Run the generate command |
| `make run-profile PROFILE=name` | Run generate with a named profile |
| `make dry-run` | Run with mock data (no API calls) |
| `make api` | Start FastAPI server on port 8000 |
| `make metrics` | Fetch raw Prometheus metrics from running API |
| `make docker-build` | Build Docker image |
| `make docker-run` | Run Docker container interactively |
| `make helm-install` | Install/upgrade Helm chart to Kubernetes |
| `make helm-uninstall` | Uninstall Helm chart |
| `make helm-template` | Render Helm templates locally (dry-run) |
| `make argocd-setup` | Create API key secret and apply ArgoCD app |
| `make argocd-status` | Check ArgoCD sync status |
| `make release-patch` | Bump patch version, commit, and tag |
| `make release-minor` | Bump minor version, commit, and tag |
| `make release-major` | Bump major version, commit, and tag |
| `make release-push` | Push commits and tags to GitHub |
| `make clean` | Remove venv, pycache, and output files |

## License

MIT
