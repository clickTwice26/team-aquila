.DEFAULT_GOAL := help
PY ?= python3
PORT ?= 8000

.PHONY: help install dev train run run-prod test lint fmt typecheck sample smoke docker-build docker-run clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime deps + package (editable)
	$(PY) -m pip install -r requirements.txt && $(PY) -m pip install -e .

dev: ## Install dev/test deps + package (editable)
	$(PY) -m pip install -r requirements-dev.txt && $(PY) -m pip install -e .

train: ## Train the tiny local fallback classifier artifact
	$(PY) scripts/train_classifier.py

run: ## Run the dev server (uvicorn, single worker)
	uvicorn queuestorm.main:app --host 0.0.0.0 --port $(PORT) --reload

run-prod: ## Run the production server (gunicorn, multi-worker)
	gunicorn -c deploy/gunicorn_conf.py queuestorm.main:app

test: ## Run the test suite
	$(PY) -m pytest

lint: ## Lint with ruff
	ruff check src tests scripts

fmt: ## Auto-fix lint + format
	ruff check --fix src tests scripts

typecheck: ## Static type check with mypy
	mypy src

sample: ## Generate sample_output.json from the public sample cases
	$(PY) scripts/generate_sample_output.py

smoke: ## Smoke-test a running endpoint (BASE_URL=...)
	BASE_URL=$${BASE_URL:-http://localhost:$(PORT)} bash scripts/smoke.sh

docker-build: ## Build the Docker image
	docker build -f deploy/Dockerfile -t queuestorm-investigator:latest .

docker-run: ## Run the Docker image
	docker run --rm -p $(PORT):8000 queuestorm-investigator:latest

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
