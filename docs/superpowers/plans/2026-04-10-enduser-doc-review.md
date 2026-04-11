# Enduser Doc Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first end-to-end enduser documentation path with a fixed markdown template, `codex` judge review, `opencode` adversarial review, and validated review artifacts.

**Architecture:** Add a focused renderer and review subsystem under `codewiki/src/enduser/`, expose it through new CLI commands, and gate output through template validation plus normalized review artifacts. Keep deterministic tests local and make real CLI execution opt-in.

**Tech Stack:** Python, Click, Pydantic, pytest, subprocess, YAML/JSON, Markdown

---

### Task 1: Add failing tests for template, renderer, and review models

**Files:**
- Create: `tests/test_enduser_docs.py`
- Create: `tests/test_enduser_review.py`

- [ ] **Step 1: Write the failing template and render tests**

```python
def test_render_doc_produces_required_sections():
    ...

def test_render_doc_rejects_missing_template_sections():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enduser_docs.py -q`
Expected: FAIL because renderer/template modules do not exist yet

- [ ] **Step 3: Write the failing review model tests**

```python
def test_review_artifact_requires_codex_judge_and_opencode_adversarial_sections():
    ...

def test_publication_decision_rejects_failed_reviews():
    ...
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enduser_review.py -q`
Expected: FAIL because review models do not exist yet

- [ ] **Step 5: Commit**

```bash
git add tests/test_enduser_docs.py tests/test_enduser_review.py
git commit -m "test: add failing enduser doc review tests"
```

### Task 2: Implement template and renderer

**Files:**
- Create: `codewiki/src/enduser/docs.py`
- Modify: `codewiki/src/enduser/__init__.py`
- Test: `tests/test_enduser_docs.py`

- [ ] **Step 1: Write minimal template and renderer implementation**

```python
class EnduserDocTemplate(BaseModel):
    ...

def render_enduser_document(...):
    ...
```

- [ ] **Step 2: Run targeted tests**

Run: `python3 -m pytest tests/test_enduser_docs.py -q`
Expected: PASS

- [ ] **Step 3: Refactor only if needed to keep template validation isolated from rendering**

- [ ] **Step 4: Commit**

```bash
git add codewiki/src/enduser/docs.py codewiki/src/enduser/__init__.py tests/test_enduser_docs.py
git commit -m "feat: add enduser document template renderer"
```

### Task 3: Add failing CLI tests for render and review commands

**Files:**
- Modify: `tests/test_enduser_cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
def test_enduser_render_doc_writes_markdown(...):
    ...

def test_enduser_review_doc_writes_review_artifact(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enduser_cli.py -q`
Expected: FAIL because the new commands do not exist yet

- [ ] **Step 3: Commit**

```bash
git add tests/test_enduser_cli.py
git commit -m "test: add failing enduser render and review cli tests"
```

### Task 4: Implement normalized review models and runner wrappers

**Files:**
- Create: `codewiki/src/enduser/review.py`
- Test: `tests/test_enduser_review.py`

- [ ] **Step 1: Implement the review artifact schema and publication gate**

```python
class ReviewScoreSet(BaseModel):
    ...

class EnduserReviewArtifact(BaseModel):
    ...
```

- [ ] **Step 2: Implement `codex` and `opencode` command wrappers with normalized parsing**

```python
def run_codex_judge(...):
    ...

def run_opencode_adversarial(...):
    ...
```

- [ ] **Step 3: Run targeted tests**

Run: `python3 -m pytest tests/test_enduser_review.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add codewiki/src/enduser/review.py tests/test_enduser_review.py
git commit -m "feat: add enduser review artifact and runner wrappers"
```

### Task 5: Implement CLI commands for rendering and reviewing

**Files:**
- Modify: `codewiki/cli/commands/enduser.py`
- Modify: `tests/test_enduser_cli.py`

- [ ] **Step 1: Add `render-doc` and `review-doc` commands**

```python
@enduser_group.command(name="render-doc")
def render_doc(...):
    ...

@enduser_group.command(name="review-doc")
def review_doc(...):
    ...
```

- [ ] **Step 2: Run CLI tests**

Run: `python3 -m pytest tests/test_enduser_cli.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add codewiki/cli/commands/enduser.py tests/test_enduser_cli.py
git commit -m "feat: add enduser render and review commands"
```

### Task 6: Add end-to-end deterministic flow tests

**Files:**
- Create: `tests/test_enduser_review_e2e.py`
- Test: `tests/test_enduser_review_e2e.py`

- [ ] **Step 1: Write the deterministic end-to-end test with monkeypatched subprocess calls**

```python
def test_enduser_review_e2e_generates_doc_and_review_artifact(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enduser_review_e2e.py -q`
Expected: FAIL until the full flow is wired correctly

- [ ] **Step 3: Adjust implementation minimally until it passes**

- [ ] **Step 4: Run the targeted end-to-end test**

Run: `python3 -m pytest tests/test_enduser_review_e2e.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_enduser_review_e2e.py
git commit -m "test: cover enduser review flow end to end"
```

### Task 7: Add opt-in real-runner integration test and user-facing docs

**Files:**
- Create: `tests/test_enduser_review_integration.py`
- Modify: `README.md`
- Modify: `docs/2026-04-10-enduser-wiki-analysis.md`

- [ ] **Step 1: Add an opt-in integration test guarded by environment and binary presence**

```python
@pytest.mark.integration
def test_enduser_review_with_real_codex_and_opencode(...):
    ...
```

- [ ] **Step 2: Document the template format, runner order, and environment expectations**

- [ ] **Step 3: Run docs and integration-adjacent tests as applicable**

Run: `python3 -m pytest tests/test_enduser_docs.py tests/test_enduser_review.py tests/test_enduser_cli.py tests/test_enduser_review_e2e.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_enduser_review_integration.py README.md docs/2026-04-10-enduser-wiki-analysis.md
git commit -m "docs: describe enduser review pipeline"
```

### Task 8: Run full verification

**Files:**
- Modify: none

- [ ] **Step 1: Run the full targeted suite**

Run: `python3 -m pytest tests/test_enduser_models.py tests/test_enduser_catalog.py tests/test_enduser_cli.py tests/test_enduser_playwright.py tests/test_enduser_extract_cli.py tests/test_enduser_docs.py tests/test_enduser_review.py tests/test_enduser_review_e2e.py -q`
Expected: PASS

- [ ] **Step 2: Run a manual CLI smoke flow**

Run: `python3 -m codewiki.cli.main enduser render-doc <catalog.yaml> --output <doc.md>`
Expected: Markdown document with the required headings

Run: `python3 -m codewiki.cli.main enduser review-doc <doc.md> --catalog <catalog.yaml> --output <review.json>`
Expected: JSON artifact containing `judge`, `adversarial`, and `publication_decision`

- [ ] **Step 3: Commit final verification if needed**

```bash
git status
```
