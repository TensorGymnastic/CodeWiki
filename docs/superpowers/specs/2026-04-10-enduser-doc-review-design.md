# Enduser Documentation Review Design

## Goal

Add a first end-to-end documentation path for `enduser-wiki` that:

- renders user-facing documentation from a validated enduser catalog
- enforces a fixed template/format
- reviews the rendered content with a real LLM judge using `codex`
- runs adversarial review with `opencode` as the second runner
- saves normalized review artifacts that can gate publication

## Scope

This slice covers one vertical path from catalog input to review output:

1. validated catalog YAML
2. rendered markdown document in a fixed format
3. normalized review request payload
4. `codex` review execution
5. `opencode` adversarial review execution
6. structured review artifact validation
7. end-to-end CLI test coverage for the format and artifact flow

This slice does not yet cover:

- HTML rendering
- multi-page site generation
- automatic remediation loops
- CI secrets/bootstrap for external CLIs
- full transaction/entity/page catalog generation beyond the initial template target

## User-Facing Flow

The intended user flow is:

1. `codewiki enduser validate catalog.yaml`
2. `codewiki enduser render-doc catalog.yaml --template <template> --output doc.md`
3. `codewiki enduser review-doc doc.md --catalog catalog.yaml --output review.json`

The review command should:

- call `codex` first for judge scoring and publication guidance
- call `opencode` second for adversarial review and unsupported-claim detection
- normalize both outputs into one machine-readable artifact
- fail if required sections or review artifact fields are missing

## Fixed Documentation Format

The first template should be machine-checkable Markdown with required headings.

Required sections:

- `# <Document Title>`
- `## Purpose`
- `## Audience`
- `## Preconditions`
- `## Steps`
- `## Fields`
- `## Navigation`
- `## Evidence`
- `## Review Status`

Rules:

- `Steps` must be a numbered list
- `Fields` must be a Markdown table
- `Evidence` must contain evidence ids and short summaries
- `Review Status` is reserved for generated review verdicts

This format is intentionally strict so tests can validate structure without depending on subjective prose quality.

## Review Artifact Format

The normalized review artifact should be JSON with this top-level structure:

- `document_path`
- `catalog_path`
- `template_id`
- `judge`
- `adversarial`
- `publication_decision`

`judge` should include:

- `runner`: `codex`
- `status`: `pass` or `fail`
- `scores`:
  - `coverage`
  - `evidence_alignment`
  - `format_compliance`
  - `clarity`
- `summary`
- `findings`

`adversarial` should include:

- `runner`: `opencode`
- `status`: `pass` or `fail`
- `findings`
- `unsupported_claims`
- `missing_evidence`
- `format_attacks`
- `summary`

`publication_decision` should include:

- `status`: `approved` or `rejected`
- `reasons`

## Runner Policy

- `codex` is the primary runner and must execute first.
- `opencode` is the secondary runner and must execute second.
- If `codex` fails to execute, the command should fail rather than silently downgrade to `opencode` only. The ordering is part of the requested policy.
- If `opencode` fails after `codex` succeeds, the command should fail with a clear message because adversarial review is part of the publication gate.

## Architecture

Add a small enduser documentation subsystem under `codewiki/src/enduser/`:

- template definitions and structural validation
- markdown renderer from catalog to document
- external review runner wrappers for `codex` and `opencode`
- normalized review models and JSON serialization

Expose this through new `enduser` CLI commands and cover the system with:

- unit tests for structure validation
- command tests for CLI behavior
- an opt-in integration test for real external runners

## Testing Strategy

Deterministic tests:

- template validation
- rendered markdown structure
- normalized review artifact validation
- command construction for `codex` and `opencode`
- end-to-end CLI flow with monkeypatched subprocess execution

Opt-in integration test:

- only runs when `codex` and `opencode` binaries are present and the environment is explicitly enabled
- validates real external command execution and artifact creation

## Risks

- external CLIs may not return stable text formats, so normalization must rely on explicit prompt constraints and JSON output requirements
- adversarial review can be noisy, so the first gate should prioritize obvious unsupported claims and format violations
- keeping the first template narrow is important; otherwise the renderer and judge prompts will sprawl before the model is stable
