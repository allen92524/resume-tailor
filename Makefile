VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
BLACK := $(VENV)/bin/black

.DEFAULT_GOAL := help

.PHONY: help install dev-install test lint format check-secrets run run-local run-profile dry-run api metrics docker-build docker-run docker-ollama docker-ollama-api docker-ollama-pull test-docker helm-install helm-uninstall helm-template argocd-setup argocd-status release-patch release-minor release-major release-push clean

help: ## Show all available targets with descriptions
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install requirements
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

dev-install: ## Install both requirements.txt and requirements-dev.txt
	python3 -m venv $(VENV)
	$(PIP) install -r requirements-dev.txt

test: ## Run pytest
	$(PYTEST) tests/ -v

lint: ## Run ruff linter
	$(RUFF) check src/ tests/

check-secrets: ## Scan repo for possible personal info (emails, phones, LinkedIn URLs)
	@echo "Scanning for personal info patterns..."
	@EMAIL_RE='[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'; \
	SAFE_EMAILS='(user@example\.com|jane\.doe@email\.com|john@example\.com|test@test\.com|noreply@|example\.org|example\.net|@example\.|@test\.|@localhost|@email\.com|@newmail\.com|@llm\.com|user@domain|name@company|someone@|fake@)'; \
	PHONE_RE='(\([0-9]{3}\)\s*[0-9]{3}[.\-][0-9]{4}|[0-9]{3}[.\-][0-9]{3}[.\-][0-9]{4})'; \
	SAFE_PHONES='(555[.\-][0-9]{3}[.\-][0-9]{4}|\(555\)|555[.\-][0-9]{4}|000[.\-]000[.\-]0000|999[.\-]999[.\-]9999|\(999\) 000[.\-]0000)'; \
	LINKEDIN_RE='linkedin\.com/in/[a-zA-Z0-9_-]+'; \
	SAFE_LINKEDIN='linkedin\.com/in/(example|janedoe|johndoe|yourprofile|username|your-name|sarahchen|johnsmith|michaeltorres|profile)'; \
	FOUND=0; \
	for f in $$(git ls-files -- '*.py' '*.md' '*.txt' '*.yml' '*.yaml' '*.json' '*.toml' '*.cfg' '*.ini' '*.sh' | grep -v venv/ | grep -v node_modules/); do \
		MATCHES=$$(grep -nE "$$EMAIL_RE" "$$f" 2>/dev/null | grep -ivE "$$SAFE_EMAILS" || true); \
		if [ -n "$$MATCHES" ]; then echo "$$f:$$MATCHES"; FOUND=1; fi; \
		MATCHES=$$(grep -nE "$$PHONE_RE" "$$f" 2>/dev/null | grep -ivE "$$SAFE_PHONES" || true); \
		if [ -n "$$MATCHES" ]; then echo "$$f:$$MATCHES"; FOUND=1; fi; \
		MATCHES=$$(grep -nE "$$LINKEDIN_RE" "$$f" 2>/dev/null | grep -ivE "$$SAFE_LINKEDIN" || true); \
		if [ -n "$$MATCHES" ]; then echo "$$f:$$MATCHES"; FOUND=1; fi; \
	done; \
	if [ "$$FOUND" -eq 0 ]; then echo "No personal info patterns found."; else echo ""; echo "Review the matches above."; exit 1; fi

format: ## Run black formatter
	$(BLACK) src/ tests/

run: ## Activate venv and run generate
	$(PYTHON) src/main.py generate

run-local: ## Run generate with local Ollama model (e.g. make run-local MODEL=ollama:qwen3.5)
	@test -n "$(MODEL)" || (echo "Usage: make run-local MODEL=ollama:<model-name>" && exit 1)
	$(PYTHON) src/main.py generate --model $(MODEL)

