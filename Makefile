###############################################################################
# WATER Framework — Makefile
# Common development & operations commands
###############################################################################
.DEFAULT_GOAL := help
SHELL := /bin/bash

# ── Paths ────────────────────────────────────────────────────────────────────
SRC_DIR     := src
TEST_DIR    := tests
COMPOSE     := docker compose

# ── Python ───────────────────────────────────────────────────────────────────
PYTHON      := python3
PIP         := pip

# ── Colors ───────────────────────────────────────────────────────────────────
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m

.PHONY: help install install-dev lint format typecheck test test-integration \
        orthanc-up orthanc-down orthanc-logs orthanc-status bootstrap clean

# ── Help ─────────────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo ""
	@echo "  WATER Framework — Development Commands"
	@echo "  ────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── Setup ────────────────────────────────────────────────────────────────────
install: ## Install the package in editable mode
	$(PIP) install -e .

install-dev: ## Install with development dependencies
	$(PIP) install -e ".[dev]"
	pre-commit install 2>/dev/null || true

# ── Code quality ─────────────────────────────────────────────────────────────
lint: ## Run linter (ruff)
	ruff check $(SRC_DIR) $(TEST_DIR)

format: ## Auto-format code (ruff)
	ruff format $(SRC_DIR) $(TEST_DIR)
	ruff check --fix $(SRC_DIR) $(TEST_DIR)

typecheck: ## Run static type checking (mypy)
	mypy $(SRC_DIR)

# ── Testing ──────────────────────────────────────────────────────────────────
test: ## Run unit tests
	pytest $(TEST_DIR)/unit -v --tb=short

test-integration: ## Run integration tests (requires Orthanc running)
	pytest $(TEST_DIR)/integration -v --tb=short -m integration

test-all: ## Run all tests with coverage
	pytest $(TEST_DIR) -v --tb=short --cov=$(SRC_DIR) --cov-report=term-missing

# ── Infrastructure ───────────────────────────────────────────────────────────
orthanc-up: ## Start the Orthanc DICOM server (Docker)
	$(COMPOSE) up -d orthanc
	@echo "$(GREEN)Orthanc starting → http://localhost:8042$(RESET)"

orthanc-down: ## Stop the Orthanc DICOM server
	$(COMPOSE) down

orthanc-logs: ## Tail Orthanc container logs
	$(COMPOSE) logs -f orthanc

orthanc-status: ## Check Orthanc health and statistics
	@curl -sf http://localhost:8042/system | python3 -m json.tool 2>/dev/null || \
		echo "$(CYAN)Orthanc is not running. Start with: make orthanc-up$(RESET)"

# ── Data ─────────────────────────────────────────────────────────────────────
bootstrap: ## Download TCIA data and push to Orthanc
	$(PYTHON) -m water.dicom.bootstrap_data

bootstrap-small: ## Bootstrap with only 2 series (quick test)
	$(PYTHON) -m water.dicom.bootstrap_data --max-series 2

# ── Cleanup ──────────────────────────────────────────────────────────────────
clean: ## Remove caches, build artifacts, and downloaded data
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage
	@echo "$(GREEN)Cleaned.$(RESET)"

clean-data: ## Remove downloaded TCIA data (keeps Orthanc DB)
	rm -rf data/tcia_downloads
	@echo "$(GREEN)TCIA download cache cleared.$(RESET)"

clean-all: clean clean-data ## Full cleanup including data
	$(COMPOSE) down -v  # also removes Docker volumes
	@echo "$(GREEN)Full cleanup complete (Docker volumes removed).$(RESET)"
