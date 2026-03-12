[English](USAGE.md) | [中文](USAGE_CN.md)

# Resume Tailor - Complete Guide

Everything you can do with Resume Tailor, organized by what you're trying to accomplish.

## Table of Contents

- [I want to apply to a new job](#i-want-to-apply-to-a-new-job)
- [I want to set up a profile for someone else](#i-want-to-set-up-a-profile-for-someone-else)
- [I want to improve my base resume](#i-want-to-improve-my-base-resume)
- [I want to try different answers for the same job](#i-want-to-try-different-answers-for-the-same-job)
- [I want to use a free local model instead of Claude](#i-want-to-use-a-free-local-model-instead-of-claude)
- [I want to run everything in Docker](#i-want-to-run-everything-in-docker)
- [I want to use the REST API](#i-want-to-use-the-rest-api)
- [I want to deploy to Kubernetes](#i-want-to-deploy-to-kubernetes)
- [I want to set up monitoring](#i-want-to-set-up-monitoring)
- [I want to back up my data](#i-want-to-back-up-my-data)
- [I want to release a new version](#i-want-to-release-a-new-version)
- [All flags reference](#all-flags-reference)
- [All Makefile targets](#all-makefile-targets)
- [Troubleshooting](#troubleshooting)

---

## I want to apply to a new job

### First time (no profile yet)

```bash
python src/main.py generate
```

The tool walks you through everything:

1. Creates a profile — enter your name, email, phone
2. Paste your resume (or give a file path to a `.txt`, `.docx`, or `.pdf`)
3. Optionally provide a reference resume from someone in a similar role
4. AI reviews your resume and suggests improvements
5. Paste the job description (or give a file path)
6. Answer a few questions about gaps between your resume and the job
7. See a compatibility score (0-100%)
8. Get your tailored resume in the `output/` folder

### Second time onward (profile exists)

```bash
python src/main.py generate
```

Same command. The tool remembers your resume and contact info from last time. Just paste the new job description and answer the gap questions. If you've answered similar questions before, the tool offers to reuse your previous answers.

### I want PDF output

```bash
python src/main.py generate --format pdf
```

Requires LibreOffice installed on your system. If you don't have it:

```bash
# Ubuntu / Debian
sudo apt install libreoffice-writer -y

# macOS
brew install --cask libreoffice
```

Or use `--format docx` and convert manually.

### I want to skip the questions and just generate

```bash
python src/main.py generate --skip-questions
```

Skips the gap analysis questions. The AI will do its best with what's in your resume.

### I want to skip the compatibility score

```bash
python src/main.py generate --skip-assessment
```

### I want to save the output somewhere specific

```bash
# Save to a specific folder
python src/main.py generate --output ~/Desktop/

# Save to a specific file
python src/main.py generate --output ~/Desktop/my_resume.docx
```

### I want to provide a reference resume

If you have a resume from someone who already has the job you want:

```bash
python src/main.py generate --reference path/to/their_resume.docx
```

The AI uses it to understand what the company values — tone, keywords, structure.

### I have all my answers ready and want to go fast

```bash
python src/main.py generate --skip-questions --skip-assessment --format pdf
```

---

## I want to set up a profile for someone else

Use the `--profile` flag to create a separate profile. Each profile has its own resume, experience bank, and history.

```bash
# Set up for your wife
python src/main.py --profile wife generate

# Set up for a friend
python src/main.py --profile alex generate
```

Each person's data is stored separately at `~/.resume-tailor/<name>/profile.json`.

### Managing another person's profile

```bash
# View their profile
python src/main.py --profile wife profile view

# Update their contact info
python src/main.py --profile wife profile update

# Back up their profile
python src/main.py --profile wife profile backup

# Reset and start over
python src/main.py --profile wife profile reset
```

---

## I want to improve my base resume

The `review` command analyzes your saved resume and suggests improvements — better bullet points, missing keywords, and overall quality score.

```bash
python src/main.py review
```

The tool will:
1. Show a quality score (0-100)
2. List strengths and weaknesses
3. Suggest improved bullet points
4. Ask if you want to apply the improvements
5. If yes, ask you to fill in any placeholder metrics (e.g., "Increased performance by [X%]")
6. Save the improved resume back to your profile

### Review using a local model

```bash
python src/main.py review --model ollama:qwen3.5
```

---

## I want to try different answers for the same job

Use `--resume-session` to reload your last run's inputs:

```bash
python src/main.py generate --resume-session
```

The tool restores your resume text, job description, and previous answers. You can keep any of them or re-enter new ones. This is useful when you want to:

- Try emphasizing different experience
- Change your answers to gap questions
- Generate a different format (add `--format pdf`)

---

## I want to use a free local model instead of Claude

[Ollama](https://ollama.com/) lets you run AI models on your own machine for free.

### Install Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Windows — download from https://ollama.com/download
```

### Download a model and run

```bash
ollama pull qwen3.5
python src/main.py generate --model ollama:qwen3.5
```

No API key needed. The `--model` flag works with both `generate` and `review`:

```bash
python src/main.py review --model ollama:qwen3.5
```

On startup, Resume Tailor will automatically check Ollama connectivity, validate that the model is available, and warm up the model by loading it into memory. You can configure the timeout via the `OLLAMA_TIMEOUT` environment variable (default: 300 seconds).

### Available models

Any Ollama model works. Some good choices:

| Model | Command | Notes |
|-------|---------|-------|
| Qwen 3.5 | `--model ollama:qwen3.5` | Good all-around, recommended |
| Devstral | `--model ollama:devstral` | Strong at technical resumes |
| Gemma 3 | `--model ollama:gemma3` | Lightweight, faster |

### Test without any AI

```bash
python src/main.py generate --dry-run
```

Uses mock responses so you can test the full flow without spending credits or needing a model.

---

## I want to run everything in Docker

Docker uses the Claude API only. Ollama (free local models) is supported when running locally without Docker — see [I want to use a free local model instead of Claude](#i-want-to-use-a-free-local-model-instead-of-claude).

> **Why no Ollama in Docker?** LLM models are multi-gigabyte files. Running them inside containers means huge images, slow pulls, and heavy resource usage. It's much better to run Ollama directly on your machine.

### Docker + Claude API

```bash
docker build -t resume-tailor .

docker run -it \
  -e ANTHROPIC_API_KEY="sk-ant-your-key" \
  -v ~/.resume-tailor:/root/.resume-tailor \
  -v $(pwd)/output:/output \
  resume-tailor generate --format pdf --output /output/
```

Or use Docker Compose:

```bash
docker compose run --rm resume-tailor
```

---

## I want to use the REST API

Resume Tailor has a web API for programmatic access.

### Start the server

```bash
make api
```

API docs: http://localhost:8000/docs (interactive Swagger UI).

### Endpoints

| Method | Endpoint | What it does |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Check if the server is running |
| `POST` | `/api/v1/analyze-jd` | Analyze a job description |
| `POST` | `/api/v1/assess-compatibility` | Score resume vs job match (0-100%) |
| `POST` | `/api/v1/generate` | Generate a tailored resume (returns JSON) |
| `POST` | `/api/v1/generate/pdf` | Generate and download as PDF file |
| `POST` | `/api/v1/review` | Review a resume and get improvement suggestions |
| `GET` | `/metrics` | Prometheus metrics |

### Examples

```bash
# Check server health
curl http://localhost:8000/api/v1/health

# Analyze a job description
curl -X POST http://localhost:8000/api/v1/analyze-jd \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "We are looking for a Senior Python Developer..."}'

# Score resume-job compatibility
curl -X POST http://localhost:8000/api/v1/assess-compatibility \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer..."}'

# Generate a tailored resume
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer...", "additional_context": "I also know Go"}'

# Generate and download as PDF
curl -X POST http://localhost:8000/api/v1/generate/pdf \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe...", "jd_text": "Senior Python Developer..."}' \
  -o resume.pdf

# Review a resume
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Jane Doe, Software Engineer..."}'
```

### Using Ollama with the API

Pass `"model": "ollama:qwen3.5"` in any request body:

```bash
curl -X POST http://localhost:8000/api/v1/analyze-jd \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "We are looking for...", "model": "ollama:qwen3.5"}'
```

---

## I want to deploy to Kubernetes

The project includes a Helm chart for Kubernetes deployment.

### What you need

- [Docker](https://docs.docker.com/get-docker/) installed
- [Helm](https://helm.sh/docs/intro/install/) v3+
- A Kubernetes cluster (or [minikube](https://minikube.sigs.k8s.io/) for testing locally)

### Deploy with minikube (local testing)

```bash
# Build the image and load it into minikube
docker build -t resume-tailor:latest .
minikube image load resume-tailor:latest

# Deploy
make helm-install

# Access the API
kubectl port-forward svc/resume-tailor 8000:8000
curl http://localhost:8000/api/v1/health
```

### Deploy to a real cluster

```bash
helm upgrade --install resume-tailor helm/resume-tailor \
  --set apiKey=$ANTHROPIC_API_KEY \
  --set image.repository=your-registry/resume-tailor \
  --set image.tag=latest
```

### Configuration options

| Setting | Default | What it does |
|---------|---------|-------------|
| `replicaCount` | `1` | Number of instances to run |
| `image.repository` | `resume-tailor` | Docker image to use |
| `image.tag` | `latest` | Image version |
| `service.port` | `8000` | Port the service listens on |
| `ingress.enabled` | `false` | Expose via Ingress (for public access) |
| `ingress.host` | `resume-tailor.local` | Domain name for Ingress |
| `apiKey` | `""` | Your Anthropic API key |
| `resources.limits.cpu` | `500m` | Max CPU per instance |
| `resources.limits.memory` | `512Mi` | Max memory per instance |

### Auto-deploy with ArgoCD

ArgoCD can automatically deploy changes when you push to `main`:

```bash
# One-time setup
make argocd-setup

# Check status
make argocd-status
```

How it works: ArgoCD watches `helm/resume-tailor` in your repo. When you push changes to `main`, it automatically syncs to your cluster. Manual changes on the cluster are auto-corrected.

See [argocd/README.md](argocd/README.md) for full setup details.

### Remove the deployment

```bash
make helm-uninstall
```

---

## I want to set up monitoring

The API has built-in metrics for monitoring.

### View metrics

```bash
# Start the API
make api

# See raw metrics
curl http://localhost:8000/metrics
```

### Available metrics

| Metric | What it tracks |
|--------|---------------|
| `http_requests_total` | Total requests (by endpoint and status code) |
| `http_request_duration_seconds` | How long requests take |
| `http_active_requests` | Currently in-flight requests |
| `claude_api_calls_total` | AI API calls (by model and success/failure) |
| `claude_api_call_duration_seconds` | How long AI calls take |
| `resume_generations_total` | Total resumes generated |

### Grafana dashboard

Import `grafana/resume-tailor-dashboard.json` into Grafana for a pre-built dashboard with:
- Request rate and error rate
- Response time (P50/P95/P99)
- AI API latency
- Active requests and resume generation count

### Kubernetes monitoring

Enable automatic metric collection and Grafana dashboard in Helm:

```bash
helm upgrade --install resume-tailor helm/resume-tailor \
  --set apiKey=$ANTHROPIC_API_KEY \
  --set metrics.serviceMonitor.enabled=true \
  --set metrics.grafanaDashboard.enabled=true
```

### Send traces to a collector

By default, traces go to the console. To send them to an OpenTelemetry collector:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
make api
```

---

## I want to back up my data

### Create a backup

```bash
python src/main.py profile backup
```

This saves a copy of your profile as `profile_backup_YYYY-MM-DD.json` in `~/.resume-tailor/<profile>/`.

### Restore from a backup

```bash
python src/main.py profile restore
```

Shows all available backups and lets you pick one.

### Back up a specific profile

```bash
python src/main.py --profile wife profile backup
python src/main.py --profile wife profile restore
```

### Tips

- **Always back up before resetting** — run `profile backup` before `profile reset`
- **Always back up before review** — the `review` command can modify your resume
- Multiple backups on the same day overwrite each other (same date = same filename)

---

## I want to release a new version

The project uses semantic versioning (e.g., `1.5.0`). The version is tracked in the `VERSION` file.

### Bump and publish

```bash
# 1. Make sure tests pass
make test

# 2. Bump the version (pick one)
make release-patch   # 1.5.0 → 1.5.1 (bug fixes)
make release-minor   # 1.5.0 → 1.6.0 (new features)
make release-major   # 1.5.0 → 2.0.0 (breaking changes)

# 3. Push to GitHub
make release-push
```

This automatically updates `VERSION`, the Helm chart version, creates a git commit, and tags it.

---

## All flags reference

| Flag | Works with | What it does | Default |
|------|-----------|-------------|---------|
| `--verbose` | any command | Show detailed debug logs | off |
| `--profile <name>` | any command | Use a named profile | `default` |
| `--format <type>` | `generate` | Output format: `docx`, `pdf`, `md`, `all` | `docx` |
| `--output <path>` | `generate` | Custom output directory or file path | `output/` |
| `--skip-questions` | `generate` | Skip gap analysis follow-up questions | off |
| `--skip-assessment` | `generate` | Skip compatibility score | off |
| `--reference <file>` | `generate` | Path to a reference resume | none |
| `--resume-session` | `generate` | Restore inputs from last session | off |
| `--model <name>` | `generate`, `review` | AI model: `claude` or `ollama:<name>` | `claude` |
| `--dry-run` | `generate` | Use mock data, no AI calls | off |

---

## All Makefile targets

Run `make help` to see this list in your terminal.

| Target | What it does |
|--------|-------------|
| `make install` | Create virtual environment and install dependencies |
| `make dev-install` | Install runtime + development dependencies |
| `make test` | Run the test suite |
| `make lint` | Check code for style issues |
| `make format` | Auto-format code |
| `make run` | Run the generate command |
| `make run-local MODEL=ollama:qwen3.5` | Run with a local Ollama model |
| `make run-profile PROFILE=name` | Run with a specific profile |
| `make dry-run` | Test the full flow with mock data |
| `make api` | Start the REST API server on port 8000 |
| `make metrics` | Fetch metrics from the running API |
| `make docker-build` | Build the Docker image |
| `make docker-run` | Run the Docker container |
| `make test-docker` | Build and smoke-test the Docker image |
| `make helm-install` | Deploy to Kubernetes via Helm |
| `make helm-uninstall` | Remove Kubernetes deployment |
| `make helm-template` | Preview Helm templates without deploying |
| `make argocd-setup` | Set up ArgoCD auto-deployment |
| `make argocd-status` | Check ArgoCD deployment status |
| `make release-patch` | Bump patch version (1.5.0 → 1.5.1) |
| `make release-minor` | Bump minor version (1.5.0 → 1.6.0) |
| `make release-major` | Bump major version (1.5.0 → 2.0.0) |
| `make release-push` | Push release commits and tags to GitHub |
| `make clean` | Delete virtual environment, caches, and outputs |

---

## Troubleshooting

### "ANTHROPIC_API_KEY environment variable is not set"

You need to set your API key before running:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

Get a key at https://console.anthropic.com/settings/keys. If you don't want to pay for an API key, use a local model instead:

```bash
python src/main.py generate --model ollama:qwen3.5
```

### "Invalid API key"

Your key might be expired or mistyped. Check it at https://console.anthropic.com/settings/keys. It should start with `sk-ant-`.

### "Could not connect to the Anthropic API"

Check your internet connection. If you're behind a corporate firewall or VPN, that might be blocking the connection.

### PDF output isn't working

PDF conversion requires LibreOffice:

```bash
# Ubuntu / Debian
sudo apt install libreoffice-writer -y

# macOS
brew install --cask libreoffice
```

If you can't install it, use DOCX instead:

```bash
python src/main.py generate --format docx
```

### Ollama connection refused

Make sure Ollama is running:

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start it if needed
ollama serve
```

### Ollama request times out

Local inference is slow, especially on CPU. Try:

1. **Increase the timeout** — set `OLLAMA_TIMEOUT` environment variable (default is 300 seconds):
   ```bash
   export OLLAMA_TIMEOUT=600
   ```
2. **Use a smaller model** — smaller models are much faster on CPU:
   ```bash
   python src/main.py generate --model ollama:qwen3.5:1.5b
   python src/main.py generate --model ollama:gemma3
   ```
3. **Pre-load the model** — the first run is slowest because the model must load into memory. Resume Tailor now warms up the model automatically, but you can also do it manually:
   ```bash
   ollama run qwen3.5 "hi"
   ```

### Ollama model not found

If you see "Model 'xyz' not found", pull it first:

```bash
ollama pull qwen3.5
```

List available models:

```bash
ollama list
```

### Ollama out of memory

Large models need lots of RAM. If you're running out of memory:

- Use a smaller model (e.g., `ollama:qwen3.5:1.5b` or `ollama:gemma3`)
- Close other applications to free RAM

### Ollama returns malformed JSON

Local models sometimes produce invalid JSON. Resume Tailor has built-in fallback parsing that handles common issues (trailing commas, markdown fences, etc.). If you still get JSON errors, try a different model — some models are better at structured output than others.

### My profile got corrupted

Reset and start fresh:

```bash
# Back up first (if possible)
python src/main.py profile backup

# Then reset
python src/main.py profile reset
```

### File path not found

- Use forward slashes: `path/to/resume.docx`
- Tilde expansion works: `~/Documents/resume.docx`
- On Windows/WSL, you can use Windows paths: `/mnt/c/Users/you/Desktop/resume.docx`
- Supported input formats: `.txt`, `.docx`, `.pdf`

### I want to start completely fresh

```bash
# Delete your profile
python src/main.py profile reset

# Delete all generated output
rm -rf output/*
```