run-profile: ## Run generate with PROFILE=name (e.g. make run-profile PROFILE=john)
	@test -n "$(PROFILE)" || (echo "Usage: make run-profile PROFILE=name" && exit 1)
	$(PYTHON) src/main.py --profile $(PROFILE) generate

dry-run: ## Run with --dry-run flag
	$(PYTHON) src/main.py generate --dry-run

api: ## Start the FastAPI server on port 8000
	$(VENV)/bin/uvicorn src.web:app --reload --port 8000

metrics: ## Fetch raw Prometheus metrics from the running API
	@curl -s http://localhost:8000/metrics

docker-build: ## Build Docker image
	docker build -t resume-tailor .

docker-run: ## Run Docker container with interactive mode
	docker run -it --rm \
		-e ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY) \
		-v $(HOME)/.resume-tailor:/root/.resume-tailor \
		-v $(PWD)/output:/output \
		resume-tailor generate

docker-ollama: ## Run CLI + Ollama together (no API key needed)
	docker compose -f docker-compose.full.yml run --rm --remove-orphans resume-tailor

docker-ollama-api: ## Start API server + Ollama together
	docker compose -f docker-compose.full.yml --profile api up --remove-orphans

docker-ollama-pull: ## Pull a model into the Ollama container (e.g. make docker-ollama-pull MODEL=qwen3.5)
	@test -n "$(MODEL)" || (echo "Usage: make docker-ollama-pull MODEL=<model-name>" && exit 1)
	docker compose -f docker-compose.full.yml exec ollama ollama pull $(MODEL)

test-docker: docker-build ## Build and smoke-test Docker image
	@echo "==> Testing dry-run (no API key needed)..."
	docker run --rm resume-tailor generate --dry-run
	@echo "==> Testing container starts with ollama model flag (no API key)..."
	docker run --rm -e ANTHROPIC_API_KEY= resume-tailor generate --model ollama:qwen3.5 --dry-run
	@echo "==> Testing health endpoint..."
	@CONTAINER_ID=$$(docker run -d --rm -p 18199:8000 resume-tailor sh -c "pip install -q uvicorn fastapi prometheus-client opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi 2>/dev/null && python -m uvicorn src.web:app --host 0.0.0.0 --port 8000"); \
	sleep 3; \
	STATUS=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:18199/api/v1/health); \
	docker stop $$CONTAINER_ID > /dev/null 2>&1; \
	if [ "$$STATUS" = "200" ]; then echo "Health endpoint OK (200)"; else echo "Health endpoint FAILED ($$STATUS)" && exit 1; fi
	@echo "==> All Docker tests passed."

helm-install: ## Install/upgrade Helm chart to Kubernetes
	@helm upgrade --install resume-tailor helm/resume-tailor --set apiKey=$(ANTHROPIC_API_KEY)

helm-uninstall: ## Uninstall Helm chart from Kubernetes
	helm uninstall resume-tailor

helm-template: ## Render Helm templates locally (dry-run)
	helm template resume-tailor helm/resume-tailor

argocd-setup: ## Create API key secret and apply ArgoCD application
	@test -n "$(ANTHROPIC_API_KEY)" || (echo "Error: ANTHROPIC_API_KEY is not set" && exit 1)
	kubectl create secret generic resume-tailor-api-key \
		--from-literal=api-key=$(ANTHROPIC_API_KEY) \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -f argocd/application.yaml

argocd-status: ## Show ArgoCD application sync status
	@kubectl get application resume-tailor -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null && echo || argocd app get resume-tailor --refresh 2>/dev/null || echo "Could not fetch status. Ensure ArgoCD is installed and the application exists."

release-patch: ## Create patch version tag
	./scripts/bump-version.sh patch

release-minor: ## Create minor version tag
	./scripts/bump-version.sh minor

release-major: ## Create major version tag
	./scripts/bump-version.sh major

release-push: ## Push tags to GitHub
	git push --tags

clean: ## Remove venv, pycache, and output files
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf output/*.docx output/*.pdf
