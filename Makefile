PYTHON ?= python3
CODEWIKI ?= $(PYTHON) -m codewiki.cli.main

ENDUSER_TESTS := tests/test_enduser_docs.py tests/test_enduser_cli.py tests/test_enduser_review.py tests/test_enduser_review_e2e.py tests/test_enduser_review_integration.py
ENDUSER_LINT_PATHS := codewiki/src/enduser codewiki/cli/commands/enduser.py tests/test_enduser_docs.py tests/test_enduser_cli.py tests/test_enduser_review.py tests/test_enduser_review_e2e.py tests/test_enduser_review_integration.py
LOCAL_GATE_FILES := $(ENDUSER_LINT_PATHS) .pre-commit-config.yaml pyproject.toml README.md Makefile scripts/run_mypy.py scripts/run_quick_pip_audit.py scripts/fake_codex_sample.py scripts/run_docs_contracts.py scripts/smoke_install.py examples/enduser/customer-search.catalog.yaml .gitignore .secrets.baseline

SAMPLE_DIR ?= $(CURDIR)/.tmp_make
SAMPLE_CATALOG ?= $(CURDIR)/examples/enduser/customer-search.catalog.yaml
SAMPLE_PAGE ?= page.customers_search
SAMPLE_TEMPLATE ?= page-default
SAMPLE_GUIDE := $(SAMPLE_DIR)/guide.md
SAMPLE_REVIEW := $(SAMPLE_DIR)/review.json
SAMPLE_FAKE_BIN := $(SAMPLE_DIR)/bin

.PHONY: help install-hooks lint test-enduser check local-gates render-sample review-sample clean-sample

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make install-hooks  - Install pre-commit and pre-push hooks via pre-commit' \
		'  make lint           - Run ruff checks on the enduser workflow files' \
		'  make test-enduser   - Run the enduser pytest suite' \
		'  make check          - Run lint + test-enduser' \
		'  make local-gates    - Run the fast local pre-commit gate suite' \
		'  make render-sample  - Render a real page-scoped sample guide from $(SAMPLE_CATALOG)' \
		'  make review-sample  - Run review-doc on the sample guide with a deterministic local codex shim' \
		'  make clean-sample   - Remove sample artifacts under $(SAMPLE_DIR)'

install-hooks:
	$(PYTHON) -m pre_commit install --hook-type pre-commit --hook-type pre-push

lint:
	$(PYTHON) -m ruff format --check $(ENDUSER_LINT_PATHS)
	$(PYTHON) -m ruff check $(ENDUSER_LINT_PATHS)
	$(PYTHON) scripts/run_mypy.py

test-enduser:
	$(PYTHON) -m pytest $(ENDUSER_TESTS) -q

check: lint test-enduser

local-gates:
	$(PYTHON) -m pre_commit run --hook-stage pre-commit --files $(LOCAL_GATE_FILES)

render-sample:
	mkdir -p $(SAMPLE_DIR)
	$(CODEWIKI) enduser render-doc $(SAMPLE_CATALOG) --page $(SAMPLE_PAGE) --template $(SAMPLE_TEMPLATE) --output $(SAMPLE_GUIDE)

review-sample: render-sample
	mkdir -p $(SAMPLE_FAKE_BIN)
	cp scripts/fake_codex_sample.py $(SAMPLE_FAKE_BIN)/codex
	chmod +x $(SAMPLE_FAKE_BIN)/codex
	PATH="$(SAMPLE_FAKE_BIN):$$PATH" $(CODEWIKI) enduser review-doc $(SAMPLE_GUIDE) --catalog $(SAMPLE_CATALOG) --template $(SAMPLE_TEMPLATE) --output $(SAMPLE_REVIEW)

clean-sample:
	rm -rf $(SAMPLE_DIR)
