VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
BLACK := $(VENV)/bin/black

.DEFAULT_GOAL := help

.PHONY: help install dev-install test lint format run run-profile dry-run api docker-build docker-run helm-install helm-uninstall helm-template clean

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

format: ## Run black formatter
	$(BLACK) src/ tests/

run: ## Activate venv and run generate
	$(PYTHON) src/main.py generate

run-profile: ## Run generate with PROFILE=name (e.g. make run-profile PROFILE=john)
	@test -n "$(PROFILE)" || (echo "Usage: make run-profile PROFILE=name" && exit 1)
	$(PYTHON) src/main.py --profile $(PROFILE) generate

dry-run: ## Run with --dry-run flag
	$(PYTHON) src/main.py generate --dry-run

api: ## Start the FastAPI server on port 8000
	$(VENV)/bin/uvicorn src.web:app --reload --port 8000

docker-build: ## Build Docker image
	docker build -t resume-tailor .

docker-run: ## Run Docker container with interactive mode
	docker run -it --rm \
		-e ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY) \
		-v $(HOME)/.resume-tailor:/root/.resume-tailor \
		-v $(PWD)/output:/output \
		resume-tailor generate

helm-install: ## Install/upgrade Helm chart to Kubernetes
	helm upgrade --install resume-tailor helm/resume-tailor --set apiKey=$(ANTHROPIC_API_KEY)

helm-uninstall: ## Uninstall Helm chart from Kubernetes
	helm uninstall resume-tailor

helm-template: ## Render Helm templates locally (dry-run)
	helm template resume-tailor helm/resume-tailor

clean: ## Remove venv, pycache, and output files
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf output/*.docx output/*.pdf
